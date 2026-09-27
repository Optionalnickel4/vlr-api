import { parseEtaOffsetMs } from "./schedule";

/** Only a complete duration is a safe input for approximate day grouping.
 * Bare clocks, partial text and unknown formats remain explicitly undated. */
export function listingDay(raw: string | null, direction: 1 | -1, now: Date, stale = false) {
  const unknown = { key: "unknown", label: "Date unavailable" };
  if (stale || !raw || !/^(?:\d+\s*(?:mo|w|d|h|m|s)\s*)+$/i.test(raw.trim())) return unknown;
  const offset = parseEtaOffsetMs(raw);
  if (offset === null) return unknown;
  const date = new Date(now.getTime() + direction * offset);
  if (!Number.isFinite(date.getTime())) return unknown;
  const key = date.toISOString().slice(0, 10);
  const diff = Math.floor(date.getTime() / 86400000) - Math.floor(now.getTime() / 86400000);
  const relative = diff === 0 ? "Today · " : diff === 1 ? "Tomorrow · " : diff === -1 ? "Yesterday · " : "";
  return { key, label: relative + new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric" }).format(date) };
}

/** Group contiguous rows only: flattening groups reproduces the input exactly. */
export function groupListing<T extends { event: string | null }>(matches: T[], timing: (m: T) => string | null, direction: 1 | -1, now: Date, stale = false) {
  const groups: { key: string; day: ReturnType<typeof listingDay>; event: string | null; matches: T[] }[] = [];
  for (const match of matches) {
    const day = listingDay(timing(match), direction, now, stale);
    const key = JSON.stringify([day.key, match.event]);
    let group = groups[groups.length - 1];
    if (!group || group.key !== key) {
      group = { key, day, event: match.event, matches: [] };
      groups.push(group);
    }
    group.matches.push(match);
  }
  return groups;
}
