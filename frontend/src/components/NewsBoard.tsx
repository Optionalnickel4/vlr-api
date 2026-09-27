import type { ApiResponse, NewsArticle } from "@/types/vlr";

function StoryMeta({ article }: { article: NewsArticle }) {
  return <div className="nw-meta"><span>{article.date ?? "Date unavailable"}</span><span>{article.author ? `By ${article.author}` : "Author unavailable"}</span></div>;
}

function StoryTitle({ article }: { article: NewsArticle }) {
  return article.url ? <a className="nw-story-link" href={article.url} target="_blank" rel="noopener noreferrer"><h2>{article.title ?? "Untitled article"}</h2><span className="nw-destination">Read original story <span aria-hidden>↗</span></span><span className="sr-only"> (opens in a new tab)</span></a> : <><h2>{article.title ?? "Untitled article"}</h2><p className="nw-destination">Source link unavailable</p></>;
}

/** A headline directory, not a mirror of the source's article text.
 * The first supplied row leads; all remaining rows keep their original order.
 * No image field exists in NewsArticle. Descriptions remain in the API but are
 * deliberately not reproduced on this full-feed surface. */
export function NewsBoard({ news }: { news: ApiResponse<NewsArticle> }) {
  const [lead, ...rest] = news.data;
  const unavailable = news.stale || Boolean(news.error);
  return <div className="news-board">
    <header className="nw-masthead">
      <div><p className="nw-kicker">Valorant / News desk</p><h1>Beyond the score<span>.</span></h1><p className="nw-deck">Headlines from VLR.gg</p></div>
      <div className="nw-source"><strong>{unavailable && !news.data.length ? "—" : news.data.length}</strong><span>supplied stories</span><p>Read the original reporting at the source.</p></div>
    </header>
    {unavailable && <p className="nw-notice" role="status">{lead ? "Updates unavailable — showing last available stories in source order." : "News unavailable — could not load the story feed."}</p>}
    {!lead && !unavailable && <p className="nw-notice">No news right now.</p>}
    {lead && <article className="nw-lead">
      <div className="nw-lead-label"><span className="nw-kicker">Lead story</span><span>First in the supplied feed</span></div>
      <div className="nw-lead-body"><StoryMeta article={lead}/><StoryTitle article={lead}/></div>
    </article>}
    {rest.length > 0 && <section className="nw-feed" aria-labelledby="news-feed-title">
      <div className="nw-feed-heading"><h2 id="news-feed-title">More headlines</h2><p>Source order · {rest.length} stories</p></div>
      <ol className="nw-stories" start={2}>{rest.map((article,i)=><li key={`${article.url}-${i}`}><article className="nw-story"><span className="nw-index" aria-hidden>{String(i+2).padStart(2,"0")}</span><div><StoryMeta article={article}/><StoryTitle article={article}/></div></article></li>)}</ol>
    </section>}
    <footer className="nw-footer"><span>Reporting, dates and bylines supplied by VLR.gg. Feed capture time unavailable.</span><a href="https://www.vlr.gg/news" target="_blank" rel="noopener noreferrer">Visit VLR news <span aria-hidden>↗</span><span className="sr-only"> (opens in a new tab)</span></a></footer>
  </div>;
}
