import { cn } from "@/lib/cn";
import type { ApiResponse, NewsArticle } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";

/**
 * NewsPanel — the headline feed as a stack of broadcast lower-thirds.
 *
 * The headline is rendered from `title` ONLY; date + author come from the
 * already-split `meta` (see normalizeNews) and live in a separate dim footer.
 * Keeping them apart is the label-bleed guard — the timestamp/author must never
 * ride along inside the headline text (the test asserts this invariant).
 */
function NewsRow({ article, lead = false }: { article: NewsArticle; lead?: boolean }) {
  const { title, description, date, author, url } = article;

  const inner = (
    <div className={cn("flex flex-col px-4", lead ? "gap-3 border-l-2 border-accent py-6" : "gap-1.5 py-3")}>
      {lead && <p className="text-sm font-medium text-accent">Latest headline</p>}
      <h3 className={cn("font-display font-semibold tracking-[0.02em] leading-snug text-ink", lead ? "text-2xl normal-case" : "text-[15px] uppercase")}>
        {title ?? "—"}
      </h3>
      {description && (
        <p className={cn("line-clamp-2 font-body text-mut", lead ? "text-sm leading-relaxed" : "text-[13px] leading-snug")}>
          {description}
        </p>
      )}
      {(date || author) && (
        <div className="flex items-center gap-2 font-display text-[11px] uppercase tracking-[0.1em] text-dim">
          {date && <span>{date}</span>}
          {date && author && <span aria-hidden>·</span>}
          {author && <span>{author}</span>}
        </div>
      )}
    </div>
  );

  const shell =
    "block border-b border-line/60 last:border-b-0 transition-colors hover:bg-ink/[0.03]";

  return url ? (
    <a href={url} target="_blank" rel="noopener noreferrer" className={shell}>
      {inner}
    </a>
  ) : (
    <div className={shell}>{inner}</div>
  );
}

// Landing teaser shows this many items; full /news page shows all.
const NEWS_TEASER_LIMIT = 5;

export function NewsPanel({
  news,
  viewAllHref,
  viewAllLabel,
  leadStory = false,
}: {
  news: ApiResponse<NewsArticle>;
  viewAllHref?: string;
  viewAllLabel?: string;
  leadStory?: boolean;
}) {
  const allRows = news.data;
  // viewAllHref present ↔ landing teaser — cap rows so the panel stays scannable.
  const rows = viewAllHref ? allRows.slice(0, NEWS_TEASER_LIMIT) : allRows;

  if (leadStory) return <section className="bc-news" aria-labelledby="news-heading">
    <div className="bc-news-heading"><span className="bc-kicker">Beyond the score</span><h2 id="news-heading">THE LATEST.</h2><span className="sr-only">News</span></div>
    {(news.stale || news.error) && <p role="status" className="bc-news-warning">Updates unavailable.</p>}
    {!rows.length && !news.stale && !news.error && <p className="bc-empty">No news right now.</p>}
    {rows.map((article, i) => <article className={i === 0 ? "bc-story bc-story-lead" : "bc-story"} key={article.url ?? i}>
      {i === 0 && <span className="bc-kicker">Latest headline</span>}
      <h3>{article.url ? <a href={article.url} target="_blank" rel="noopener noreferrer">{article.title ?? "Untitled article"}<span className="sr-only"> (opens in a new tab)</span></a> : article.title ?? "Untitled article"}</h3>
      {i === 0 && article.description && <p>{article.description}</p>}
      {(article.date || article.author) && <div className="bc-story-meta">{[article.date, article.author].filter(Boolean).join(" · ")}</div>}
    </article>)}
    <a className="bc-section-link" href={viewAllHref ?? "/news"}>{viewAllLabel ?? "All news"} <span aria-hidden>↗</span></a>
  </section>;
  return (
    <MatchSection
      title="News"
      count={allRows.length}
      stale={news.stale || Boolean(news.error)}
      isEmpty={allRows.length === 0}
      emptyLabel="No news right now."
      viewAllHref={viewAllHref}
      viewAllLabel={viewAllLabel}
    >
      {rows.map((a, i) => (
        <NewsRow key={a.url ?? `${a.title}-${i}`} article={a} lead={leadStory && i === 0} />
      ))}
    </MatchSection>
  );
}
