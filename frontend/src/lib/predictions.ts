import type { MatchPrediction, PredictionTeam } from "@/types/predictions";

type Raw = Record<string, unknown>;
const object = (v: unknown): Raw | null => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Raw : null;
const text = (v: unknown): string | null => typeof v === "string" && v.trim() ? v.trim() : null;
const id = (v: unknown): string | null => typeof v === "string" && /^\d{1,32}$/.test(v) ? v : null;
const strings = (v: unknown): string[] => Array.isArray(v) ? v.filter((s): s is string => typeof s === "string" && Boolean(s.trim())) : [];
const date = (v: unknown): string | null => typeof v === "string" && /(?:Z|[+-]\d\d:\d\d)$/.test(v) && Number.isFinite(Date.parse(v)) ? v : null;

/** Unknown winners or malformed evidence become pending, never invented picks. */
export function normalizePredictions(raw: unknown): MatchPrediction[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap(value => {
    const row = object(value), matchId = id(object(value)?.match_id);
    if (!row || !matchId || !Array.isArray(row.teams) || row.teams.length !== 2) return [];
    const teams = row.teams.map(value => {
      const team = object(value), logo = text(object(value)?.logo);
      return { id: id(team?.id), name: text(team?.name) ?? "TBD", logo: logo && /^https?:\/\//.test(logo) ? logo : null };
    }) as [PredictionTeam, PredictionTeam];
    // Keep undetermined fixtures off the Predictions page, including its counts.
    if (teams.some(team => /^(tbd|tba|unknown|to be (determined|announced)|\?)$/i.test(team.name))) return [];
    const facts = Array.isArray(row.facts) ? row.facts.flatMap(value => {
      const fact = object(value), factId = text(object(value)?.id), teamId = id(object(value)?.team_id), copy = text(object(value)?.text);
      return fact && factId && teamId && copy && teams.some(t => t.id === teamId)
        ? [{ id: factId, teamId, text: copy, sourceUrl: `https://www.vlr.gg/team/${teamId}` }] : [];
    }) : [];
    const answer = object(row.prediction), winnerId = id(object(row.prediction)?.winner_id);
    const explanation = text(answer?.explanation), evidenceIds = strings(answer?.evidence_ids), caveats = strings(answer?.caveats);
    const startsAt = date(row.starts_at), generatedAt = date(row.generated_at);
    const published = row.status === "published" && winnerId && teams.some(t => t.id === winnerId);
    const noPick = row.status === "no_pick" && answer?.winner_id === null;
    const valid = Boolean((published || noPick) && explanation && caveats.length && evidenceIds.length >= 2
      && startsAt && generatedAt && Date.parse(generatedAt) < Date.parse(startsAt)
      && evidenceIds.every(ref => facts.some(f => f.id === ref))
      && teams.every(t => evidenceIds.some(ref => facts.some(f => f.id === ref && f.teamId === t.id))));
    return [{ matchId, teams, event: text(row.event), timing: text(row.timing), startsAt, generatedAt: valid ? generatedAt : null,
      status: valid ? (noPick ? "no_pick" : "published") : "pending",
      prediction: valid ? { winnerId, explanation: explanation!, evidenceIds, caveats } : null,
      facts: valid ? facts : [], limitations: valid ? strings(row.limitations) : [] } satisfies MatchPrediction];
  });
}
