import { cn } from "@/lib/cn";
import { Panel } from "@/components/Panel";
import { TeamCrest } from "@/components/TeamCrest";
import type { ScheduleBoardData, ScheduleDay } from "@/lib/schedule";
import type { UpcomingMatch } from "@/types/vlr";

// ScheduleBoard — the broadcast schedule: a "NEXT UP" hero, then day sections
// (TODAY / TOMORROW / weekday), each sub-grouped under a single teal event
// label. Typographic crests stand in for logos (none in the match-list payload).
// All server-rendered; the derived day comes from the page's `new Date()`.
//
// NOTE ON THE RIGHT SLOT: vlr's upcoming feed has no BO/series-format field, so
// the row/hero surface the raw start clock (`startTime`) there instead of a
// fabricated "BO3". The amber countdown pill carries the relative time.

const TEAM_NAME =
  "font-display font-semibold uppercase tracking-[0.03em] leading-tight text-ink";

/** Amber countdown pill (mono), the schedule's relative-time marker. */
function CountdownPill({ label, size = "sm" }: { label: string; size?: "sm" | "lg" }) {
  return (
    <span
      className={cn(
        "inline-block shrink-0 rounded-full border border-warn/40 bg-warn/[0.09]",
        "font-mono font-semibold uppercase tracking-[0.04em] text-warn",
        size === "lg" ? "px-3 py-1 text-[14px]" : "px-2 py-0.5 text-[11px]",
      )}
    >
      {label}
    </span>
  );
}

/** One team side: crest above, name below, centered — mirrors on both flanks. */
function HeroSide({ name }: { name: string | null }) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-3 text-center">
      <TeamCrest name={name} size="lg" />
      <span className={cn(TEAM_NAME, "text-[22px] sm:text-[26px]")}>
        {name ?? "TBD"}
      </span>
    </div>
  );
}

function Hero({ m }: { m: UpcomingMatch }) {
  const body = (
    <div className="relative overflow-hidden rounded-[12px] border border-line bg-gradient-to-b from-panel to-panel-2">
      {/* teal left accent bar — the showpiece marker */}
      <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-accent" />

      <div className="flex items-start justify-between gap-3 pl-6 pr-5 pt-4 sm:pr-7">
        <div className="min-w-0">
          <div className="font-display text-[11px] font-semibold uppercase tracking-broadcast text-accent">
            Next Up
          </div>
          <div className="mt-1 truncate font-display text-[13px] uppercase tracking-[0.08em] text-mut">
            {m.event ?? "—"}
            {m.series ? <span className="text-dim"> · {m.series}</span> : null}
          </div>
        </div>
        {m.timeUntil ? <CountdownPill label={m.timeUntil} size="lg" /> : null}
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-7 pl-6 pr-5 sm:gap-6 sm:pr-7">
        <HeroSide name={m.team1} />
        <span className="font-display text-[15px] font-semibold uppercase tracking-[0.2em] text-dim">
          vs
        </span>
        <HeroSide name={m.team2} />
      </div>

      {m.startTime ? (
        <div className="border-t border-line/60 py-2.5 pl-6 pr-5 text-center font-mono text-[12px] text-dim sm:pr-7">
          {m.startTime}
        </div>
      ) : null}
    </div>
  );

  return m.id ? (
    <a href={`/match/${m.id}`} className="block">
      {body}
    </a>
  ) : (
    body
  );
}

/** One airy full-width row: countdown left · matchup center · start time right. */
function Row({ m }: { m: UpcomingMatch }) {
  const inner = (
    <div className="grid grid-cols-[64px_1fr_auto] items-center gap-3 px-3 py-3.5 sm:px-4">
      <div className="justify-self-start">
        {m.timeUntil ? (
          <CountdownPill label={m.timeUntil} />
        ) : (
          <span className="font-mono text-[11px] text-dim">TBD</span>
        )}
      </div>

      <div className="grid min-w-0 grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-3">
        <div className="flex min-w-0 items-center justify-end gap-2">
          <span className={cn(TEAM_NAME, "truncate text-[15px]")}>
            {m.team1 ?? "TBD"}
          </span>
          <TeamCrest name={m.team1} size="sm" />
        </div>
        <span className="font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-dim">
          vs
        </span>
        <div className="flex min-w-0 items-center gap-2">
          <TeamCrest name={m.team2} size="sm" />
          <span className={cn(TEAM_NAME, "truncate text-[15px]")}>
            {m.team2 ?? "TBD"}
          </span>
        </div>
      </div>

      <div className="justify-self-end text-right">
        {m.startTime ? (
          <span className="font-mono text-[11px] text-dim">{m.startTime}</span>
        ) : null}
      </div>
    </div>
  );

  const shell =
    "block border-b border-line/60 last:border-b-0 transition-colors hover:bg-ink/[0.03]";

  return m.id ? (
    <a href={`/match/${m.id}`} className={shell}>
      {inner}
    </a>
  ) : (
    <div className={shell}>{inner}</div>
  );
}

function DaySection({ day }: { day: ScheduleDay }) {
  // today bright → future progressively muted
  const headTone =
    day.kind === "today"
      ? "text-ink"
      : day.kind === "tomorrow"
        ? "text-mut"
        : "text-dim";

  return (
    <section className="flex flex-col gap-3">
      <h3
        className={cn(
          "flex items-center gap-3 font-display text-[13px] font-semibold uppercase tracking-broadcast",
          headTone,
          "after:h-px after:flex-1 after:bg-line after:content-['']",
        )}
      >
        {day.label}
        {day.kind === "today" && (
          <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
        )}
      </h3>

      <Panel className="overflow-hidden">
        {day.events.map((grp) => (
          <div key={grp.key}>
            {/* event stated ONCE per group (teal), not on every row */}
            <div className="flex items-center gap-2 border-b border-line/60 bg-ink/[0.02] px-3 py-2 sm:px-4">
              <span className="truncate font-display text-[11px] font-semibold uppercase tracking-[0.1em] text-accent">
                {grp.event ?? "—"}
              </span>
              {grp.series && (
                <span className="truncate font-body text-[12px] text-dim">
                  · {grp.series}
                </span>
              )}
            </div>
            {grp.matches.map((m, i) => (
              <Row key={m.id ?? `${m.team1}-${m.team2}-${i}`} m={m} />
            ))}
          </div>
        ))}
      </Panel>
    </section>
  );
}

export function ScheduleBoard({
  board,
  count,
  stale,
}: {
  board: ScheduleBoardData;
  count: number;
  stale: boolean;
}) {
  if (count === 0) {
    return (
      <Panel className="px-4 py-10 text-center">
        <p className="font-body text-sm text-dim">
          {stale
            ? "Source unavailable — showing nothing."
            : "No upcoming matches scheduled."}
        </p>
      </Panel>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {board.hero && <Hero m={board.hero} />}
      {board.days.map((day) => (
        <DaySection key={day.key} day={day} />
      ))}
    </div>
  );
}
