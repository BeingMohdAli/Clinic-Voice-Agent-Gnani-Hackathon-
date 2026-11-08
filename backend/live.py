"""Live console: a second browser window that shows the call as it happens.

The agent POSTs small events (what the caller said, what the agent said, which API it called).
Open http://localhost:8000/live in another window to watch them. Demo only: fake data, no login.
"""
import asyncio
import json
import time
from collections import deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse

_history = deque(maxlen=300)
_listeners: set = set()


def make_router(require_key) -> APIRouter:
    router = APIRouter()

    @router.post("/events", dependencies=[Depends(require_key)], include_in_schema=False)
    async def post_event(request: Request):
        try:
            data = await request.json()
        except Exception:
            return {"ok": False}
        event = {
            "t": time.strftime("%H:%M:%S"),
            "kind": str(data.get("kind", "info"))[:20],
            "text": str(data.get("text", ""))[:600],
        }
        _history.append(event)
        for q in list(_listeners):
            q.put_nowait(event)
        return {"ok": True}

    @router.get("/live/stream", include_in_schema=False)
    async def stream():
        q: asyncio.Queue = asyncio.Queue()
        _listeners.add(q)

        async def gen():
            try:
                for e in list(_history):
                    yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
                while True:
                    try:
                        e = await asyncio.wait_for(q.get(), timeout=15)
                        yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
            finally:
                _listeners.discard(q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @router.get("/live", response_class=HTMLResponse, include_in_schema=False)
    async def page():
        return LIVE_HTML

    return router


LIVE_HTML = """<!doctype html>
<html lang="hi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Live Call Console</title>
<style>
 :root{--bg:#0e1116;--card:#171b22;--text:#e8ecf1;--mute:#8b96a5;--user:#2f81f7;--agent:#2ea043;--api:#d29922;--sys:#a371f7}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,"Segoe UI",sans-serif}
 header{padding:14px 20px;border-bottom:1px solid #262c36;display:flex;gap:12px;align-items:center;justify-content:space-between}
 h1{font-size:16px;margin:0} .sub{color:var(--mute);font-size:13px}
 #dot{width:10px;height:10px;border-radius:50%;background:#555;display:inline-block;margin-right:6px}
 .on #dot{background:var(--agent)} button{background:#262c36;color:var(--text);border:0;border-radius:6px;padding:6px 12px;cursor:pointer}
 main{max-width:820px;margin:0 auto;padding:16px 16px 80px}
 .row{display:flex;gap:10px;margin:10px 0}.row.user{justify-content:flex-end}
 .bubble{max-width:78%;padding:10px 14px;border-radius:14px;background:var(--card);white-space:pre-wrap;word-break:break-word}
 .user .bubble{background:#12294d;border:1px solid var(--user)} .agent .bubble{background:#12301b;border:1px solid var(--agent)}
 .who{font-size:12px;color:var(--mute);margin-bottom:2px}
 .small{align-items:center;justify-content:center}
 .small .bubble{max-width:95%;background:transparent;border:1px dashed #3a4350;color:var(--mute);font:13px ui-monospace,Consolas,monospace;padding:5px 10px}
 .api .bubble{border-color:var(--api);color:var(--api)} .sys .bubble{border-color:var(--sys);color:var(--sys)}
 #empty{color:var(--mute);text-align:center;margin-top:80px}
</style></head><body>
<header><div><h1>Live Call Console</h1><div class="sub">Clinic voice agent &middot; Gnani Prisma + Timbre &middot; fake data only</div></div>
<div><span id="st"><span id="dot"></span><span id="stt">connecting...</span></span> <button onclick="clearAll()">Clear</button></div></header>
<main id="log"><div id="empty">Waiting for a call... start one in the other window.</div></main>
<script>
const log=document.getElementById('log');
function add(e){
  const empty=document.getElementById('empty'); if(empty) empty.remove();
  const k=e.kind, row=document.createElement('div');
  if(k==='user'||k==='agent'){
    row.className='row '+k;
    row.innerHTML='<div><div class="who"></div><div class="bubble"></div></div>';
    row.querySelector('.who').textContent=(k==='user'?'Caller':'Agent')+' \\u00b7 '+e.t;
    row.querySelector('.bubble').textContent=e.text;
  } else {
    row.className='row small '+(k==='api'?'api':'sys');
    row.innerHTML='<div class="bubble"></div>';
    row.querySelector('.bubble').textContent=e.t+'  '+e.text;
  }
  const nearBottom=innerHeight+scrollY>=document.body.scrollHeight-120;
  log.appendChild(row);
  if(nearBottom) scrollTo(0,document.body.scrollHeight);
}
function clearAll(){log.innerHTML='';}
const es=new EventSource('/live/stream');
es.onopen=()=>{document.getElementById('st').className='on';document.getElementById('stt').textContent='live';};
es.onerror=()=>{document.getElementById('st').className='';document.getElementById('stt').textContent='reconnecting...';};
es.onmessage=ev=>add(JSON.parse(ev.data));
</script></body></html>
"""
