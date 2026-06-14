import Link from "next/link";
import { cn } from "@/lib/cn";
import {
  PLAYER_FLAT_EPSILON,
  playerOverall,
  shouldRenderTrendLine,
  signatureAgent,
} from "@/lib/vlr";
import type { ApiResponse, PlayerDetail, PlayerMatch, PlayerTrend } from "@/types/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { Sparkline } from "@/components/Sparkline";

/**
 * PlayerCard — the broadcast player lower-third at the top of the player page. It
 * reads like an ESPN player card: identity, a headline aggregate stat line, a
 * signature-agent chip, a recent-form strip, and a compact rating trend — the
 * always-populated headline, with the deep 14-agent table living below it.
 *
 * The three headline numbers are ROUNDS-WEIGHTED overalls (`playerOverall`) — VLR
 * exposes no totals row, only per-agent rows, so the data layer collapses them
 * weighting by rounds (a 5881-round Omen dominates a 15-round Harbor). All values
 * are parseNumeric-coerced (dash, never NaN); a missing trend shrinks to a slim
 * young-history note rather than a fake flat line (the only element empty at
 * launch). Pure broadcast chroma — same vocabulary as the team/match cards.
 */
const fmtRating = (n: number | null) => (n === null ? "—" : n.toFixed(2));
const fmtKd = (n: number | null) => (n === null ? "—" : n.toFixed(2));
const fmtAcs = (n: number | null) => (n === null ? "—" : String(Math.round(n)));

function HeadlineStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-display text-[10px] font-semibold uppercase tracking-[0.16em] text-dim">
        {label}
      </span>
      <span className="font-mono text-3xl font-bold tabular-nums text-ink">{value}</span>
    </div>
  );
}

/** Recent-form dots: most-recent-first, win-green / loss-red broadcast chroma. */
function FormStrip({ matches }: { matches: PlayerMatch[] }) {
  const recent = matches.slice(0, 10); // matches arrive most-recent-first
  if (recent.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="font-display text-[10px] font-semibold uppercase tracking-[0.16em] text-dim">
        Form
      </span>
      <div className="flex items-center gap-1">
        {recent.map((m, i) => {
          const win = m.result === "win";
          const loss = m.result === "loss";
          return (
            <span
              key={m.id ?? i}
              title={win ? "Win" : loss ? "Loss" : "—"}
              className={cn(
                "h-3.5 w-3.5 rounded-[3px]",
                win ? "bg-up" : loss ? "bg-down" : "bg-line",
              )}
            >
              <span className="sr-only">{win ? "W" : loss ? "L" : "-"}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function SignatureChip({ agent, usage }: { agent: string; usage: string | null }) {
  return (
    <span className="inline-flex w-fit items-center gap-2 rounded-full border border-line bg-panel-2/60 px-2.5 py-1">
      <span className="font-display text-[10px] font-semibold uppercase tracking-[0.16em] text-dim">
        Main
      </span>
      <span className="font-display text-[12px] font-semibold uppercase tracking-[0.08em] text-accent">
        {agent}
      </span>
      {usage && <span className="font-mono text-[12px] text-mut">· {usage}</span>}
    </span>
  );
}

/** Compact rating trend beside the headline. Rich → small sparkline; thin → a
 *  slim young-history note (NOT a fake flat line — the degenerate-flat gate). */
function CompactTrend({ trend }: { trend: ApiResponse<PlayerTrend> }) {
  const t = trend.data[0] ?? null;
  const points = t?.ratingTrend ?? [];
  const errored = !t && trend.stale;
  const hasLine = shouldRenderTrendLine(points, PLAYER_FLAT_EPSILON);
  const change = t?.ratingChange ?? null;
  const dir = change === null || change === 0 ? "flat" : change > 0 ? "up" : "down";

  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-display text-[10px] font-semibold uppercase tracking-[0.16em] text-dim">
        Rating Trend
        {t?.windowDays != null && (
          <span className="ml-1.5 font-mono text-[10px] font-normal tracking-normal text-dim">
            {t.windowDays}d
          </span>
        )}
      </span>
      {hasLine ? (
        <Sparkline
          values={points.map((p) => p.rating)}
          tone={dir}
          width={150}
          height={36}
          className="w-[150px]"
        />
      ) : (
        <p className="max-w-[190px] font-body text-[11px] leading-snug text-dim">
          {errored
            ? "Trend unavailable right now."
            : "History is still young — fills in as the page is viewed."}
        </p>
      )}
    </div>
  );
}

export function PlayerCard({
  player,
  trend,
}: {
  player: PlayerDetail;
  trend: ApiResponse<PlayerTrend>;
}) {
  const overall = playerOverall(player.agentStats);
  const sig = signatureAgent(player.agentStats);

  return (
    <Panel className="border-l-[3px] border-l-accent p-5 sm:p-6">
      {/* identity + recent-form strip */}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="font-display text-4xl font-bold uppercase leading-none tracking-[0.03em] text-ink">
            {player.alias ?? "—"}
          </h1>
          {player.realName && (
            <span className="font-body text-base text-mut">{player.realName}</span>
          )}
          {player.team &&
            (player.teamId ? (
              <Link
                href={`/team/${player.teamId}`}
                className="font-display text-sm font-semibold uppercase tracking-[0.08em] text-accent"
              >
                {player.team}
              </Link>
            ) : (
              <span className="font-display text-sm font-semibold uppercase tracking-[0.08em] text-mut">
                {player.team}
              </span>
            ))}
          {player.country && (
            <Badge tone="neutral" className="self-center uppercase">
              {player.country}
            </Badge>
          )}
        </div>
        <FormStrip matches={player.matches} />
      </div>

      <div className="my-5 h-px bg-line/60" />

      {/* headline aggregates + signature chip | compact trend */}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-5">
        <div className="flex flex-col gap-3">
          <div className="flex items-end gap-7">
            <HeadlineStat label="Rating" value={fmtRating(overall.rating)} />
            <HeadlineStat label="K/D" value={fmtKd(overall.kd)} />
            <HeadlineStat label="ACS" value={fmtAcs(overall.acs)} />
          </div>
          {sig && <SignatureChip agent={sig.agent} usage={sig.usage} />}
        </div>
        <CompactTrend trend={trend} />
      </div>
    </Panel>
  );
}
