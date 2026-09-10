"""FastAPI server: serves the viewer, neuron metadata, and streams Frames over a WebSocket."""
import asyncio
import struct
import threading
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from . import data, populations
from .model import Brain, Params

app = FastAPI()
STATIC = Path(__file__).parent / "static"
brain: Brain | None = None


@app.on_event("startup")
def load():
    global brain
    brain = Brain()
    print(f"brain ready on {brain.device}: {brain.n} neurons")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/positions")
def positions():
    """float32 (N,3) soma xyz in nm, NaN where unknown."""
    return Response(data.soma_xyz(brain.neurons).tobytes(), media_type="application/octet-stream")


@app.get("/api/meta")
def meta():
    xyz = data.soma_xyz(brain.neurons)
    return {
        "n": brain.n, "device": str(brain.device), "no_soma": int(np.isnan(xyz[:, 0]).sum()),
        "super_class": brain.neurons["super_class"].fillna("unknown").tolist(),
        "populations": {k: brain.pop(k).tolist() for k in populations.REGISTRY},
    }


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    loop, q, stop = asyncio.get_event_loop(), asyncio.Queue(maxsize=64), threading.Event()

    def run(cfg):
        p = Params(dt=cfg.get("dt", 0.1))
        b = Brain.__new__(Brain); b.__dict__.update(brain.__dict__); b.p = p  # share weights, own params
        for t, idx, c in b.frames(cfg.get("duration", 1e9), cfg.get("stimuli", {}), cfg.get("window", 10.0)):
            if stop.is_set():
                break
            buf = struct.pack("<fI", t, len(idx)) + idx.astype(np.uint32).tobytes() + c.astype(np.uint16).tobytes()
            asyncio.run_coroutine_threadsafe(q.put(buf), loop).result()
        asyncio.run_coroutine_threadsafe(q.put(None), loop)

    async def pump():
        while (buf := await q.get()) is not None:
            await sock.send_bytes(buf)
        await sock.send_text('{"done": true}')

    worker = pumper = None
    try:
        while True:
            msg = await sock.receive_json()
            if msg.get("cmd") == "start":
                stop.set()
                if worker: worker.join()
                stop.clear()
                worker = threading.Thread(target=run, args=(msg,), daemon=True); worker.start()
                pumper = asyncio.create_task(pump())
            elif msg.get("cmd") == "stop":
                stop.set()
    except WebSocketDisconnect:
        stop.set()
