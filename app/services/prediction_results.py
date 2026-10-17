"""Grade immutable predictions against identity-checked final match results."""
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MatchPrediction, PredictionResult
from app.services import predictions as P, refresh as R


def confirmed_result(record, detail, now):
    if (record.generated_at >= record.starts_at or record.starts_at > now
            or not isinstance(detail, dict) or str(detail.get("id")) != record.match_id
            or detail.get("status") != "final"):
        return None
    teams = detail.get("teams")
    expected = {t["id"] for t in record.evidence["teams"]}
    if not isinstance(teams, list) or len(teams) != 2 or any(not isinstance(t, dict) for t in teams):
        return None
    ids = [str(t.get("id")) for t in teams]
    if len(set(ids)) != 2 or set(ids) != expected:
        return None
    scores = [t.get("score") for t in teams]
    if any(isinstance(s, bool) or not isinstance(s, (int, float)) or not 0 <= s <= 5 or s != int(s) for s in scores):
        return None
    if scores[0] == scores[1]:
        return None
    winner = 0 if scores[0] > scores[1] else 1
    if teams[winner].get("won") is False or teams[1-winner].get("won") is True:
        return None
    return {"match_id": record.match_id, "winner_id": ids[winner],
            "scores": dict(zip(ids, map(int, scores))), "checked_at": now}


async def refresh_prediction_results():
    if not get_settings().predictions_enabled:
        return 0
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        records = list((await session.scalars(select(MatchPrediction)
            .outerjoin(PredictionResult, MatchPrediction.match_id == PredictionResult.match_id)
            .where(MatchPrediction.starts_at <= now, PredictionResult.match_id.is_(None))
            .order_by(MatchPrediction.starts_at.desc()).limit(50))).all())
    saved = attempted = 0
    for record in records:
        if not await get_redis().set(f"vlr:prediction:result:{record.match_id}", "checking", nx=True, ex=300):
            continue
        attempted += 1
        try:
            detail = (await P._live_api(f"/match/{record.match_id}")
                      if get_settings().predictions_source_api_url else await R.refresh_match(record.match_id))
            result = confirmed_result(record, detail, datetime.now(timezone.utc))
            if result:
                async with SessionLocal() as session:
                    await session.execute(insert(PredictionResult).values(**result)
                        .on_conflict_do_nothing(index_elements=[PredictionResult.match_id]))
                    await session.commit()
                saved += 1
        except Exception as exc:
            P.log.warning("Prediction result %s unavailable (%s)", record.match_id, type(exc).__name__)
        if attempted >= get_settings().predictions_batch_size:
            break
    return saved


async def accuracy(session, now):
    winner = MatchPrediction.prediction["winner_id"].astext
    actual = PredictionResult.winner_id
    row = (await session.execute(select(
        func.count().filter(winner.is_not(None), actual.is_not(None), winner == actual),
        func.count().filter(winner.is_not(None), actual.is_not(None), winner != actual),
        func.count().filter(winner.is_(None)),
        func.count().filter(winner.is_not(None), actual.is_(None)),
    ).select_from(MatchPrediction).outerjoin(PredictionResult, MatchPrediction.match_id == PredictionResult.match_id)
        .where(MatchPrediction.starts_at <= now, MatchPrediction.generated_at < MatchPrediction.starts_at))).one()
    return dict(zip(("correct", "incorrect", "no_pick", "awaiting_result"), row))
