// 3D arena: a three.js box world with a fly whose body parts are bound to Populations; sends commands for objects and the fly.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = id => document.getElementById(id);
const COLOR = { source: 0xfacc15, patch: 0x4ade80, pillar: 0x475569, light: 0xfff2b0 };
let send, highlight, cv, hud, tip, strip, renderer, scene, camera, controls, CH, NAMES;
let state = { source: {}, patch: {}, pillar: {}, light: {}, size: 100, height: 50, start: [50, 50, 25, 0], gains: {}, wind: null };
let fly = {}, bioT = 0, wallT = 0, phase = 0;              // fly = latest trailer values by channel name
let sel = null, drag = null, p0 = { x: 0, y: 0 }, downPart = null, hover = null, nextId = Date.now();
const objs = new Map(), handles = [], parts = [];        // objs: 'kind:id' -> Object3D; handles/parts: raycast targets
let flyG, body, head, antL, antR, prob, legs = [], wingL, wingR, trail, trailN = 0, floor, windArrow;
const ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), hit3 = new THREE.Vector3();
let sbuf, sp = 0;                                        // channel strip ring: C rows x 200 Frames (2 s bio)

export function init(o) {
  send = o.send; highlight = o.highlight; cv = o.canvas; CH = o.meta.channels; NAMES = [...CH.sense, ...CH.motor];
  hud = $('hud'); tip = $('tip'); strip = $('strip'); sbuf = new Float32Array(NAMES.length * 200);
  strip.style.height = 12 * NAMES.length + 'px';
  renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true }); renderer.setPixelRatio(devicePixelRatio);
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x05060a);
  camera = new THREE.PerspectiveCamera(50, 1, 0.1, 2000); camera.up.set(0, 0, 1); camera.position.set(50, -90, 70);
  controls = new OrbitControls(camera, cv); controls.target.set(50, 50, 10);
  scene.add(new THREE.AmbientLight(0x8090a0, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5); sun.position.set(-30, -60, 100); scene.add(sun);
  buildArena(); buildFly();
  addEventListener('resize', resize); resize();
  cv.oncontextmenu = e => e.preventDefault();
  cv.addEventListener('pointerdown', down, true);        // capture phase: runs before OrbitControls' own listener
  cv.onpointermove = move; cv.onpointerup = up;
  addEventListener('keydown', e => { if ((e.key === 'Delete' || e.key === 'Backspace') && sel && document.activeElement.tagName !== 'INPUT') { send({ cmd: 'delete', kind: sel.kind, id: sel.id }); delete state[sel.kind][sel.id]; sel = null; setState({}); } });
  $('selz').onchange = () => { if (!sel) return; if (sel.kind === 'fly') send({ cmd: 'fly', z: +$('selz').value }); else { const o = state[sel.kind][sel.id]; o.z = +$('selz').value; send({ cmd: sel.kind, id: sel.id, ...o }); } };
  $('chase').onchange = () => controls.enabled = !$('chase').checked;
  requestAnimationFrame(draw);
}
export function resize() { renderer.setSize(cv.clientWidth, cv.clientHeight, false); camera.aspect = cv.clientWidth / cv.clientHeight; camera.updateProjectionMatrix(); }
export function onFrame(t, f) {
  bioT = t; fly = f;
  NAMES.forEach((k, i) => sbuf[i * 200 + sp] = f[k]); sp = (sp + 1) % 200;
  trail.geometry.attributes.position.array.copyWithin(3, 0); trail.geometry.attributes.position.set([f.x, f.y, f.z], 0);
  trail.geometry.attributes.position.needsUpdate = true; trailN = Math.min(600, trailN + 1); trail.geometry.setDrawRange(0, trailN);
}
export function setState(s) {
  state = { ...state, ...s };
  const seen = new Set();
  for (const kind in COLOR) for (const [id, o] of Object.entries(state[kind] || {})) {
    const key = kind + ':' + id; seen.add(key);
    let g = objs.get(key); if (!g) { g = makeObj(kind, id); objs.set(key, g); scene.add(g); }
    g.position.set(o.x, o.y, o.z ?? (kind === 'patch' ? 0.03 : state.height / 2));
    if (kind === 'source') g.children[1].scale.set(4 * o.sigma, 4 * o.sigma, 1);
    if (kind === 'patch') g.scale.set(o.r, o.r, 1);
    if (kind === 'pillar') g.scale.set(o.r, 1, o.r);
  }
  for (const [key, g] of objs) if (!seen.has(key)) { scene.remove(g); objs.delete(key); handles.splice(handles.indexOf(g.userData.handle), 1); }
  windArrow.visible = state.wind != null; if (windArrow.visible) windArrow.setDirection(new THREE.Vector3(Math.cos(state.wind), Math.sin(state.wind), 0));
  if (sel && sel.kind !== 'fly' && !state[sel.kind]?.[sel.id]) sel = null;
  $('selz').value = sel ? (sel.kind === 'fly' ? fly.z : state[sel.kind][sel.id].z ?? 0).toFixed(1) : ''; $('selz').disabled = !sel || sel.kind === 'patch' || sel.kind === 'pillar';
}

// --- scene ---
function buildArena() {
  const S = state.size, H = state.height;
  floor = new THREE.Mesh(new THREE.PlaneGeometry(S, S), new THREE.MeshLambertMaterial({ color: 0x0e1220 })); floor.position.set(S / 2, S / 2, 0); scene.add(floor);
  const grid = new THREE.GridHelper(S, 10, 0x2a3145, 0x1a1f2e); grid.rotation.x = Math.PI / 2; grid.position.set(S / 2, S / 2, 0.02); scene.add(grid);
  const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(S, S, H)), new THREE.LineBasicMaterial({ color: 0x2a3145 })); box.position.set(S / 2, S / 2, H / 2); scene.add(box);
  windArrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(8, S - 8, H / 2), 10, 0x8b93a7); windArrow.visible = false; scene.add(windArrow);
  const start = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.6, 24), new THREE.MeshBasicMaterial({ color: 0x334155, side: THREE.DoubleSide })); start.name = 'start'; scene.add(start);
  trail = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(600 * 3), 3)), new THREE.LineBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: .4 }));
  trail.geometry.setDrawRange(0, 0); trail.frustumCulled = false; scene.add(trail);
}
const gradient = (() => { const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'), r = g.createRadialGradient(64, 64, 0, 64, 64, 64); r.addColorStop(0, 'rgba(250,204,21,1)'); r.addColorStop(1, 'rgba(250,204,21,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c); })();
function makeObj(kind, id) {
  const g = new THREE.Group(); let h;
  if (kind === 'source') {
    h = new THREE.Mesh(new THREE.SphereGeometry(1.5, 12, 8), new THREE.MeshBasicMaterial({ color: COLOR.source }));
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: gradient, blending: THREE.AdditiveBlending, depthWrite: false, opacity: .3, transparent: true })); s.raycast = () => {}; g.add(h, s);
  } else if (kind === 'patch') { h = new THREE.Mesh(new THREE.CircleGeometry(1, 32), new THREE.MeshBasicMaterial({ color: COLOR.patch, transparent: true, opacity: .35 })); g.add(h); }
  else if (kind === 'pillar') { h = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, state.height, 24), new THREE.MeshLambertMaterial({ color: COLOR.pillar })); h.rotation.x = Math.PI / 2; g.add(h); }
  else { h = new THREE.Mesh(new THREE.SphereGeometry(2, 12, 8), new THREE.MeshBasicMaterial({ color: COLOR.light })); g.add(h, new THREE.PointLight(COLOR.light, 2000, 300)); }
  h.userData = { kind, id }; g.userData.handle = h; handles.push(h);
  return g;
}
function part(geo, color, pops, name, opts = {}) {
  const m = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color, ...opts })); m.userData = { kind: 'fly', part: name, pops }; parts.push(m); return m;
}
function buildFly() {
  flyG = new THREE.Group(); flyG.scale.setScalar(2); flyG.rotation.order = 'ZYX';  // a real fly is 3 mm; 6 mm reads in a 100 mm box
  body = part(new THREE.SphereGeometry(1, 16, 12), 0x6b4a2b, [], 'body'); body.scale.set(1.5, .6, .5); flyG.add(body);
  head = new THREE.Group(); head.position.set(1.6, 0, .2); flyG.add(head);
  head.add(part(new THREE.SphereGeometry(.45, 12, 8), 0x7a5533, ['neck_l', 'neck_r'], 'head'));
  for (const s of [1, -1]) {
    const eye = part(new THREE.SphereGeometry(.28, 10, 8), 0xb3261e, [s > 0 ? 'r16_l' : 'r16_r'], s > 0 ? 'left eye' : 'right eye'); eye.position.set(.3, s * .4, .15); head.add(eye);
    const br = part(new THREE.SphereGeometry(.12, 6, 4), 0x3a2a1a, [s > 0 ? 'bristle_l' : 'bristle_r'], s > 0 ? 'left bristles' : 'right bristles'); br.position.set(0, s * .5, .35); head.add(br);
    const ant = part(new THREE.CylinderGeometry(.05, .05, .8).translate(0, .4, 0), 0x3a2a1a, s > 0 ? ['orn_food_l', 'jo_wind_l', 'antmn_l'] : ['orn_food_r', 'jo_wind_r', 'antmn_r'], s > 0 ? 'left antenna' : 'right antenna');
    ant.position.set(.5, s * .2, .1); ant.rotation.z = -Math.PI / 2 + s * .52; head.add(ant); if (s > 0) antL = ant; else antR = ant;
    const wing = part(new THREE.PlaneGeometry(.8, 2.2).translate(-.2, 1.1, 0), 0xcfe8ff, ['dng02', s > 0 ? 'dna02_l' : 'dna02_r'], s > 0 ? 'left wing' : 'right wing', { transparent: true, opacity: .35, side: THREE.DoubleSide });
    wing.position.set(-.2, s * .3, .5); flyG.add(wing); if (s > 0) wingL = wing; else wingR = wing;
    for (const x of [.6, 0, -.6]) { const leg = part(new THREE.CylinderGeometry(.04, .04, 1).translate(0, -.5, 0), 0x3a2a1a, ['dnp09', 'mdn'], 'legs'); leg.position.set(x, s * .5, -.2); leg.rotation.x = Math.PI / 2 + s * .5; flyG.add(leg); legs.push(leg); }
  }
  prob = part(new THREE.CylinderGeometry(.12, .08, 1).translate(0, -.5, 0), 0x8a6a4a, ['shiu_mn9', 'sugar_grn'], 'proboscis'); prob.position.set(.3, 0, -.3); prob.rotation.x = Math.PI / 2; head.add(prob);
  scene.add(flyG);
}

// --- input: click places, drag moves (controls off), right-drag fly = heading, hover/click a part = its Populations ---
function cast(e, list) { const r = cv.getBoundingClientRect(); ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera); return list ? ray.intersectObjects(list, false)[0] : null; }
function onPlane(e, z) { cast(e); plane.constant = -z; return ray.ray.intersectPlane(plane, hit3); }
function down(e) {
  p0 = { x: e.clientX, y: e.clientY }; downPart = null;
  const h = cast(e, [...parts, ...handles]); if (!h) return;
  const u = h.object.userData;
  if (u.kind === 'fly') { downPart = u; drag = e.button === 2 ? { kind: 'heading' } : { kind: 'fly', z: fly.z || 0, dx: fly.x - h.point.x, dy: fly.y - h.point.y }; }
  else if (e.button === 0) { const o = state[u.kind][u.id]; sel = { kind: u.kind, id: u.id }; drag = { ...sel, z: o.z ?? 0, dx: o.x - h.point.x, dy: o.y - h.point.y }; setState({}); }
  if (drag) { controls.enabled = false; cv.setPointerCapture(e.pointerId); e.stopImmediatePropagation(); }
}
function move(e) {
  if (!drag) {
    const h = cast(e, parts); hover = h ? h.object.userData : null; tip.hidden = !hover;
    if (hover) { tip.style.left = e.clientX + 14 + 'px'; tip.style.top = e.clientY + 14 + 'px'; tip.textContent = hover.part + '\n' + hover.pops.map(p => `${p} ${(fly[p] ?? 0).toFixed(0)} Hz`).join('\n'); }
    return;
  }
  const p = onPlane(e, drag.z || 0); if (!p) return;
  const S = state.size, nx = Math.max(0, Math.min(S, p.x + (drag.dx || 0))), ny = Math.max(0, Math.min(S, p.y + (drag.dy || 0)));
  if (drag.kind === 'heading') { fly.th = Math.atan2(p.y - fly.y, p.x - fly.x); send({ cmd: 'fly', theta: fly.th }); }
  else if (drag.kind === 'fly') { fly.x = nx; fly.y = ny; send({ cmd: 'fly', x: nx, y: ny }); }
  else { const o = state[drag.kind][drag.id]; if (!o) return; o.x = nx; o.y = ny; send({ cmd: drag.kind, id: drag.id, ...o }); setState({}); }
}
function up(e) {
  if (drag) { drag = null; controls.enabled = !$('chase').checked; return; }
  if (e.button !== 0 || Math.hypot(e.clientX - p0.x, e.clientY - p0.y) > 4) return;
  if (downPart) { sel = { kind: 'fly' }; highlight(downPart.pops); setState({}); return; }
  const p = onPlane(e, 0); if (!p || p.x < 0 || p.x > state.size || p.y < 0 || p.y > state.size) return;
  const kind = e.shiftKey ? 'patch' : $('place').value, id = kind === 'light' ? 'light' : String(nextId++);
  state[kind][id] = { x: p.x, y: p.y, ...(kind === 'source' ? { z: 25, amp: 1, sigma: 20 } : kind === 'light' ? { z: 40, amp: 1 } : { r: 5 }) };
  send({ cmd: kind, id, x: p.x, y: p.y }); sel = { kind, id }; setState({});
}

// --- render: animate the fly from its channels, chase cam, HUD, channel strip ---
function draw(now) {
  requestAnimationFrame(draw); wallT = now / 1000;
  const G = state.gains, f = fly, landed = (f.z ?? 1) <= 0, feeding = landed && f.shiu_mn9 > (G.mn9_thr ?? 20);
  if (f.x != null) {
    flyG.position.set(f.x, f.y, f.z); flyG.rotation.z = f.th; flyG.rotation.y = -Math.atan2(f.vz, Math.max(f.v, 1));
    head.rotation.z = Math.max(-.5, Math.min(.5, .01 * (f.neck_l - f.neck_r)));
    antL.rotation.y = .4 * Math.sin(wallT * 30) * Math.min(1, f.antmn_l / 20); antR.rotation.y = -.4 * Math.sin(wallT * 30) * Math.min(1, f.antmn_r / 20);
    prob.scale.y = .3 + .7 * Math.min(1, f.shiu_mn9 / (G.mn9_thr ?? 20));
    if (landed) phase += f.v * .05;
    legs.forEach((l, i) => l.rotation.z = landed ? .5 * Math.sin(phase + i * Math.PI) : .3);
    const amp = landed ? 0 : .4 + .6 * Math.min(1, f.dng02 / 30), fl = amp * Math.sin(wallT * 60), fold = landed ? 1.25 : .2;
    wingL.rotation.set(fl, 0, fold); wingR.rotation.set(-fl, 0, Math.PI - fold);
    body.material.color.set(feeding ? 0x4ade80 : 0x6b4a2b);
    if ($('chase').checked) { camera.position.lerp(new THREE.Vector3(f.x - 14 * Math.cos(f.th), f.y - 14 * Math.sin(f.th), f.z + 7), .1); camera.lookAt(f.x + 4 * Math.cos(f.th), f.y + 4 * Math.sin(f.th), f.z); }
  }
  scene.getObjectByName('start').position.set(state.start[0], state.start[1], (state.start[2] ?? 0) + .05);
  for (const g of objs.values()) { const h = g.userData.handle; h.material.color.set(sel && sel.kind === h.userData.kind && sel.id === h.userData.id ? 0xffffff : COLOR[h.userData.kind]); }
  if (!$('chase').checked) controls.update();
  renderer.render(scene, camera);
  const srcs = Object.values(state.source); let idx = '—';
  if (srcs.length && f.x != null) { const near = p => Math.min(...srcs.map(o => Math.hypot(p[0] - o.x, p[1] - o.y, (p[2] ?? 0) - o.z))); const d0 = near(state.start); idx = d0 > 0 ? ((d0 - near([f.x, f.y, f.z])) / d0).toFixed(2) : '—'; }
  hud.textContent = `bio ${(bioT / 1000).toFixed(2)} s · feeds ${f.feeds ?? 0} · index ${idx}\nz ${(f.z ?? 0).toFixed(1)} · v ${(f.v ?? 0).toFixed(1)} · vz ${(f.vz ?? 0).toFixed(1)} mm/s · ${landed ? 'landed' : 'airborne'}${feeding ? ' · feeding' : ''}`;
  drawStrip();
}
function drawStrip() {
  const g = strip.getContext('2d'), W = strip.width = strip.clientWidth * devicePixelRatio, Hh = strip.height = strip.clientHeight * devicePixelRatio, rh = 12 * devicePixelRatio, x0 = 64 * devicePixelRatio, x1 = W - 40 * devicePixelRatio;
  g.fillStyle = '#0a0c14'; g.fillRect(0, 0, W, Hh); g.font = `${10 * devicePixelRatio}px system-ui`; g.lineWidth = devicePixelRatio;
  NAMES.forEach((k, i) => {
    const y = rh * (i + 1), row = sbuf.subarray(i * 200, i * 200 + 200); let mx = 1; for (const v of row) mx = Math.max(mx, v);
    const c = hover?.pops.includes(k) ? '#fff' : i < CH.sense.length ? '#7dd3fc' : '#fb923c';
    g.fillStyle = c; g.fillText(k, 4, y - 2 * devicePixelRatio); g.fillText(row[(sp + 199) % 200].toFixed(0), x1 + 4 * devicePixelRatio, y - 2 * devicePixelRatio);
    g.strokeStyle = c; g.beginPath();
    for (let j = 0; j < 200; j++) { const v = row[(sp + j) % 200], px = x0 + (x1 - x0) * j / 199, py = y - 1 - (rh - 3) * v / mx; j ? g.lineTo(px, py) : g.moveTo(px, py); }
    g.stroke();
  });
}
