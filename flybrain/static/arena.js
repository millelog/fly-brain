// 2D top-down arena: renders World state + per-Frame pose, sends commands for sources, patches and the fly.
let send, cv, ctx, hud;
let state = { sources: {}, patches: {}, size: 100, start: [50, 50, 0], gains: {} };
let fly = { x: 50, y: 50, th: 0, dnp09: 0, mdn: 0, dna02_l: 0, dna02_r: 0, mn9: 0, feeds: 0 }, bioT = 0;
const trail = [];
let sel = null, drag = null; // sel = {kind, id}; drag = {kind, id, dx, dy} or {kind:'heading'}
let nextId = Date.now();

export function init(o) {
  send = o.send; cv = o.canvas; ctx = cv.getContext('2d'); hud = document.getElementById('hud');
  addEventListener('resize', resize); resize();
  cv.oncontextmenu = e => e.preventDefault();
  cv.onpointerdown = down; cv.onpointermove = move; cv.onpointerup = up;
  addEventListener('keydown', e => { if ((e.key === 'Delete' || e.key === 'Backspace') && sel && document.activeElement.tagName !== 'INPUT') { send({ cmd: 'delete', kind: sel.kind, id: sel.id }); sel = null; } });
  requestAnimationFrame(draw);
}
export function resize() { cv.width = cv.clientWidth * devicePixelRatio; cv.height = cv.clientHeight * devicePixelRatio; }
export function setState(s) { state = { ...state, ...s }; }
export function onFrame(t, f) { bioT = t; fly = f; trail.push(f.x, f.y); if (trail.length > 1200) trail.splice(0, 2); }

// world (mm, y up) <-> canvas px
function scale() { return Math.min(cv.width, cv.height) / state.size; }
function ox() { return (cv.width - state.size * scale()) / 2; }
function oy() { return (cv.height - state.size * scale()) / 2; }
function toPx(x, y) { const s = scale(); return [ox() + x * s, oy() + (state.size - y) * s]; }
function toMm(e) { const r = cv.getBoundingClientRect(), s = scale(); return [((e.clientX - r.left) * devicePixelRatio - ox()) / s, state.size - ((e.clientY - r.top) * devicePixelRatio - oy()) / s]; }

function hit(x, y) {
  if (Math.hypot(x - fly.x, y - fly.y) < 3) return { kind: 'fly' };
  for (const [id, p] of Object.entries(state.patches)) if (Math.hypot(x - p.x, y - p.y) < p.r) return { kind: 'patch', id };
  for (const [id, s] of Object.entries(state.sources)) if (Math.hypot(x - s.x, y - s.y) < 4) return { kind: 'source', id };
  return null;
}
function down(e) {
  cv.setPointerCapture(e.pointerId);
  const [x, y] = toMm(e), h = hit(x, y);
  if (h?.kind === 'fly' && e.button === 2) { drag = { kind: 'heading' }; return; }
  if (h) { sel = h.kind === 'fly' ? null : h; const o = h.kind === 'fly' ? fly : (h.kind === 'patch' ? state.patches : state.sources)[h.id]; drag = { ...h, dx: o.x - x, dy: o.y - y }; return; }
  if (e.button !== 0) return;
  const id = String(nextId++);
  if (e.shiftKey || document.getElementById('place').value === 'patch') { state.patches[id] = { x, y, r: 5 }; send({ cmd: 'patch', id, x, y }); sel = { kind: 'patch', id }; }
  else { state.sources[id] = { x, y, amp: 1, sigma: 20 }; send({ cmd: 'source', id, x, y }); sel = { kind: 'source', id }; }
}
function move(e) {
  if (!drag) return;
  const [x, y] = toMm(e);
  if (drag.kind === 'heading') { fly.th = Math.atan2(y - fly.y, x - fly.x); send({ cmd: 'fly', theta: fly.th }); return; }
  const nx = Math.max(0, Math.min(state.size, x + drag.dx)), ny = Math.max(0, Math.min(state.size, y + drag.dy));
  if (drag.kind === 'fly') { fly.x = nx; fly.y = ny; send({ cmd: 'fly', x: nx, y: ny }); }
  else { const o = (drag.kind === 'patch' ? state.patches : state.sources)[drag.id]; if (!o) return; o.x = nx; o.y = ny; send({ cmd: drag.kind, id: drag.id, ...o }); }
}
function up() { drag = null; }

function draw() {
  requestAnimationFrame(draw);
  const W = cv.width, H = cv.height, s = scale();
  ctx.fillStyle = '#05060a'; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#0e1220'; ctx.fillRect(ox(), oy(), state.size * s, state.size * s);
  ctx.strokeStyle = '#2a3145'; ctx.lineWidth = devicePixelRatio; ctx.strokeRect(ox(), oy(), state.size * s, state.size * s);
  // Odor: radial gradients (stretched downwind when wind is set).
  for (const [id, src] of Object.entries(state.sources)) {
    const [px, py] = toPx(src.x, src.y), r = src.sigma * 2 * s;
    ctx.save(); ctx.translate(px, py);
    if (state.wind != null) { ctx.rotate(-state.wind); ctx.translate(r * 0.6, 0); ctx.scale(1.8, 1); }
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
    g.addColorStop(0, `rgba(250,204,21,${0.3 * src.amp})`); g.addColorStop(1, 'rgba(250,204,21,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fill(); ctx.restore();
    ctx.strokeStyle = sel?.id === id ? '#fff' : '#facc15'; ctx.lineWidth = 2 * devicePixelRatio; ctx.beginPath(); ctx.arc(px, py, 5 * devicePixelRatio, 0, 7); ctx.stroke();
  }
  for (const [id, p] of Object.entries(state.patches)) {
    const [px, py] = toPx(p.x, p.y);
    ctx.fillStyle = 'rgba(74,222,128,.25)'; ctx.strokeStyle = sel?.id === id ? '#fff' : '#4ade80'; ctx.lineWidth = 1.5 * devicePixelRatio;
    ctx.beginPath(); ctx.arc(px, py, p.r * s, 0, 7); ctx.fill(); ctx.stroke();
  }
  if (state.wind != null) { // wind arrow, top-left of the arena
    const [ax, ay] = toPx(8, state.size - 8), L = 6 * s;
    ctx.strokeStyle = '#8b93a7'; ctx.lineWidth = 2 * devicePixelRatio; ctx.beginPath(); ctx.moveTo(ax - L * Math.cos(state.wind), ay + L * Math.sin(state.wind)); ctx.lineTo(ax + L * Math.cos(state.wind), ay - L * Math.sin(state.wind)); ctx.stroke();
    ctx.fillStyle = '#8b93a7'; ctx.beginPath(); ctx.arc(ax + L * Math.cos(state.wind), ay - L * Math.sin(state.wind), 3 * devicePixelRatio, 0, 7); ctx.fill();
  }
  // Trail, start marker, fly.
  ctx.strokeStyle = 'rgba(125,211,252,.35)'; ctx.lineWidth = devicePixelRatio; ctx.beginPath();
  for (let i = 0; i < trail.length; i += 2) { const [px, py] = toPx(trail[i], trail[i + 1]); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
  ctx.stroke();
  const [sx, sy] = toPx(state.start[0], state.start[1]); ctx.strokeStyle = '#334155'; ctx.beginPath(); ctx.arc(sx, sy, 3 * devicePixelRatio, 0, 7); ctx.stroke();
  const [fx, fy] = toPx(fly.x, fly.y), a = fly.th, R = Math.max(2.5 * s, 8 * devicePixelRatio);
  ctx.fillStyle = fly.mn9 > (state.gains.mn9_thr ?? 20) ? '#4ade80' : '#7dd3fc';
  ctx.beginPath(); ctx.moveTo(fx + R * Math.cos(a), fy - R * Math.sin(a)); ctx.lineTo(fx + R * .7 * Math.cos(a + 2.5), fy - R * .7 * Math.sin(a + 2.5)); ctx.lineTo(fx + R * .7 * Math.cos(a - 2.5), fy - R * .7 * Math.sin(a - 2.5)); ctx.closePath(); ctx.fill();
  const d = (state.gains.antenna ?? .5) * s; // antennae as two dots, brighter on the side smelling more
  for (const [k, sgn] of [['dna02_l', 1], ['dna02_r', -1]]) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(fx + Math.max(d, R) * Math.cos(a + sgn * .52), fy - Math.max(d, R) * Math.sin(a + sgn * .52), 2 * devicePixelRatio, 0, 7); ctx.fill(); }
  // HUD: clock, DN rates, feeds, chemotaxis index toward the nearest source.
  let idx = '—';
  const srcs = Object.values(state.sources);
  if (srcs.length) { const near = p => Math.min(...srcs.map(o => Math.hypot(p[0] - o.x, p[1] - o.y))); const d0 = near(state.start); idx = d0 > 0 ? ((d0 - near([fly.x, fly.y])) / d0).toFixed(2) : '—'; }
  hud.textContent = `bio ${(bioT / 1000).toFixed(2)} s · feeds ${fly.feeds} · index ${idx}\nDNp09 ${fly.dnp09.toFixed(0)} · MDN ${fly.mdn.toFixed(0)} · DNa02 L ${fly.dna02_l.toFixed(0)} R ${fly.dna02_r.toFixed(0)} · MN9 ${fly.mn9.toFixed(0)} Hz`;
}
