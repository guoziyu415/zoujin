"""Run backend's real s1b proxy with a fake Live client and serve the S2 page. Container test only: no model calls,
no cloud, binds to 127.0.0.1. Usage (deps: google-genai, fastapi, uvicorn, as in backend/spikes/pyproject.toml):

  PYTHONDONTWRITEBYTECODE=1 python fake_serve.py [port]       # then open http://127.0.0.1:8091/ , code TEST-TEST-TEST
  FAKE_PACE=0.13 ...                                           # downlink slower than real time, to see underrunCount
"""
import asyncio, math, os, struct, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.gettempdir()) / "s2-fake"
os.environ.setdefault("ZJ_PROJECT", "fake-project")
os.environ.setdefault("ZJ_OUT", str(TMP / "out"))
os.environ.setdefault("ZJ_LEDGER", str(TMP / "ledger.json"))
os.environ.setdefault("ZJ_S1B_SECRET_DIR", str(TMP / "secret"))
os.environ.setdefault("ZJ_BUDGET_USD", "1000")
os.environ.setdefault("ZJ_S1B_MAX_USD", "500")
sys.path.insert(0, str(HERE.parents[3] / "backend" / "spikes"))   # s2-voice/test -> app-team, then backend/spikes/zj_spike
from google.genai import types
from zj_spike import s1b_proxy as P

HEARD = ["こんばんは。この町、なんだか静かですね。", "王様は、どんな方ですか。", "どうして皆さん、黙っているんですか。"]
PACE = float(os.environ.get("FAKE_PACE", "0.04"))   # seconds between 100 ms chunks; above 0.1 the downlink is slower than real time
SAY = "旅の人か。この町は、王が人を殺すので、皆おびえているのだ。"

def msg(**sc):
    return types.LiveServerMessage(server_content=types.LiveServerContent(**sc))

class FakeSession:
    def __init__(self):
        self.q = asyncio.Queue(); self.reply = None; self.n = 0; self.up = 0
    async def send_realtime_input(self, activity_start=None, activity_end=None, audio=None):
        if activity_start is not None:
            if self.reply and not self.reply.done():
                self.reply.cancel(); await self.q.put(msg(interrupted=True))
            self.up = 0
        elif activity_end is not None:
            self.reply = asyncio.create_task(self._reply(voice=True))
        elif audio is not None:
            self.up += len(audio.data)
    async def send_client_content(self, turns=None, turn_complete=True):
        if self.reply and not self.reply.done():
            self.reply.cancel(); await self.q.put(msg(interrupted=True))
        self.reply = asyncio.create_task(self._reply(voice=False))
    async def _reply(self, voice):
        self.n += 1; n = self.n
        heard = HEARD[(n - 1) % len(HEARD)]
        late = voice and n % 3 == 0        # every third turn: the player's text arrives after turn_complete
        await asyncio.sleep(0.25)
        if voice and not late:
            await self.q.put(msg(input_transcription=types.Transcription(text=heard[:6])))
            await self.q.put(msg(input_transcription=types.Transcription(text=heard[6:])))
        await asyncio.sleep(0.35)
        rate, secs, f = 24000, 2.4, 220.0
        total = int(rate * secs); step = 2400   # 100 ms chunks, sent every 40 ms (faster than real time, like Live)
        for i0 in range(0, total, step):
            pcm = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * f * (i / rate)))) for i in range(i0, min(total, i0 + step)))
            await self.q.put(msg(model_turn=types.Content(role="model", parts=[types.Part(inline_data=types.Blob(data=pcm, mime_type="audio/pcm;rate=24000"))])))
            if i0 == step * 3:
                await self.q.put(msg(output_transcription=types.Transcription(text=SAY[:10])))
            await asyncio.sleep(PACE)
        await self.q.put(msg(output_transcription=types.Transcription(text=SAY[10:])))
        await self.q.put(msg(turn_complete=True))
        if late:
            await asyncio.sleep(0.4)
            await self.q.put(msg(input_transcription=types.Transcription(text=heard)))
    async def receive(self):
        while True:
            m = await self.q.get()
            yield m
            if m.server_content and m.server_content.turn_complete:
                return

class _CM:
    async def __aenter__(self):
        await asyncio.sleep(0.3); return FakeSession()
    async def __aexit__(self, *a): return False

class FakeClient:
    class aio:
        class live:
            @staticmethod
            def connect(model=None, config=None): return _CM()

if __name__ == "__main__":
    import uvicorn
    code = os.environ.get("S2_FAKE_CODE", "TEST-TEST-TEST")
    hub = P.Hub(P.hash_code(code), client_factory=FakeClient, log_path=TMP / "out" / "serve.jsonl")
    app = P.create_app(hub, HERE.parent / "page")
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8091, log_level="warning", access_log=False)
