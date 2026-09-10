"""Arena: a 3D box the brain flies a Fly through. One tick() per Frame, lock-step with the brain."""
import json
import math
import queue
import struct

import numpy as np
import torch

from .model import Brain, Params

SIZE, H = 100.0, 50.0  # mm: square floor, ceiling height; origin bottom-left-floor
POSE = ["x", "y", "z", "th", "v", "vz"]
SENSE = ["orn_food_l", "orn_food_r", "jo_wind_l", "jo_wind_r", "r16_l", "r16_r", "bristle_l", "bristle_r", "sugar_grn"]
MOTOR = ["dnp09", "mdn", "dna02_l", "dna02_r", "dng02", "shiu_mn9", "neck_l", "neck_r", "antmn_l", "antmn_r"]
CHANNELS = dict(pose=POSE, sense=SENSE, motor=MOTOR)
TRAILER = f"<{len(POSE) + len(SENSE) + len(MOTOR)}fI"  # appended to each Frame: pose, sense Hz, motor EMA Hz, feeds
KINDS = dict(source=dict(z=25.0, amp=1.0, sigma=20.0), patch=dict(r=5.0), pillar=dict(r=5.0), light=dict(z=40.0, amp=1.0))
GAINS = dict(g_f=0.2, g_b=0.2, g_t=0.01, v_base=5.0, vmax=30.0, noise=1.0, g_lift=0.5, sink=2.0, body=1.0,
             r0=2.0, r_max=150.0, k=0.3, antenna=0.5, wind_v=10.0, g_wind=3.0, ambient=0.0, r_light=60.0,
             bristle_hz=100.0, mn9_thr=20.0)


class World:
    def __init__(self, brain: Brain, window_ms=10.0, seed=0):
        self.brain, self.window = brain, window_ms
        self.rate = torch.zeros(brain.n, device=brain.device)
        self.cnt = np.zeros(brain.n, dtype=np.float32)
        self.np_idx = {k: brain.pop(k) for k in SENSE + MOTOR}
        assert all(len(v) for v in self.np_idx.values()), "empty population"  # mean() of none is NaN
        self.idx = {k: torch.tensor(v, device=brain.device) for k, v in self.np_idx.items()}
        self.objs = {k: {} for k in KINDS}
        self.wind, self.gains = None, dict(GAINS)
        self.pokes, self.cmds, self.rec, self.events = [], queue.Queue(), None, []
        self.paused, self.dt, self.seed = False, brain.p.dt, seed
        self.reset()

    def reset(self, dt=None, seed=None):
        self.dt, self.seed = dt or self.dt, self.seed if seed is None else seed
        self.brain.p = Params(dt=self.dt)
        self.rate.zero_()
        self.gen = self.brain.frames(1e9, self.rate, self.window, self.seed)
        self.rng = np.random.default_rng(self.seed)
        self.pose = np.array([SIZE / 2, SIZE / 2, H / 2, 0.0])  # x, y, z mm; heading rad
        self.start = self.pose.copy()
        self.v = self.vz = 0.0
        self.ema = dict.fromkeys(MOTOR, 0.0)
        self.sense = dict.fromkeys(SENSE, 0.0)
        self.t, self.feeds, self.feeding, self.pokes = 0.0, 0, False, []

    # --- commands (drained on the brain thread, so world state has one writer) ---
    def apply(self, m):
        c = m.get("cmd")
        if c in KINDS:
            self.objs[c][m["id"]] = {**KINDS[c], **{k: float(m[k]) for k in ("x", "y", "z", "amp", "sigma", "r") if k in m}}
        elif c == "delete":
            self.objs[m["kind"]].pop(m["id"], None)
        elif c == "fly":
            for i, (k, hi) in enumerate([("x", SIZE), ("y", SIZE), ("z", H)]):
                if k in m: self.pose[i] = min(hi, max(0.0, m[k]))
            if "theta" in m: self.pose[3] = m["theta"]
            self.start = self.pose.copy()
            self.v = self.vz = 0.0
        elif c == "pause":
            self.paused = bool(m["on"])
        elif c == "reset":
            self.reset(m.get("dt"), m.get("seed"))
        elif c == "wind":
            self.wind = m.get("dir")
        elif c == "gains":
            self.gains.update({k: float(v) for k, v in m.items() if k in GAINS})
        elif c == "poke":
            ix = self.brain.pop(m["pop"]) if "pop" in m else np.asarray(m["idx"])
            self.pokes.append([torch.tensor(ix, device=self.brain.device), float(m["rate"]), max(1, round(m.get("ms", 100) / self.window))])
        elif c == "record":
            self.rec = [] if m["on"] else None
        elif c == "save":
            self.save(m["path"])
        self.events.append((self.t, m))

    def state(self):
        return dict(**self.objs, wind=self.wind, gains=self.gains, paused=self.paused, dt=self.dt, seed=self.seed,
                    t=self.t, feeds=self.feeds, start=self.start.tolist(), size=SIZE, height=H)

    # --- physics ---
    def conc(self, x, y, z):
        """Odor concentration at a point: sum of 3D Gaussian sources, stretched 3x downwind (horizontally) if wind is set."""
        c = 0.0
        for s in self.objs["source"].values():
            dx, dy, dz = x - s["x"], y - s["y"], z - s["z"]
            s2 = 2 * s["sigma"] ** 2
            if self.wind is None:
                c += s["amp"] * math.exp(-(dx * dx + dy * dy + dz * dz) / s2)
            else:
                u = dx * math.cos(self.wind) + dy * math.sin(self.wind)  # along-wind
                w = -dx * math.sin(self.wind) + dy * math.cos(self.wind)
                su = s["sigma"] * (3.0 if u > 0 else 1.0)
                c += s["amp"] * math.exp(-(u * u / (2 * su * su) + (w * w + dz * dz) / s2))
        return c

    def tick(self):
        """Advance one Frame. Returns the wire bytes (Frame + TRAILER) or None when paused."""
        while not self.cmds.empty():
            self.apply(self.cmds.get_nowait())
        if self.paused:
            return None
        G, e, S = self.gains, self.ema, self.sense
        t, idx, c = next(self.gen)
        self.t = t
        cnt = self.cnt
        cnt[idx] = c
        a = 1 - math.exp(-self.window / 50.0)
        for k in MOTOR:
            e[k] += a * (float(cnt[self.np_idx[k]].mean()) * 1000 / self.window - e[k])
        cnt[idx] = 0
        # Motor Map: DNp09/MDN thrust, DNa02 L-R yaw, DNg02 lift against a constant sink.
        v = min(G["vmax"], max(0.0, G["v_base"] + G["g_f"] * e["dnp09"] - G["g_b"] * e["mdn"]))
        w = G["g_t"] * (e["dna02_l"] - e["dna02_r"]) + G["noise"] * self.rng.standard_normal()
        vz = G["g_lift"] * e["dng02"] - G["sink"]
        dt = self.window / 1000.0
        x, y, z, th = map(float, self.pose)
        th += w * dt
        hx, hy = math.cos(th), math.sin(th)
        x, y, z = x + v * hx * dt, y + v * hy * dt, z + vz * dt
        contact = []  # directions fly -> obstacle; None = head-on (both sides)
        for i, lo, hi in [(0, (-1, 0), (1, 0)), (1, (0, -1), (0, 1))]:
            p = (x, y)[i]
            if p < 0: contact.append(lo)
            if p > SIZE: contact.append(hi)
        x, y = min(SIZE, max(0.0, x)), min(SIZE, max(0.0, y))
        if z > H: z, _ = H, contact.append(None)
        z = max(0.0, z)  # floor = landing, not a touch
        for p in self.objs["pillar"].values():
            dx, dy, R = x - p["x"], y - p["y"], p["r"] + G["body"]
            d = math.hypot(dx, dy)
            if d < R:
                x, y = p["x"] + dx / max(d, 1e-6) * R, p["y"] + dy / max(d, 1e-6) * R
                contact.append((-dx, -dy))
        cross = [None if c is None else hx * c[1] - hy * c[0] for c in contact]
        bl, br = any(s is None or s >= 0 for s in cross), any(s is None or s <= 0 for s in cross)
        landed = z == 0.0
        self.pose[:] = x, y, z, th
        self.v, self.vz = v, vz
        # Sense: antennae smell and feel airflow, eyes see the light, bristles touch, proboscis tastes when landed.
        d = G["antenna"]
        cl = self.conc(x + d * math.cos(th + 0.52), y + d * math.sin(th + 0.52), z)
        cr = self.conc(x + d * math.cos(th - 0.52), y + d * math.sin(th - 0.52), z)
        S["orn_food_l"], S["orn_food_r"] = (G["r0"] + G["r_max"] * cc / (cc + G["k"]) for cc in (cl, cr))
        wx, wy = (G["wind_v"] * math.cos(self.wind), G["wind_v"] * math.sin(self.wind)) if self.wind is not None else (0.0, 0.0)
        ax, ay = wx - v * hx, wy - v * hy  # air velocity relative to the fly
        an, side = math.hypot(ax, ay), -ax * hy + ay * hx  # airflow component toward the left
        S["jo_wind_l"], S["jo_wind_r"] = G["g_wind"] * (an - side) / 2, G["g_wind"] * (an + side) / 2
        S["r16_l"] = S["r16_r"] = G["ambient"]
        for L in self.objs["light"].values():
            lx, ly, lz = L["x"] - x, L["y"] - y, L["z"] - z
            ln = math.hypot(lx, ly, lz) or 1.0
            for k, sgn in (("r16_l", 1), ("r16_r", -1)):
                S[k] += G["r_light"] * L["amp"] * max(0.0, (math.cos(th + sgn * math.pi / 3) * lx + math.sin(th + sgn * math.pi / 3) * ly) / ln)
        S["bristle_l"], S["bristle_r"] = G["bristle_hz"] * bl, G["bristle_hz"] * br
        on = landed and any((x - p["x"]) ** 2 + (y - p["y"]) ** 2 < p["r"] ** 2 for p in self.objs["patch"].values())
        S["sugar_grn"] = 150.0 * on
        self.rate.zero_()
        for k in SENSE:
            self.rate[self.idx[k]] = S[k]
        feeding = on and e["shiu_mn9"] > G["mn9_thr"]
        self.feeds += feeding and not self.feeding  # rising edge
        self.feeding = feeding
        for p in self.pokes:
            self.rate[p[0]] += p[1]
            p[2] -= 1
        self.pokes = [p for p in self.pokes if p[2] > 0]
        trail = [x, y, z, th, v, vz, *(S[k] for k in SENSE), *(e[k] for k in MOTOR)]
        buf = pack_frame(t, idx, c) + struct.pack(TRAILER, *trail, self.feeds)
        if self.rec is not None:
            self.rec.append((t, idx, c, trail, self.feeds))
        return buf

    def save(self, path):
        """Trial recording: Frames + trailer per Frame + the command log, replayable without a GPU."""
        r = self.rec or []
        np.savez_compressed(path, t=np.array([f[0] for f in r]), idx=np.concatenate([f[1] for f in r] or [np.zeros(0, np.uint32)]),
                            counts=np.concatenate([f[2] for f in r] or [np.zeros(0, np.uint16)]),
                            offsets=np.cumsum([0] + [len(f[1]) for f in r]), trail=np.array([f[3] for f in r]).reshape(-1, len(POSE) + len(SENSE) + len(MOTOR)),
                            feeds=np.array([f[4] for f in r]), events=json.dumps(self.events), state=json.dumps(self.state()))


def pack_frame(t, idx, c):
    return struct.pack("<fI", t, len(idx)) + idx.astype(np.uint32).tobytes() + c.astype(np.uint16).tobytes()
