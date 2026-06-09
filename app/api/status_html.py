"""Phase 6 status dashboard — the HTML half.

One self-contained string: inline CSS, no build step, no CDN required to function
(the Saira Condensed webfont is a progressive enhancement with a system fallback;
the page is fully legible without it). The static half (header, tiles, phases) is
rendered server-side so it shows with JS off; a little vanilla JS fetches
`/api/v1/status` to fill the live half, degrading to a clear notice on failure.

Aesthetic: valstats broadcast — dark, condensed display type, green = up/fresh,
red = down/stale. Not a generic ops page.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app import status_meta as meta

router = APIRouter()


def _phase_rows() -> str:
    out = []
    for p in meta.PHASES:
        cls = "on" if p["shipped"] else "off"
        mark = "●" if p["shipped"] else "○"
        out.append(
            f'<li class="phase {cls}">'
            f'<span class="pn">{p["n"]:02d}</span>'
            f'<span class="pname">{p["name"]}</span>'
            f'<span class="pdesc">{p["desc"]}</span>'
            f'<span class="pmark">{mark}</span>'
            f"</li>"
        )
    return "\n".join(out)


def render_status_page() -> str:
    shipped = sum(1 for p in meta.PHASES if p["shipped"])
    total = len(meta.PHASES)
    tiles = (
        f'<div class="tile"><div class="tv">{shipped}<span class="td">/{total}</span></div>'
        f'<div class="tl">phases shipped</div></div>'
        f'<div class="tile"><div class="tv">{meta.TESTS_PASSING}</div>'
        f'<div class="tl">tests passing</div></div>'
        f'<div class="tile"><div class="tv">{len(meta.HISTORY_TABLES)}</div>'
        f'<div class="tl">history tables</div></div>'
    )
    html = _TEMPLATE
    html = html.replace("__COMMIT__", meta.COMMIT)
    html = html.replace("__LXC__", str(meta.DEPLOY["lxc"]))
    html = html.replace("__HOST__", str(meta.DEPLOY["host"]))
    html = html.replace("__TILES__", tiles)
    html = html.replace("__PHASES__", _phase_rows())
    return html


@router.get("/status", response_class=HTMLResponse)
async def status_page() -> HTMLResponse:
    return HTMLResponse(render_status_page())


@router.get("/", response_class=HTMLResponse)
async def root_page() -> HTMLResponse:
    return HTMLResponse(render_status_page())


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vlr-api · status</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@400;600;700&family=Saira:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0a0d12; --panel:#11161f; --panel2:#0d1219; --line:#1d2735;
    --ink:#e8eef6; --mut:#7c8aa0; --dim:#566273;
    --up:#22d37a; --down:#ff4d5e; --warn:#ffb02e; --accent:#2de1c2;
    --display:'Saira Condensed','Oswald','Arial Narrow',system-ui,sans-serif;
    --body:'Saira',system-ui,'Segoe UI',sans-serif;
    --mono:'JetBrains Mono',ui-monospace,'SF Mono',Menlo,monospace;
  }
  *{box-sizing:border-box}
  body{margin:0;background:
      radial-gradient(1200px 500px at 80% -10%,#13202b 0,transparent 60%),
      linear-gradient(#0a0d12,#080a0e);
    color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.45;
    -webkit-font-smoothing:antialiased;min-height:100vh}
  .wrap{max-width:1040px;margin:0 auto;padding:28px 22px 60px}
  a{color:var(--accent);text-decoration:none}

  /* header */
  header{display:flex;flex-wrap:wrap;align-items:flex-end;gap:14px 22px;
    border-bottom:1px solid var(--line);padding-bottom:18px}
  .brand{font-family:var(--display);font-weight:700;letter-spacing:.04em;
    font-size:44px;line-height:.9;text-transform:uppercase}
  .brand .dot{color:var(--accent)}
  .tagline{color:var(--mut);font-family:var(--display);font-weight:600;
    letter-spacing:.18em;text-transform:uppercase;font-size:13px;margin-top:4px}
  .meta{margin-left:auto;text-align:right;font-family:var(--mono);font-size:12px;
    color:var(--mut)}
  .meta b{color:var(--ink);font-weight:500}
  .live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;
    background:var(--dim);margin-right:6px;vertical-align:middle;
    box-shadow:0 0 0 0 rgba(34,211,122,.5)}
  .live-dot.up{background:var(--up);animation:pulse 2s infinite}
  .live-dot.down{background:var(--down)}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,211,122,.5)}
    70%{box-shadow:0 0 0 7px rgba(34,211,122,0)}100%{box-shadow:0 0 0 0 rgba(34,211,122,0)}}

  /* section heading */
  h2{font-family:var(--display);font-weight:600;letter-spacing:.16em;
    text-transform:uppercase;font-size:13px;color:var(--mut);
    margin:34px 0 12px;display:flex;align-items:center;gap:10px}
  h2::after{content:"";flex:1;height:1px;background:var(--line)}

  /* tiles */
  .tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}
  .tile{background:linear-gradient(var(--panel),var(--panel2));
    border:1px solid var(--line);border-radius:10px;padding:16px 18px}
  .tile .tv{font-family:var(--display);font-weight:700;font-size:40px;line-height:1;
    color:var(--ink)}
  .tile .td{font-size:22px;color:var(--dim)}
  .tile .tl{font-family:var(--display);letter-spacing:.14em;text-transform:uppercase;
    font-size:11px;color:var(--mut);margin-top:6px}

  /* phases */
  ul.phases{list-style:none;margin:0;padding:0;border:1px solid var(--line);
    border-radius:10px;overflow:hidden;background:var(--panel2)}
  li.phase{display:grid;grid-template-columns:46px 160px 1fr 24px;align-items:center;
    gap:14px;padding:11px 16px;border-top:1px solid var(--line)}
  li.phase:first-child{border-top:none}
  .pn{font-family:var(--mono);color:var(--dim);font-size:13px}
  .pname{font-family:var(--display);font-weight:600;letter-spacing:.04em;
    text-transform:uppercase;font-size:16px}
  .pdesc{color:var(--mut);font-size:13.5px}
  .pmark{text-align:right;font-size:14px}
  .phase.on .pmark{color:var(--up)}
  .phase.off .pmark{color:var(--dim)}
  .phase.off .pname{color:var(--mut)}

  /* live status */
  .cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  @media(max-width:720px){.cards{grid-template-columns:1fr}.tiles{grid-template-columns:1fr}
    li.phase{grid-template-columns:34px 1fr 20px}.pdesc{display:none}}
  .card{background:var(--panel2);border:1px solid var(--line);border-radius:10px;
    padding:14px 16px}
  .card h3{margin:0 0 10px;font-family:var(--display);font-weight:600;
    letter-spacing:.14em;text-transform:uppercase;font-size:12px;color:var(--mut)}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  td,th{text-align:left;padding:6px 4px;border-top:1px solid var(--line)}
  tr:first-child td,tr:first-child th{border-top:none}
  th{color:var(--dim);font-weight:500;font-family:var(--display);letter-spacing:.08em;
    text-transform:uppercase;font-size:11px}
  td.k{color:var(--ink);font-family:var(--mono);font-size:12.5px}
  td.num{font-family:var(--mono);text-align:right;color:var(--ink)}
  td.age{text-align:right;color:var(--mut);font-size:12.5px;white-space:nowrap}
  .pill{display:inline-flex;align-items:center;gap:7px;font-family:var(--display);
    font-weight:600;letter-spacing:.1em;text-transform:uppercase;font-size:12px;
    padding:5px 11px;border-radius:999px;border:1px solid var(--line)}
  .pill .b{width:8px;height:8px;border-radius:50%;background:var(--dim)}
  .pill.up{color:var(--up);border-color:rgba(34,211,122,.35);background:rgba(34,211,122,.07)}
  .pill.up .b{background:var(--up)}
  .pill.down{color:var(--down);border-color:rgba(255,77,94,.35);background:rgba(255,77,94,.07)}
  .pill.down .b{background:var(--down)}
  .checks{display:flex;gap:10px}
  .fresh{color:var(--up)} .stale{color:var(--down)} .none{color:var(--dim)}
  .notice{border:1px solid var(--down);background:rgba(255,77,94,.08);color:#ffd2d6;
    border-radius:10px;padding:12px 16px;font-size:13.5px}
  .loading{color:var(--mut);font-style:italic;padding:4px 2px}
  footer{margin-top:40px;color:var(--dim);font-size:12px;font-family:var(--mono);
    display:flex;gap:16px;flex-wrap:wrap}
  .refresh{cursor:pointer;background:none;border:1px solid var(--line);color:var(--mut);
    font-family:var(--display);letter-spacing:.1em;text-transform:uppercase;font-size:11px;
    padding:5px 12px;border-radius:6px}
  .refresh:hover{border-color:var(--accent);color:var(--accent)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="brand">VLR<span class="dot">·</span>API</div>
      <div class="tagline">self-hosted vlr.gg · status</div>
    </div>
    <div class="meta">
      <div><span id="livedot" class="live-dot"></span><b id="livelabel">live status loading…</b></div>
      <div>deploy <b>LXC __LXC__</b> · <b>__HOST__</b></div>
      <div>commit <b>__COMMIT__</b></div>
    </div>
  </header>

  <div class="tiles">__TILES__</div>

  <h2>phases</h2>
  <ul class="phases">__PHASES__</ul>

  <h2>live status <button class="refresh" onclick="loadStatus()">refresh</button></h2>
  <div id="live">
    <div class="loading">loading live status…</div>
  </div>

  <footer>
    <span>read-only · reads cache + db, never scrapes</span>
    <span><a href="/api/v1/status">/api/v1/status</a></span>
  </footer>
</div>

<script>
function ago(iso){
  if(!iso) return null;
  var t = Date.parse(iso); if(isNaN(t)) return null;
  var s = Math.round((Date.now()-t)/1000);
  if(s < 0) s = 0;
  if(s < 60) return s+"s ago";
  var m = Math.floor(s/60), h = Math.floor(m/60), d = Math.floor(h/24);
  if(m < 60) return m+"m ago";
  if(h < 24) return h+"h "+(m%60)+"m ago";
  return d+"d "+(h%24)+"h ago";
}
function until(iso){
  if(!iso) return null;
  var s = Math.round((Date.parse(iso)-Date.now())/1000);
  if(isNaN(s)) return null;
  if(s <= 0) return "due";
  var m = Math.floor(s/60), h = Math.floor(m/60);
  if(s < 60) return "in "+s+"s";
  if(m < 60) return "in "+m+"m";
  return "in "+h+"h "+(m%60)+"m";
}
function esc(x){return String(x).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
function freshClass(iso, staleSecs){
  if(!iso) return "none";
  var s = (Date.now()-Date.parse(iso))/1000;
  return s > staleSecs ? "stale" : "fresh";
}

function render(d){
  var pg = d.checks.postgres, rd = d.checks.redis;
  document.getElementById("livedot").className = "live-dot " + ((pg&&rd)?"up":"down");
  document.getElementById("livelabel").textContent = (pg&&rd) ? "all systems up" : "degraded";

  var checks = '<div class="card"><h3>backend</h3><div class="checks">'
    + '<span class="pill '+(pg?'up':'down')+'"><span class="b"></span>postgres '+(pg?'up':'down')+'</span>'
    + '<span class="pill '+(rd?'up':'down')+'"><span class="b"></span>redis '+(rd?'up':'down')+'</span>'
    + '</div></div>';

  var hrows = d.history.map(function(h){
    var rows = (h.rows===null||h.rows===undefined) ? '<span class="none">n/a</span>' : h.rows;
    var a = ago(h.newest);
    var cls = freshClass(h.newest, 86400);
    return '<tr><td class="k">'+esc(h.table)+'</td><td class="num">'+rows+'</td>'
      + '<td class="age '+cls+'">'+(a?esc(a):'—')+'</td></tr>';
  }).join('');
  var hist = '<div class="card"><h3>history tables</h3><table>'
    + '<tr><th>table</th><th style="text-align:right">rows</th><th style="text-align:right">newest</th></tr>'
    + hrows + '</table></div>';

  var crows = d.cache_keys.map(function(c){
    var warm = c.ttl===null||c.ttl===undefined;
    var ttl = warm ? '<span class="none">cold</span>'
      : '<span class="fresh">'+c.ttl+'s</span>';
    return '<tr><td class="k">'+esc(c.key)+'</td><td class="num">'+ttl+'</td></tr>';
  }).join('');
  var cache = '<div class="card"><h3>cache keys (ttl)</h3><table>'
    + '<tr><th>key</th><th style="text-align:right">ttl</th></tr>'+crows+'</table></div>';

  var srows = d.scheduler.map(function(s){
    var last = ago(s.last_run);
    var lcls = freshClass(s.last_run, 21600);
    var nxt = until(s.next_run);
    return '<tr><td class="k">'+esc(s.job)+'</td>'
      + '<td class="age '+lcls+'">'+(last?esc(last):'<span class="none">never</span>')+'</td>'
      + '<td class="age">'+(nxt?esc(nxt):'<span class="none">—</span>')+'</td></tr>';
  }).join('');
  var sched = '<div class="card"><h3>scheduler</h3><table>'
    + '<tr><th>job</th><th style="text-align:right">last run</th><th style="text-align:right">next run</th></tr>'
    + srows + '</table></div>';

  document.getElementById("live").innerHTML =
    '<div class="cards">'+checks+hist+cache+sched+'</div>';
}

function loadStatus(){
  fetch("/api/v1/status", {headers:{"accept":"application/json"}})
    .then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
    .then(render)
    .catch(function(){
      document.getElementById("livedot").className = "live-dot down";
      document.getElementById("livelabel").textContent = "live status unavailable";
      document.getElementById("live").innerHTML =
        '<div class="notice">live status unavailable — could not reach '
        + '<code>/api/v1/status</code>. Static project info above is still accurate.</div>';
    });
}
loadStatus();
</script>
</body>
</html>"""
