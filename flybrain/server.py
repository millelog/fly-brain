"""FastAPI server: serves the viewer, neuron metadata, and streams the shared World (or a replay) to every socket."""
import asyncio
import json
import os
import queue
import struct
import threading
import time
from pathlib import Path

import numpy as np
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import data, populations
from .model import Brain
from .world import TRAILER, World, pack_frame

app = FastAPI()
STATIC = Path(__file__).parent / "static"
brain: Brain | None = None
world: World | None = None
replay = None  # dict of npz arrays when REPLAY=file.npz
sockets: dict[WebSocket, asyncio.Queue] = {}
loop: asyncio.AbstractEventLoop | None = None


def push(msg):
    """Fan out one message to every socket; drop the oldest when a viewer is slow. Runs on the event loop thread."""
    for q in sockets.values():
        if q.full():
            q.get_nowait()
        q.put_nowait(msg)


def run_world():
    last_state = 0.0
    while True:
        n_cmd = world.cmds.qsize()
        buf = world.tick()
        if buf is not None:
            loop.call_soon_threadsafe(push, buf)
        if n_cmd or time.time() - last_state > 1.0:
            loop.call_soon_threadsafe(push, json.dumps(world.state()))
            last_state = time.time()
        if buf is None:
            time.sleep(0.02)


def run_replay():
    """Stream recorded Frames at ~real time; `seek` commands move the cursor."""
    r, k, cmds = replay, 0, world_cmds
    n = len(r["t"])
    ev = json.loads(str(r["events"])); state = json.loads(str(r["state"]))
    while True:
        while not cmds.empty():
            m = cmds.get_nowait()
            if m.get("cmd") == "seek":
                k = max(0, min(n - 1, int(m["frame"])))
        if n == 0:
            time.sleep(0.1); continue
        a, b = r["offsets"][k], r["offsets"][k + 1]
        buf = pack_frame(float(r["t"][k]), r["idx"][a:b], r["counts"][a:b]) + struct.pack(TRAILER, *r["pose"][k], *r["ema"][k], int(r["feeds"][k]))
        loop.call_soon_threadsafe(push, buf)
        if k % 100 == 0:
            st = dict(state, t=float(r["t"][k]), frames=n, frame=k)
            loop.call_soon_threadsafe(push, json.dumps(st))
        k = (k + 1) % n
        time.sleep(0.01)


@app.on_event("startup")
def load():
    global brain, world, replay, loop, world_cmds
    loop = asyncio.get_event_loop()
    brain = Brain()
    print(f"brain ready on {brain.device}: {brain.n} neurons")
    if os.environ.get("REPLAY"):
        replay = dict(np.load(os.environ["REPLAY"]))
        world_cmds = queue.Queue()
        threading.Thread(target=run_replay, daemon=True).start()
    else:
        world = World(brain)
        world_cmds = world.cmds
        threading.Thread(target=run_world, daemon=True).start()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/positions")
def positions():
    """float32 (N,3) soma xyz in µm, NaN where unknown."""
    return Response(data.soma_xyz(brain.neurons).tobytes(), media_type="application/octet-stream")


@app.get("/api/meta")
def meta():
    xyz = data.soma_xyz(brain.neurons)
    return {
        "n": brain.n, "device": str(brain.device), "no_soma": int(np.isnan(xyz[:, 0]).sum()), "replay": replay is not None,
        "super_class": brain.neurons["super_class"].fillna("unknown").tolist(),
        "populations": {k: brain.pop(k).tolist() for k in populations.REGISTRY},
    }


@app.get("/api/neuron/{i}")
def neuron(i: int, limit: int = 200):
    """Annotation row plus strongest synaptic partners: out = [[post, w]], in = [[pre, w]]."""
    if not hasattr(brain, "rev"):
        brain.rev = data.reverse_csr(brain.ptr, brain.post, brain.w)
    row = brain.neurons.iloc[i][["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "side", "top_nt", "flow"]]
    def top(ptr, nbr, w):
        a, b = int(ptr[i]), int(ptr[i + 1])
        ww, nn = w[a:b], nbr[a:b]
        o = torch.argsort(ww.abs(), descending=True)[:limit]
        return [[int(j), round(float(x), 3)] for j, x in zip(nn[o].tolist(), ww[o].tolist())]
    return {**{k: (None if (isinstance(v, float) and np.isnan(v)) else (str(v) if k == "root_id" else v)) for k, v in row.items()},
            "out": top(brain.ptr, brain.post, brain.w), "in": top(*brain.rev), "n_out": int(brain.ptr[i + 1] - brain.ptr[i]),
            "n_in": int(brain.rev[0][i + 1] - brain.rev[0][i])}


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    q = sockets[sock] = asyncio.Queue(maxsize=8)
    if world is not None:
        await sock.send_text(json.dumps(world.state()))

    async def pump():
        while True:
            m = await q.get()
            await (sock.send_bytes(m) if isinstance(m, bytes) else sock.send_text(m))

    task = asyncio.create_task(pump())
    try:
        while True:
            world_cmds.put(await sock.receive_json())
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        sockets.pop(sock, None)
