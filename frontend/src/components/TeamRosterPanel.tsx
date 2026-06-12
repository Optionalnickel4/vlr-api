import type { RosterMember } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { TableShell } from "@/components/TableShell";
import { Badge } from "@/components/Badge";

/**
 * TeamRosterPanel — the active roster as a tight broadcast stat table: alias,
 * real name, role, country. Players come first, staff (coach / manager) sink to
 * the bottom under a dim divider so the five starters read at a glance. The
 * captain carries a small accent badge. Every alias links to that player's
 * vlr.gg page (internal player detail is a sibling slice).
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
          {m.url ? (
            <a href={m.url} target="_blank" rel="noopener noreferrer">
              {alias}
            </a>
          ) : (
            alias
          )}
          {m.isCaptain && (
            <Badge tone="accent" className="px-1.5 py-0">
              C
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
    <MatchSection
      title="Roster"
      count={players.length}
      isEmpty={roster.length === 0}
      emptyLabel="No roster listed."
    >
      <TableShell
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
    </MatchSection>
  );
}
