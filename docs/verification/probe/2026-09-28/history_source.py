import asyncio, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select, text
from app.core.db import SessionLocal, engine
from app.models import PlayerSnapshot
from app.services.trends import build_player_response

async def main():
 async with SessionLocal() as session:
  await session.execute(text('SET TRANSACTION READ ONLY'))
  await session.execute(text("SET LOCAL statement_timeout = '10s'"))
  snaps=(await session.execute(select(PlayerSnapshot).where(PlayerSnapshot.player_id=='36245').order_by(PlayerSnapshot.captured_at.desc()).limit(1000))).scalars().all()
 rows=[{'captured_at':s.captured_at,'alias':s.alias,'team':s.team,'agent_stats':s.agent_stats} for s in snaps]
 cutoff=datetime.now(timezone.utc)-timedelta(days=90)
 result=build_player_response('36245',90,rows,cutoff)
 report={'player_id':'36245','transaction':'READ ONLY','row_limit':1000,'rows_read':len(rows),'within_window':sum(r['captured_at']>=cutoff for r in rows),'source_points':len(result['rating_trend']),'source_summary':result['summary'],'newest_capture':max(s.captured_at for s in snaps).isoformat()}
 print(json.dumps(report))
 Path('docs/verification/probe/2026-09-28/history-source.json').write_text(json.dumps(report,indent=2)+'\n')
 await engine.dispose()
asyncio.run(main())
