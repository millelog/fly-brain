// 3D brain: soma point cloud where active neurons grow and glow (bio-time decay), clip slabs, per-class opacity, picking + inspector, neuropil hulls.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const $ = id => document.getElementById(id);
const palette = { optic: [.22,.24,.36], central: [.36,.30,.42], sensory: [.24,.40,.32], motor: [.55,.30,.20], descending: [.55,.45,.15], ascending: [.30,.45,.45],
  visual_projection: [.25,.30,.45], visual_centrifugal: [.30,.25,.45], sensory_ascending: [.25,.40,.40], endocrine: [.45,.25,.35], unknown: [.30,.30,.34] };
const roColors = ['#4ade80', '#f472b6', '#60a5fa', '#facc15', '#fb923c'];
let meta, send, N, V, vert, v2n, pos, base, heat, alpha, renderer, scene, camera, controls, geo, points, mat, planes, cx, cy, cz, bbox, slot;
let bioT = 0, bioT0 = -1, frames = 0, active = 0, t0 = performance.now();
const hist = [], ROLL = 200; // recent Frames for readout Hz
const opac = {}, pins = [], traces = new Map(); // traces: neuron -> Uint16Array ring of counts
let selected = null, partners = new Set(), inSet = null, hulls = [];

const VERT = `
attribute vec3 base; attribute float heat; attribute float alpha;
uniform float size, scale, actOnly, floor;
varying vec3 vColor; varying float vAlpha;
#include <clipping_planes_pars_vertex>
void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  gl_PointSize = size * (1.0 + 1.5 * heat) * scale / -mvPosition.z;
  vColor = mix(base, mix(vec3(1.0, 0.55, 0.1), vec3(1.0, 0.95, 0.6), heat), heat);
  vAlpha = alpha * mix(1.0, max(heat, floor), actOnly);
  #include <clipping_planes_vertex>
}`;
const FRAG = `
varying vec3 vColor; varying float vAlpha;
#include <clipping_planes_pars_fragment>
void main() {
  #include <clipping_planes_fragment>
  if (length(gl_PointCoord - 0.5) > 0.5) discard;
  gl_FragColor = vec4(vColor, vAlpha);
}`;

export function init(o) {
  meta = o.meta; send = o.send; N = meta.n; const xyz = o.xyz;
  vert = new Int32Array(N).fill(-1); pos = []; v2n = [];
  cx = cy = cz = 0;
  for (let i = 0; i < N; i++) if (!Number.isNaN(xyz[3 * i])) { vert[i] = pos.length / 3; v2n.push(i); pos.push(xyz[3 * i], xyz[3 * i + 1], xyz[3 * i + 2]); }
  V = pos.length / 3;
  for (let v = 0; v < V; v++) { cx += pos[3 * v]; cy += pos[3 * v + 1]; cz += pos[3 * v + 2]; }
  cx /= V; cy /= V; cz /= V;
  bbox = [[1e9, -1e9], [1e9, -1e9], [1e9, -1e9]];
  for (let v = 0; v < V; v++) { pos[3 * v] -= cx; pos[3 * v + 1] = -(pos[3 * v + 1] - cy); pos[3 * v + 2] -= cz; for (let a = 0; a < 3; a++) { bbox[a][0] = Math.min(bbox[a][0], pos[3 * v + a]); bbox[a][1] = Math.max(bbox[a][1], pos[3 * v + a]); } }
  base = new Float32Array(V * 3); heat = new Float32Array(V); alpha = new Float32Array(V).fill(.9); slot = new Int32Array(N).fill(-1);

  renderer = new THREE.WebGLRenderer({ canvas: $('c'), antialias: true }); renderer.setPixelRatio(devicePixelRatio); renderer.localClippingEnabled = true;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, 1, 1, 1e5); camera.position.set(0, 0, 1700);
  controls = new OrbitControls(camera, renderer.domElement); controls.autoRotate = true; controls.autoRotateSpeed = 0.4;
  planes = [...[0, 1, 2].flatMap(a => { const n1 = new THREE.Vector3(), n2 = new THREE.Vector3(); n1.setComponent(a, 1); n2.setComponent(a, -1); return [new THREE.Plane(n1, -bbox[a][0] - 1), new THREE.Plane(n2, bbox[a][1] + 1)]; }),
    new THREE.Plane(new THREE.Vector3(0, 0, 1), 1e5), new THREE.Plane(new THREE.Vector3(0, 0, -1), 1e5)];
  geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('base', new THREE.BufferAttribute(base, 3));
  geo.setAttribute('heat', new THREE.BufferAttribute(heat, 1));
  geo.setAttribute('alpha', new THREE.BufferAttribute(alpha, 1));
  mat = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, clipping: true, clippingPlanes: planes,
    uniforms: { size: { value: 5 }, scale: { value: 1 }, actOnly: { value: 1 }, floor: { value: .06 } } });
  points = new THREE.Points(geo, mat);
  scene.add(points);
  addEventListener('resize', resize); resize();
  buildPanel(); paintBase(); loadHulls();
  renderer.domElement.addEventListener('pointerdown', e => { pick.x = e.clientX; pick.y = e.clientY; });
  renderer.domElement.addEventListener('pointerup', e => { if (Math.hypot(e.clientX - pick.x, e.clientY - pick.y) < 4) onPick(e); });
  requestAnimationFrame(loop);
}
export function resize() { const el = $('right'); renderer.setSize(el.clientWidth, el.clientHeight, false); camera.aspect = el.clientWidth / el.clientHeight; camera.updateProjectionMatrix(); mat.uniforms.scale.value = renderer.domElement.height / 2; }
export function setHighlight(pops) { for (const o of $('ro').options) o.selected = pops.includes(o.value); paintBase(); readoutRates(); }

function paintBase() {
  for (let i = 0; i < N; i++) { const v = vert[i]; if (v >= 0) base.set(palette[meta.super_class[i]] || palette.unknown, 3 * v); }
  const sel = [...$('ro').selectedOptions].map(o => o.value);
  slot.fill(-1);
  sel.forEach((s, j) => { const c = new THREE.Color(roColors[j % 5]); paintPop(meta.populations[s], [c.r, c.g, c.b]); for (const i of meta.populations[s]) slot[i] = j; });
  if (selected != null) { paintPop([...partners], [.95, .5, .2]); paintPop([selected], [1, 1, 1]); }
  inSet = $('isolate')?.checked && selected != null ? new Set([selected, ...partners, ...sel.flatMap(s => meta.populations[s])]) : null;
  geo.attributes.base.needsUpdate = true; paintAlpha();
}
function paintPop(indices, c) { for (const i of indices) if (vert[i] >= 0) base.set(c, 3 * vert[i]); }
function paintAlpha() {
  for (let v = 0; v < V; v++) { const i = v2n[v]; alpha[v] = (opac[meta.super_class[i]] ?? 1) * (inSet && !inSet.has(i) ? .02 : 1) * .9; }
  geo.attributes.alpha.needsUpdate = true;
}

// --- panel ---
function buildPanel() {
  const pops = Object.keys(meta.populations);
  for (const p of pops) { $('ro').add(new Option(`${p} (${meta.populations[p].length})`, p)); $('pokepop').add(new Option(`${p} (${meta.populations[p].length})`, p)); }
  for (const o of $('ro').options) o.selected = ['shiu_mn9', 'dna02_l', 'dna02_r', 'dng02'].includes(o.value);
  $('pokepop').value = 'orn_food_l';
  $('ro').onchange = paintBase;
  $('poke').onclick = () => send({ cmd: 'poke', pop: $('pokepop').value, rate: +$('pokerate').value, ms: +$('pokems').value });
  const classes = [...new Set(meta.super_class)].sort();
  $('opac').innerHTML = classes.map(c => `<span>${c}</span><input type="range" data-c="${c}" min="0" max="1" step=".02" value="${c === 'optic' ? .25 : 1}"><span id="ov_${c}">${c === 'optic' ? .25 : 1}</span>`).join('');
  for (const c of classes) opac[c] = c === 'optic' ? .25 : 1;
  $('opac').oninput = e => { opac[e.target.dataset.c] = +e.target.value; $('ov_' + e.target.dataset.c).textContent = e.target.value; paintAlpha(); };
  $('slice').innerHTML = ['x', 'y', 'z'].flatMap((a, i) => [`<span>${a} min</span><input type="range" data-p="${2 * i}" min="${bbox[i][0]}" max="${bbox[i][1]}" value="${bbox[i][0]}" step="1"><span id="sv${2 * i}">${bbox[i][0] | 0}</span>`,
    `<span>${a} max</span><input type="range" data-p="${2 * i + 1}" min="${bbox[i][0]}" max="${bbox[i][1]}" value="${bbox[i][1]}" step="1"><span id="sv${2 * i + 1}">${bbox[i][1] | 0}</span>`]).join('');
  $('slice').oninput = e => { const p = +e.target.dataset.p; planes[p].constant = (p % 2 ? 1 : -1) * +e.target.value; $('sv' + p).textContent = e.target.value; };
  $('camd').oninput = () => $('camdv').textContent = $('camd').value; $('camw').oninput = () => $('camwv').textContent = $('camw').value;
  $('tau').oninput = () => $('tauv').textContent = $('tau').value; $('floor').oninput = () => { mat.uniforms.floor.value = +$('floor').value; $('floorv').textContent = $('floor').value; };
  $('actonly').onchange = () => mat.uniforms.actOnly.value = $('actonly').checked ? 1 : 0;
  $('isolate').onchange = paintBase; $('rotate').onchange = () => controls.autoRotate = $('rotate').checked;
  $('iclose').onclick = () => { selected = null; partners = new Set(); $('inspector').classList.remove('on'); paintBase(); };
  $('ipoke').onclick = () => send({ cmd: 'poke', idx: [selected], rate: +$('pokerate').value, ms: +$('pokems').value });
  $('pin').onclick = () => { if (selected != null && !pins.includes(selected)) { pins.push(selected); traces.set(selected, new Uint16Array(200)); } };
}
function loadHulls() {
  new GLTFLoader().load('/static/neuropils.glb', g => {
    const grp = g.scene; grp.scale.set(1, -1, 1); grp.position.set(-cx, cy, -cz);
    grp.traverse(m => { if (m.isMesh) { m.material = new THREE.MeshBasicMaterial({ color: 0x3b82f6, transparent: true, opacity: .06, side: THREE.DoubleSide, depthWrite: false, clippingPlanes: planes }); hulls.push(m); } });
    scene.add(grp);
    $('hulls').innerHTML = `<h2>Neuropils</h2><div class="g"><span>opacity</span><input id="hop" type="range" min="0" max=".6" step=".01" value=".06"><span></span></div>` + hulls.map((m, i) => `<label><input type="checkbox" data-h="${i}" checked> ${m.name}</label>`).join('');
    $('hop').oninput = () => hulls.forEach(m => m.material.opacity = +$('hop').value);
    $('hulls').onchange = e => { if (e.target.dataset.h) hulls[+e.target.dataset.h].visible = e.target.checked; };
  }, undefined, () => {});
}

// --- picking + inspector ---
const pick = { x: 0, y: 0 }, ray = new THREE.Raycaster(); ray.params.Points.threshold = 6;
async function onPick(e) {
  const r = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const fl = $('actonly').checked ? mat.uniforms.floor.value : 1;
  const hit = ray.intersectObject(points).find(h => alpha[h.index] * Math.max(heat[h.index], fl) > 0.05 && planes.every(p => p.distanceToPoint(new THREE.Vector3().fromBufferAttribute(geo.attributes.position, h.index)) >= 0));
  if (!hit) return;
  selected = v2n[hit.index];
  const d = await (await fetch(`/api/neuron/${selected}`)).json();
  partners = new Set([...d.out.map(x => x[0]), ...d.in.map(x => x[0])]);
  $('ititle').textContent = `#${selected} ${d.cell_type || d.cell_class || d.super_class || ''}`;
  $('ibody').textContent = `root ${d.root_id}\n${d.super_class} · ${d.cell_class || ''} · ${d.cell_sub_class || ''}\nside ${d.side} · ${d.top_nt || '?'} · ${d.flow}\nout ${d.n_out} (top: ${d.out.slice(0, 3).map(x => x[0]).join(', ')})\nin ${d.n_in} (top: ${d.in.slice(0, 3).map(x => x[0]).join(', ')})`;
  $('inspector').classList.add('on'); paintBase();
}

// --- streaming: heat decays in bio time, so pause freezes the glow and propagation runs at the sim's pace ---
export function onFrame(t, idx, cnt) {
  if (bioT0 < 0 || t < bioT) { bioT0 = t; t0 = performance.now(); }  // first frame, or the World was reset
  const k = Math.exp(-Math.max(0, t - bioT) / +$('tau').value);
  bioT = t; frames++; active = idx.length;
  for (let v = 0; v < V; v++) heat[v] *= k;
  for (const [, tr] of traces) { tr.copyWithin(0, 1); tr[199] = 0; }
  for (let k = 0; k < idx.length; k++) { const v = vert[idx[k]]; if (v >= 0) heat[v] = Math.min(1, heat[v] + 0.4 * cnt[k]); const tr = traces.get(idx[k]); if (tr) tr[199] = cnt[k]; }
  geo.attributes.heat.needsUpdate = true;
  hist.push({ t, idx, cnt }); while (hist.length && hist[0].t < t - ROLL) hist.shift();
  if (frames % 5 === 0) { readoutRates(); stats(); drawTraces(); }
}
function readoutRates() {
  const sel = [...$('ro').selectedOptions].map(o => o.value), tot = new Float64Array(sel.length);
  const span = Math.min(ROLL, bioT || ROLL);
  let c = 0;
  for (const f of hist) for (let k = 0; k < f.idx.length; k++) { const s = slot[f.idx[k]]; if (s >= 0) tot[s] += f.cnt[k]; if (f.idx[k] === selected) c += f.cnt[k]; }
  $('ititle').textContent = $('ititle').textContent.replace(/ · \d+ Hz$/, '') + (selected != null ? ` · ${(c * 1000 / span).toFixed(0)} Hz` : '');
  $('readouts').innerHTML = sel.map((s, j) => `<span><i class="sw" style="background:${roColors[j % 5]}"></i></span><span>${s}</span><span>${(tot[j] / meta.populations[s].length * 1000 / span).toFixed(1)} Hz</span>`).join('');
}
function stats() {
  const wall = (performance.now() - t0) / 1000;
  $('stats').textContent = `${meta.device}${meta.replay ? ' · replay' : ''} · ${N.toLocaleString()} neurons, ${meta.no_soma.toLocaleString()} drawn at arbor position (no soma)\nbio ${(bioT / 1000).toFixed(2)} s · wall ${wall.toFixed(0)} s · ${(wall / ((bioT - bioT0) / 1000 || 1)).toFixed(1)} s/bio-s\nactive last frame: ${active}`;
}
function drawTraces() {
  const c = $('trace'), g = c.getContext('2d'); c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio;
  g.fillStyle = '#0a0c14'; g.fillRect(0, 0, c.width, c.height);
  const rows = pins.length; if (!rows) return;
  const rh = c.height / rows, bw = c.width / 200;
  pins.forEach((n, r) => { const tr = traces.get(n); g.fillStyle = roColors[r % 5]; for (let k = 0; k < 200; k++) if (tr[k]) g.fillRect(k * bw, rh * (r + 1) - Math.min(rh, tr[k] * rh / 3), Math.max(1, bw), Math.min(rh, tr[k] * rh / 3)); g.fillStyle = '#8b93a7'; g.font = `${10 * devicePixelRatio}px system-ui`; g.fillText(`#${n}`, 3, rh * r + 10 * devicePixelRatio); });
}

// --- render loop: only the view-aligned slab is per-frame work; colors and sizes live in the shader ---
const dir = new THREE.Vector3();
function loop() {
  requestAnimationFrame(loop);
  if ($('camclip').checked) { camera.getWorldDirection(dir); const d = +$('camd').value, w = +$('camw').value; planes[6].normal.copy(dir); planes[6].constant = -(d - w / 2); planes[7].normal.copy(dir).negate(); planes[7].constant = d + w / 2; }
  else { planes[6].constant = planes[7].constant = 1e5; }
  controls.update(); renderer.render(scene, camera);
}
