import Link from "next/link";
import type { RosterMember } from "@/types/vlr";
import { TableShell } from "@/components/TableShell";
import { Badge } from "@/components/Badge";

/**
 * TeamRosterPanel — the active roster as a tight broadcast stat table: alias,
 * real name, role, country. Players come first, staff (coach / manager) sink to
 * the bottom under a dim divider so the five starters read at a glance. The
 * captain carries a small accent badge. Each alias links to that player's
 * INTERNAL detail page (/player/{id}) when we have the id; only members without
 * a player id fall back to their vlr.gg page.
 */
function RosterRow({ m }: { m: RosterMember }) {
  const alias = (
    <span className="font-display text-sm font-semibold uppercase tracking-[0.03em] text-ink">
      {m.alias ?? "—"}
    </span>
  );
  return (
    <tr>
      <td>
        <span className="flex items-center gap-2">
          {m.playerId ? (
            <Link
              href={`/player/${m.playerId}`}
              className="transition-colors hover:text-accent"
            >
              {alias}
            </Link>
          ) : m.url ? (
            <a href={m.url} target="_blank" rel="noopener noreferrer">
              {alias}
            </a>
          ) : (
            alias
          )}
          {m.isCaptain && (
            <Badge tone="accent" className="px-1.5 py-0">
              Captain
            </Badge>
          )}
        </span>
      </td>
      <td className="font-body text-[13px] text-mut">{m.realName ?? "—"}</td>
      <td className="font-body text-[13px] text-mut">{m.role ?? "—"}</td>
      <td className="font-body text-[13px] uppercase text-dim">
        {m.country ?? "—"}
      </td>
    </tr>
  );
}

export function TeamRosterPanel({
  roster,
  teamName,
}: {
  roster: RosterMember[];
  teamName?: string | null;
}) {
  const players = roster.filter((m) => !m.isStaff);
  const staff = roster.filter((m) => m.isStaff);

  return (
    <section aria-labelledby="team-roster">
      <div className="td-section-heading"><div><p className="td-kicker">03 / Team sheet</p><h2 id="team-roster">Roster</h2></div><p>{players.length} listed players · {staff.length} staff</p></div>
      {roster.length > 0 && <p className="td-caption">Scroll horizontally to see all columns on smaller screens.</p>}
      {roster.length === 0 ? <p className="td-empty">No roster listed by the source.</p> : <div className="td-table-scroll td-roster" tabIndex={0} role="region" aria-label="Team roster, scroll horizontally">
      <TableShell className="td-table"
        // First column heads with the team name (same identity anchor
        // PlayerStatsTable uses on match detail) so the table reads as *this
        // team's* roster, not a generic wall of names.
        columns={[
          { label: teamName || "Player" },
          { label: "Name" },
          { label: "Role" },
          { label: "Country", className: "w-20" },
        ]}
      >
        {players.map((m, i) => (
          <RosterRow key={m.playerId ?? `p-${i}`} m={m} />
        ))}
        {staff.length > 0 && (
          <>
            <tr>
              <td
                colSpan={4}
                className="!py-1.5 font-display text-[10px] font-semibold uppercase tracking-[0.16em] text-dim"
              >
                Staff
              </td>
            </tr>
            {staff.map((m, i) => (
              <RosterRow key={m.playerId ?? `s-${i}`} m={m} />
            ))}
          </>
        )}
      </TableShell>
      </div>}
    </section>
  );
}
