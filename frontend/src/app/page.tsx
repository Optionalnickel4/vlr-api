import { Panel, SectionHeading } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { LiveBadge } from "@/components/LiveBadge";
import { ScoreDisplay } from "@/components/ScoreDisplay";
import { TableShell } from "@/components/TableShell";

/**
 * Slice 2 preview — a style reference for the locked broadcast primitives +
 * design tokens, using illustrative demo values (NOT real vlr-api data). This
 * page is replaced by the real match center in slice 3.
 */
export default function PrimitivesPreview() {
  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-12">
      <header className="mb-12 flex items-baseline gap-3">
        <span className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">
          valstats<span className="text-accent">.</span>
        </span>
        <span className="font-display text-[13px] font-semibold uppercase tracking-broadcast text-mut">
          broadcast primitives
        </span>
        <span className="ml-auto font-mono text-xs text-dim">slice 2 · preview</span>
      </header>

      <div className="flex flex-col gap-12">
        {/* surfaces */}
        <section className="flex flex-col gap-4">
          <SectionHeading>Surfaces</SectionHeading>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Panel className="p-5">
              <div className="font-mono text-xs text-dim">Panel</div>
              <p className="mt-2 text-sm text-mut">
                Graded near-black surface with a hairline border.
              </p>
            </Panel>
            <Panel className="p-5">
              <div className="font-display text-[40px] font-bold leading-none text-ink tabular-nums">
                58
              </div>
              <div className="mt-1.5 font-display text-[11px] uppercase tracking-broadcast text-mut">
                tests passing
              </div>
            </Panel>
            <Panel className="p-5">
              <div className="font-display text-[40px] font-bold leading-none text-up tabular-nums">
                +26
              </div>
              <div className="mt-1.5 font-display text-[11px] uppercase tracking-broadcast text-mut">
                rating change
              </div>
            </Panel>
          </div>
        </section>

        {/* badges */}
        <section className="flex flex-col gap-4">
          <SectionHeading>Badges &amp; status</SectionHeading>
          <Panel className="flex flex-wrap items-center gap-3 p-5">
            <LiveBadge />
            <Badge tone="up" dot>
              Win
            </Badge>
            <Badge tone="down" dot>
              Loss
            </Badge>
            <Badge tone="warn">Upcoming</Badge>
            <Badge tone="accent">Masters</Badge>
            <Badge tone="neutral">EU</Badge>
          </Panel>
        </section>

        {/* scorebug */}
        <section className="flex flex-col gap-4">
          <SectionHeading>Scorebug</SectionHeading>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Panel className="flex items-center justify-between gap-4 p-5">
              <span className="font-display text-lg font-semibold uppercase tracking-[0.04em] text-ink">
                NRG
              </span>
              <ScoreDisplay score1={1} score2={2} />
              <span className="font-display text-lg font-semibold uppercase tracking-[0.04em] text-up">
                LEVIATÁN
              </span>
            </Panel>
            <Panel className="flex items-center justify-between gap-4 p-5">
              <span className="font-display text-lg font-semibold uppercase tracking-[0.04em] text-ink">
                SEN
              </span>
              <ScoreDisplay score1={null} score2={null} />
              <span className="font-display text-lg font-semibold uppercase tracking-[0.04em] text-ink">
                100T
              </span>
            </Panel>
            <Panel className="flex items-center justify-between gap-4 p-5">
              <span className="font-display text-lg font-semibold uppercase tracking-[0.04em] text-ink">
                FNC
              </span>
              <ScoreDisplay score1={1} score2={0} decided={false} />
              <span className="font-display text-lg font-semibold uppercase tracking-[0.04em] text-ink">
                TH
              </span>
            </Panel>
          </div>
        </section>

        {/* stat table */}
        <section className="flex flex-col gap-4">
          <SectionHeading>Stat table</SectionHeading>
          <Panel className="overflow-hidden p-1.5">
            <TableShell
              columns={[
                { label: "Player" },
                { label: "Agent" },
                { label: "ACS", align: "right" },
                { label: "K:D", align: "right" },
                { label: "KAST", align: "right" },
                { label: "ADR", align: "right" },
              ]}
            >
              {[
                ["TenZ", "Jett", "263.8", "1.32", "72%", "156.4"],
                ["zekken", "Raze", "241.1", "1.18", "74%", "149.0"],
                ["johnqt", "Omen", "198.4", "1.04", "78%", "131.7"],
              ].map(([player, agent, acs, kd, kast, adr]) => (
                <tr key={player}>
                  <td className="font-display font-semibold tracking-[0.03em] text-ink">
                    {player}
                  </td>
                  <td className="text-mut">{agent}</td>
                  <td className="text-right font-mono text-ink">{acs}</td>
                  <td className="text-right font-mono text-ink">{kd}</td>
                  <td className="text-right font-mono text-mut">{kast}</td>
                  <td className="text-right font-mono text-ink">{adr}</td>
                </tr>
              ))}
            </TableShell>
          </Panel>
        </section>
      </div>
    </main>
  );
}
