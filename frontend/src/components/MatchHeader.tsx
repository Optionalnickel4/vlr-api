import type { MatchDetail } from "@/types/vlr";
import { cn } from "@/lib/cn";
import { liveMapScore } from "@/lib/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { LiveBadge } from "@/components/LiveBadge";
import { ScoreDisplay } from "@/components/ScoreDisplay";

/**
 * MatchHeader — the broadcast scorebug for a match: event + stage line, both
 * teams with the series score (winner lit green), a status/format marker, the
 * veto/picks strip, and an "Open on VLR.gg" source link. Mirrors the match-card
 * language used in the center, scaled up to a page header.
 *
 * During a LIVE match whose series is still 0:0 (a map is in progress but not yet
 * awarded), the scorebug shows the live MAP score (e.g. 9–3) with a "MAP n · name"
 * caption instead of the misleading 0:0 series score — see `liveMapScore`. Once a
 * map is won (series 1:0+) or the match is final, it's the series score as before.
 */
export function MatchHeader({ match }: { match: MatchDetail }) {
  const [t1, t2] = match.teams;
  const live = match.status === "live";
  const liveMap = liveMapScore(match);
  const TEAM =
    "font-display text-2xl font-bold uppercase tracking-[0.03em] leading-none sm:text-3xl";

  return (
    <Panel className="flex flex-col gap-5 p-6">
      {/* event / stage + status */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
        <span className="font-display uppercase tracking-[0.12em] text-mut">
          {match.event ?? "—"}
        </span>
        {match.series && (
          <span className="font-body text-dim">· {match.series}</span>
        )}
        <span className="ml-auto flex items-center gap-2">
          {match.format && <Badge tone="neutral">{match.format}</Badge>}
          {live ? (
            <LiveBadge />
          ) : (
            match.status && <Badge tone="neutral">{match.status}</Badge>
          )}
        </span>
      </div>

      {/* scorebug */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <a
          href={t1?.id ? `/team/${t1.id}` : undefined}
          className={cn(
            TEAM,
            "text-right",
            t1?.won ? "text-up" : t2?.won ? "text-mut" : "text-ink",
          )}
        >
          {t1?.name ?? "TBD"}
        </a>
        {liveMap ? (
          // live, series still level → show the in-progress MAP score, captioned
          // so it reads as the current map, not the series. No winner color
          // (decided=false): the map's still being played.
          <div className="flex flex-col items-center gap-1.5">
            <ScoreDisplay
              score1={liveMap.score1}
              score2={liveMap.score2}
              decided={false}
              size="lg"
            />
            <span className="font-display text-[10px] font-semibold uppercase tracking-[0.16em] text-mut">
              Map {liveMap.mapNumber}
              {liveMap.name ? ` · ${liveMap.name}` : ""}
            </span>
          </div>
        ) : (
          <ScoreDisplay
            score1={t1?.score ?? null}
            score2={t2?.score ?? null}
            decided={match.status === "final"}
            size="lg"
          />
        )}
        <a
          href={t2?.id ? `/team/${t2.id}` : undefined}
          className={cn(
            TEAM,
            "text-left",
            t2?.won ? "text-up" : t1?.won ? "text-mut" : "text-ink",
          )}
        >
          {t2?.name ?? "TBD"}
        </a>
      </div>

      {/* veto / picks strip */}
      {match.veto && (
        <p className="border-t border-line/60 pt-4 text-center font-body text-[12px] leading-relaxed text-dim">
          {match.veto}
        </p>
      )}

      {match.url && (
        <div className="text-center">
          <a
            href={match.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-display text-[11px] font-semibold uppercase tracking-[0.12em] text-accent"
          >
            Open on VLR.gg ↗
          </a>
        </div>
      )}
    </Panel>
  );
}
