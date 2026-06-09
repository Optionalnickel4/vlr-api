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
function NewsRow({ article }: { article: NewsArticle }) {
  const { title, description, date, author, url } = article;

  const inner = (
    <div className="flex flex-col gap-1.5 px-4 py-3">
      <h3 className="font-display text-[15px] font-semibold uppercase tracking-[0.02em] leading-snug text-ink">
        {title ?? "—"}
      </h3>
      {description && (
        <p className="line-clamp-2 font-body text-[13px] leading-snug text-mut">
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

export function NewsPanel({ news }: { news: ApiResponse<NewsArticle> }) {
  const rows = news.data;

  return (
    <MatchSection
      title="News"
      count={rows.length}
      stale={news.stale}
      isEmpty={rows.length === 0}
      emptyLabel="No news right now."
    >
      {rows.map((a, i) => (
        <NewsRow key={a.url ?? `${a.title}-${i}`} article={a} />
      ))}
    </MatchSection>
  );
}
