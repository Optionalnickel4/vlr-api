"""Isolated real API/parser/Redis/Postgres; VLR HTTP replaced with saved HTML."""
import os,asyncio,pathlib,json,time
B=pathlib.Path('/tmp/vlr-reliability')
os.environ.update(VLR_REDIS_URL='unix:///tmp/vlr-reliability/redis/redis.sock',VLR_DATABASE_URL='postgresql+asyncpg://builder@/postgres?host=/tmp/vlr-reliability/pg/socket&port=55432',VLR_ENABLE_SCHEDULER='false',VLR_BASE_URL='https://fixture.invalid')
import httpx,uvicorn
from app.main import app
from app.core import http as H,cache as C,db
from app.services import refresh as R
scenario=lambda:(B/'scenario').read_text().strip()
calls=[]
async def fixture(request):
 mode="hung" if request.url.path == "/9900" else scenario();calls.append({'path':request.url.path,'mode':mode,'at':time.time()})
 if mode=='slow':await asyncio.sleep(12)
 if mode=='hung':await asyncio.sleep(120)
 if mode=='missing':return httpx.Response(404)
 if mode=='failed':return httpx.Response(503)
 name='player_tenz.html' if request.url.path.startswith('/player/') else 'team_sentinels.html' if request.url.path.startswith('/team/') else 'match_detail_completed.html'
 return httpx.Response(200,text=pathlib.Path('/opt/vlr-api/tests/fixtures',name).read_text())
original_session=R.SessionLocal
class Session:
 def __init__(self,*a,**k):self.inner=original_session(*a,**k)
 async def __aenter__(self):
  if scenario()=='dbfailed':raise RuntimeError('CONTROLLED database outage')
  session=await self.inner.__aenter__()
  if scenario()=='dbslow':
   commit=session.commit
   async def delayed():await asyncio.sleep(12);return await commit()
   session.commit=delayed
  return session
 async def __aexit__(self,*args):return await self.inner.__aexit__(*args)
R.SessionLocal=Session
@app.post('/_audit/reset')
async def reset():
 assert C.get_settings().redis_url.startswith('unix:///tmp/vlr-reliability/')
 await C.get_redis().flushdb();calls.clear();return {'reset':'isolated Redis only'}
@app.get('/_audit/trace')
async def trace():return {'scenario':scenario(),'scrapes':calls}
async def main():
 await db.init_db()
 client=H.get_client();await client._client.aclose();client._client=httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(fixture))
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8102,lifespan='off',log_level='warning'))
 await server.serve()
asyncio.run(main())
