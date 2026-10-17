"""Scheduled, immutable pre-match picks. Public reads never call the model.

Only fresh match/team caches are used. The opt-in scheduler may populate missing
detail caches through the existing bounded services, respecting VLR throttling.
Unknown UTC starts, TBD teams, sparse form and already-started matches abstain.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import httpx

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.cache import cache_get, get_redis
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MatchPrediction, PredictionResult
from app.services import refresh as R
from app.services.openclaw import connection_ready, request_prediction
from app.services.prediction_evidence import enrich

log = logging.getLogger("vlr.predictions")
PROMPT_VERSION = "winner-explanation-v3"
SAFETY_MARGIN = timedelta(minutes=15)
HORIZON = timedelta(days=7)
WORK_TIMEOUT = 180
LEASE_SECONDS = 190
_RELEASE = "if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0"
_COOLDOWN = "if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('SET',KEYS[1],'cooldown','EX',1800) end return 0"
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]


class PredictionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    winner_id: str | None
    explanation: Text
    evidence_ids: list[str] = Field(min_length=2, max_length=8)
    caveats: list[Text] = Field(min_length=1, max_length=3)


class EvidenceUnavailable(Exception):
    pass


def utc_start(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except ValueError:
        return None


def _id(value: object) -> str | None:
    text = str(value) if value is not None else ""
    return text if re.fullmatch(r"[0-9]{1,32}", text) else None


def _text(value: object, limit: int = 256) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def eligible_detail(detail: dict, now: datetime) -> bool:
    start = utc_start(detail.get("starts_at"))
    teams = detail.get("teams")
    return bool(
        start and SAFETY_MARGIN < start - now <= HORIZON
        and detail.get("status") in (None, "upcoming")
        and isinstance(teams, list) and len(teams) == 2
        and all(isinstance(t, dict) and _id(t.get("id")) and _text(t.get("name"))
                and t["name"].strip().casefold() not in ("tbd", "tba", "unknown")
                for t in teams)
        and _id(teams[0]["id"]) != _id(teams[1]["id"])
        and not any(r.get("winner") in (1, 2) for m in detail.get("maps", [])
                    for r in m.get("rounds", []))
    )


def build_evidence(match_id: str, detail: dict, teams: list[dict], now: datetime) -> dict:
    if not eligible_detail(detail, now) or len(teams) != 2:
        raise EvidenceUnavailable("Match identity or start is unconfirmed")
    identities = detail["teams"]
    facts = []
    for identity, team in zip(identities, teams):
        if _id(team.get("id")) != _id(identity["id"]):
            raise EvidenceUnavailable("Team identity is unconfirmed")
        recent = []
        for row in team.get("results", []):
            if not isinstance(row, dict) or row.get("result") not in ("win", "loss"):
                continue
            # Same-day results have ambiguous source-local time; exclude them.
            raw_date = _text(row.get("date")) or ""
            date = re.match(r"^(\d{4})[/\-](\d{2})[/\-](\d{2})", raw_date)
            try:
                played = datetime(*(int(x) for x in date.groups()), tzinfo=timezone.utc) if date else None
            except ValueError:
                played = None
            rid = _id(row.get("id"))
            if not played or played.date() >= now.date() or not rid or rid == match_id:
                continue
            if now.date() - played.date() > timedelta(days=90):
                continue
            recent.append({"match_id": rid, "result": row["result"],
                           "opponent": _text(row.get("opponent")), "date": played.date().isoformat()})
        recent = sorted({row["match_id"]: row for row in recent}.values(),
                        key=lambda row: row["date"], reverse=True)[:5]
        if len(recent) < 3:
            raise EvidenceUnavailable("Not enough recent results for both teams")
        tid = _id(identity["id"])
        wins = sum(row["result"] == "win" for row in recent)
        facts.append({"id": f"form:{tid}", "team_id": tid,
                      "text": f"{identity['name']}: {wins} wins and {len(recent) - wins} losses in {len(recent)} recent recorded matches.",
                      "source_url": f"https://www.vlr.gg/team/{tid}", "matches": recent})
    return {
        "match_id": match_id, "collected_at": now.isoformat(),
        "starts_at": detail["starts_at"], "event": _text(detail.get("event")),
        "series": _text(detail.get("series")), "format": _text(detail.get("format")),
        "teams": [{"id": _id(t["id"]), "name": _text(t["name"]), "logo": _text(t.get("logo"), 1024)} for t in identities],
        "facts": facts,
        "limitations": ["Recent results are an uneven sample, not opponent-adjusted ratings.",
                         "No roster availability, map-pool or veto evidence is supplied.",
                         "Same-day results and results older than 90 days are excluded."],
    }


def validate_answer(raw: dict, evidence: dict) -> dict:
    answer = PredictionAnswer.model_validate(raw)
    teams = {team["id"] for team in evidence["teams"]}
    facts = {fact["id"]: fact for fact in evidence["facts"]}
    if answer.winner_id is not None and answer.winner_id not in teams:
        raise ValueError("Winner is not a match participant")
    if any(ref not in facts for ref in answer.evidence_ids):
        raise ValueError("Unknown evidence reference")
    if {facts[ref]["team_id"] for ref in answer.evidence_ids} != teams:
        raise ValueError("Evidence must cover both teams")
    # User requested winner + explanation, without odds or score predictions.
    copy = " ".join([answer.explanation, *answer.caveats])
    if re.search(r"\d\s*%|\b\d+\s*[-:]\s*\d+\b", copy):
        raise ValueError("Probabilities and predicted scores are outside this release")
    result = answer.model_dump()
    result["evidence_ids"] = list(dict.fromkeys(answer.evidence_ids))
    return result


async def _fresh_detail(match_id: str, force: bool = False) -> dict:
    if get_settings().predictions_source_api_url:
        detail = await _live_api(f"/match/{match_id}")
        if not isinstance(detail, dict):
            raise EvidenceUnavailable("Live match data unavailable")
        if force or not utc_start(detail.get("starts_at")):
            # The current live API predates the absolute UTC field. Verify only
            # that missing timestamp against its original VLR page, fail closed
            # if participant identity or match status changed.
            verified = await R.refresh_match(match_id)
            if ([str(t.get("id")) for t in detail.get("teams", [])]
                    != [str(t.get("id")) for t in verified.get("teams", [])]
                    or verified.get("status") in ("live", "final")):
                raise EvidenceUnavailable("Live fixture changed")
            detail = {**detail, "starts_at": verified.get("starts_at")}
        return detail
    detail = None if force else await cache_get(R.CACHE_MATCH.format(id=match_id))
    return detail if isinstance(detail, dict) else await R.refresh_match(match_id)


async def _team(team_id: str) -> dict:
    if get_settings().predictions_source_api_url:
        team = await _live_api(f"/team/{team_id}")
        if not isinstance(team, dict):
            raise EvidenceUnavailable("Live team data unavailable")
        return team
    team = await cache_get(R.CACHE_TEAM.format(id=team_id))
    return team if isinstance(team, dict) else await R.refresh_team(team_id)


async def _live_api(path: str):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.get(settings.predictions_source_api_url.rstrip("/") + path,
                                    headers={"Accept": "application/json", "User-Agent": settings.user_agent})
        response.raise_for_status()
        if response.headers.get("X-VLR-Cache") == "stale":
            raise EvidenceUnavailable("Live API evidence is stale")
        return response.json()


async def _exists(match_id: str) -> bool:
    async with SessionLocal() as session:
        return await session.get(MatchPrediction, match_id) is not None


async def _save(evidence: dict, prediction: dict, generated_at: datetime) -> bool:
    # Unique match key + DO NOTHING makes first publication immutable across workers.
    stmt = insert(MatchPrediction).values(
        match_id=evidence["match_id"], starts_at=utc_start(evidence["starts_at"]),
        generated_at=generated_at, evidence=evidence, prediction=prediction,
        input_hash=hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest(),
        agent_id=get_settings().openclaw_agent_id, prompt_version=PROMPT_VERSION,
    ).on_conflict_do_nothing(index_elements=[MatchPrediction.match_id]).returning(MatchPrediction.match_id)
    async with SessionLocal() as session:
        saved = (await session.execute(stmt)).scalar_one_or_none()
        await session.commit()
        return saved is not None


async def generate_one(match_id: str, lease: str, owner: str) -> bool:
    if not _id(match_id) or await _exists(match_id):
        return False
    now = datetime.now(timezone.utc)
    detail = await _fresh_detail(match_id)
    if not eligible_detail(detail, now):
        return False
    # Serial loads respect the existing single upstream throttle.
    teams = [await _team(_id(t["id"])) for t in detail["teams"]]
    evidence = build_evidence(match_id, detail, teams, datetime.now(timezone.utc))
    async def historical(mid):
        if get_settings().predictions_source_api_url:
            return await _live_api(f"/match/{mid}")
        return await R.refresh_match(mid)
    evidence = await enrich(evidence, teams, historical)
    answer = validate_answer(await request_prediction(evidence), evidence)
    # Re-scrape match status after inference. Never bank a post-start pick or a
    # prediction for changed participants, even if the schedule cache lags.
    current = await _fresh_detail(match_id, force=True)
    finished = datetime.now(timezone.utc)
    if not eligible_detail(current, finished):
        return False
    if ([str(t["id"]) for t in current["teams"]] != [t["id"] for t in evidence["teams"]]
            or current.get("starts_at") != evidence["starts_at"]):
        return False
    if await get_redis().get(lease) != owner:
        return False
    return await _save(evidence, answer, finished)


async def refresh_predictions() -> int:
    settings = get_settings()
    if not settings.predictions_enabled or not connection_ready(settings):
        return 0
    upcoming = await cache_get(R.CACHE_UPCOMING)
    if not isinstance(upcoming, list):
        return 0
    generated = attempted = 0
    for row in upcoming:
        mid = _id(row.get("id")) if isinstance(row, dict) else None
        if not mid or row.get("status") != "upcoming" or await _exists(mid):
            continue
        names = row.get("teams", [])
        if len(names) != 2 or any(not isinstance(n, str) or n.strip().casefold() in ("tbd", "tba", "") for n in names):
            continue
        # Cheap rough gate only: absolute date/status checks happen on detail.
        eta = str(row.get("eta") or "")
        if not re.search(r"\d+\s*[dh]", eta):
            continue
        lease = f"vlr:prediction:{mid}:lease"
        owner = uuid4().hex
        if not await get_redis().set(lease, owner, nx=True, ex=LEASE_SECONDS):
            continue
        attempted += 1
        saved = False
        try:
            async with asyncio.timeout(WORK_TIMEOUT):
                saved = await generate_one(mid, lease, owner)
                generated += int(saved)
        except Exception as exc:
            # Exceptions can contain provider responses/secrets; log class only.
            log.warning("Prediction %s unavailable (%s)", mid, type(exc).__name__)
        finally:
            # Sparse or unavailable fixtures yield to later matches next run.
            await get_redis().eval(_RELEASE if saved else _COOLDOWN, 1, lease, owner)
        if attempted >= settings.predictions_batch_size:
            break
    return generated


async def list_predictions() -> dict:
    """Read schedule + recent saved records, gracefully preserving saved picks."""
    rows = []
    stale = False
    records = []
    results = {}
    summary = None
    try:
        rows = await cache_get(R.CACHE_UPCOMING)
        if not isinstance(rows, list):
            rows, stale = [], True
    except Exception:
        stale = True
    try:
        async with SessionLocal() as session:
            records = list((await session.scalars(
                select(MatchPrediction).order_by(MatchPrediction.starts_at.desc()).limit(50)
            )).all())
            from app.services.prediction_results import accuracy
            summary = await accuracy(session, datetime.now(timezone.utc))
            if records:
                results = {r.match_id: {"winner_id": r.winner_id, "scores": r.scores}
                           for r in (await session.scalars(select(PredictionResult)
                               .where(PredictionResult.match_id.in_([r.match_id for r in records])))).all()}
    except Exception:
        stale = True
    saved = {record.match_id: record for record in records}
    cards = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not (mid := _id(row.get("id"))) or mid in seen:
            continue
        seen.add(mid)
        names = row.get("teams", [])
        cards.append(_card(mid, saved.get(mid), names=names, event=_text(row.get("event")),
                           timing=_text(row.get("eta"))))
    cards.extend(_card(r.match_id, r) for r in records if r.match_id not in seen)
    for card in cards:
        card["result"] = results.get(card["match_id"]) if card["prediction"] else None
    return {"data": cards, "stale": stale, "accuracy": summary,
            "error": "Prediction coverage temporarily unavailable" if stale else None}


def _card(mid: str, record: MatchPrediction | None, names: list | None = None,
          event: str | None = None, timing: str | None = None) -> dict:
    if record:
        snapshot = record.evidence
        # If the schedule changed sides/participants, keep the old record in the
        # database but withhold its pick from the current fixture.
        if names is not None and names != [t["name"] for t in snapshot["teams"]]:
            return _card(mid, None, names, event, timing)
        return {"match_id": mid, "teams": snapshot["teams"], "event": snapshot.get("event"),
                "timing": timing, "starts_at": record.starts_at.isoformat(),
                "generated_at": record.generated_at.isoformat(),
                "status": "no_pick" if record.prediction["winner_id"] is None else "published",
                "prediction": record.prediction, "facts": snapshot["facts"],
                "limitations": snapshot["limitations"]}
    return {"match_id": mid,
            "teams": [{"id": None, "name": _text(name) or "TBD", "logo": None} for name in (names or [])[:2]],
            "event": event, "timing": timing, "starts_at": None, "generated_at": None,
            "status": "pending", "prediction": None, "facts": [], "limitations": []}
