import type { ApiResponse, TeamTrend } from "@/types/vlr";
import { shouldRenderTrendLine } from "@/lib/vlr";

export function captureDate(value: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Date unavailable";
  return new Date(value).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}
const fmt = (value: number | null | undefined) => value == null ? "—" : Number.isInteger(value) ? String(value) : value.toFixed(1);

export function TeamTrendPanel({ trend }: { trend: ApiResponse<TeamTrend> }) {
  const t = trend.data[0];
  const points = t?.ratingTrend ?? [];
  const rated = points.filter(p => p.rating !== null);
  const dated = rated.filter(p => p.capturedAt && Number.isFinite(Date.parse(p.capturedAt)));
  const times = dated.map(p => Date.parse(p.capturedAt!));
  const distinctTimes = new Set(times).size;
  const chronological = dated.length === rated.length && distinctTimes >= 2;
  const hasLine = chronological && shouldRenderTrendLine(points);
  // Keep the API's delta; do not infer a change from a single snapshot.
  const change = rated.length >= 2 ? t?.ratingChange : null;
  const tone = change == null || change === 0 ? "flat" : change > 0 ? "up" : "down";
  const min = rated.length ? Math.min(...rated.map(p => p.rating!)) : 0;
  const max = rated.length ? Math.max(...rated.map(p => p.rating!)) : 0;
  const start = Math.min(...times), end = Math.max(...times);
  let penDown = false;
  const path = hasLine ? points.map(p => {
    if (p.rating === null || !p.capturedAt || !Number.isFinite(Date.parse(p.capturedAt))) { penDown = false; return ""; }
    const x = 8 + (Date.parse(p.capturedAt) - start) / (end - start) * 784;
    const y = 8 + (max - p.rating) / (max - min) * 144;
    const command = `${penDown ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`; penDown = true; return command;
  }).join(" ") : "";
  return <section aria-labelledby="team-rating">
    <div className="td-section-heading"><div><p className="td-kicker">02 / Banked history</p><h2 id="team-rating">Rating movement</h2></div><p>{t?.windowDays != null ? `${t.windowDays}-day lookback` : "Window unavailable"}</p></div>
    <div className="td-rating">
      {!t ? <p className="td-empty">{trend.stale || trend.error ? "Rating history unavailable — couldn't load this team's history." : "No rating history returned by the source."}</p> : <>
        {trend.stale && <p className="td-notice" role="status">History updates unavailable — showing last available data.</p>}
        <div className="td-rating-stats"><div><span>Latest captured rating</span><strong>{fmt(t.summary?.currentRating)}</strong></div><div><span>Change in window</span><strong data-tone={tone}>{change == null ? "—" : `${change > 0 ? "+" : ""}${fmt(change)}`}</strong></div><div><span>Peak in window</span><strong>{fmt(t.summary?.peakRating)}</strong></div><div><span>Window W / L</span><strong>{t.summary ? `${t.summary.wins} / ${t.summary.losses}` : "—"}</strong></div></div>
        <p className="td-caption">{rated.length} rated snapshots / {points.length} total captures. {dated.length ? `${captureDate(dated[0].capturedAt)} → ${captureDate(dated[dated.length - 1].capturedAt)}` : "Capture dates unavailable."}</p>
        {hasLine ? <figure className="td-chart" data-tone={tone}>
          <div className="td-chart-range"><span>{fmt(max)}</span><span>{fmt(min)}</span></div>
          <svg viewBox="0 0 800 160" preserveAspectRatio="none" role="img" aria-label={`Rating history: ${rated.length} snapshots, minimum ${fmt(min)}, maximum ${fmt(max)}. Exact captures in the table below.`}><path d={path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />{dated.map((p,i) => <circle key={i} cx={8+(times[i]-start)/(end-start)*784} cy={8+(max-p.rating!)/(max-min)*144} r="3" />)}</svg>
          <figcaption>Capture time → · range {fmt(min)}–{fmt(max)} (axis does not start at zero). Missing ratings are not interpolated.</figcaption>
        </figure> : <p className="td-empty">{rated.length === 0 ? "No rated snapshots in this window." : rated.length < 2 ? "One rated snapshot — not enough history to show movement." : !chronological ? "Capture dates are insufficient for a time-based chart." : "Rating held flat across this window — too little movement to chart."}</p>}
        {t.note && <p className="td-notice">Source note: {t.note}</p>}
        {points.length > 0 && <details className="td-history"><summary>View {points.length} rating captures</summary><p className="td-caption">Scroll horizontally to see all columns on smaller screens.</p><div className="td-table-scroll" tabIndex={0} role="region" aria-label="Rating capture history, scroll horizontally"><table className="td-table"><caption className="sr-only">Rating captures, chronological order; dates are capture times, not match dates</caption><thead><tr><th scope="col">Captured at (UTC)</th><th scope="col">Rating</th><th scope="col">Rank</th></tr></thead><tbody>{points.map((p,i) => <tr key={i}><th scope="row">{captureDate(p.capturedAt)}</th><td>{fmt(p.rating)}</td><td>{fmt(p.rank)}</td></tr>)}</tbody></table></div></details>}
      </>}
    </div>
  </section>;
}
