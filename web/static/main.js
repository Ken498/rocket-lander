import * as THREE from 'three';

const MAX_THRUST = 30_000;
const RAD2DEG   = 180 / Math.PI;
const BODY_H    = 20;
const BODY_R_TOP = 0.5;
const BODY_R_BOT = 0.7;

// ── Renderer ──────────────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

// ── Scene ─────────────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050a14);
scene.fog = new THREE.FogExp2(0x050a14, 0.0005);

// ── Camera ────────────────────────────────────────────────────────────────────
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 5000);
camera.position.set(0, 130, 210);
camera.lookAt(0, 90, 0);

// ── Lights ────────────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x253050, 3.0));

const sun = new THREE.DirectionalLight(0xfff0e0, 1.8);
sun.position.set(300, 500, 150);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(2048);
sun.shadow.camera.near = 1;
sun.shadow.camera.far  = 1500;
sun.shadow.camera.left = sun.shadow.camera.bottom = -250;
sun.shadow.camera.right = sun.shadow.camera.top   =  250;
scene.add(sun);

// ── Stars ─────────────────────────────────────────────────────────────────────
{
  const pos = [];
  for (let i = 0; i < 4000; i++) {
    const r = 1500 + Math.random() * 800;
    const t = Math.random() * 2 * Math.PI;
    const p = Math.acos(2 * Math.random() - 1);
    pos.push(
      r * Math.sin(p) * Math.cos(t),
      r * Math.cos(p),
      r * Math.sin(p) * Math.sin(t),
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({
    color: 0xffffff, size: 1.8, sizeAttenuation: false,
  })));
}

// ── Ground ────────────────────────────────────────────────────────────────────
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(3000, 3000),
  new THREE.MeshLambertMaterial({ color: 0x111118 }),
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const grid = new THREE.GridHelper(600, 60, 0x1c2535, 0x161e2d);
grid.position.y = 0.02;
scene.add(grid);

// Landing pad + X markings
{
  const pad = new THREE.Mesh(
    new THREE.CylinderGeometry(7, 7, 0.25, 32),
    new THREE.MeshLambertMaterial({ color: 0x2a3345 }),
  );
  pad.position.y = 0.125;
  pad.receiveShadow = true;
  scene.add(pad);

  // Outer ring
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(6.5, 7.2, 32),
    new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.26;
  scene.add(ring);

  // Cross arms
  [0, Math.PI / 2].forEach(angle => {
    const arm = new THREE.Mesh(
      new THREE.BoxGeometry(11, 0.05, 0.4),
      new THREE.MeshBasicMaterial({ color: 0xffffff }),
    );
    arm.rotation.y = angle;
    arm.position.y = 0.27;
    scene.add(arm);
  });
}

// ── Rocket ────────────────────────────────────────────────────────────────────
// Origin is at the rocket base (ground contact point).
const rocketGroup = new THREE.Group();
scene.add(rocketGroup);

const silverMat  = new THREE.MeshPhongMaterial({ color: 0xd5d8dc, shininess: 130, specular: 0x555555 });
const darkMat    = new THREE.MeshPhongMaterial({ color: 0x1a1a28, shininess: 50 });
const accentMat  = new THREE.MeshPhongMaterial({ color: 0x1a4d99, shininess: 120 });
const windowMat  = new THREE.MeshPhongMaterial({ color: 0x88ccff, emissive: 0x224466, shininess: 200 });

// Body
const body = new THREE.Mesh(
  new THREE.CylinderGeometry(BODY_R_TOP, BODY_R_BOT, BODY_H, 14),
  silverMat,
);
body.position.y = BODY_H / 2;
body.castShadow = true;
rocketGroup.add(body);

// Nose cone
const nose = new THREE.Mesh(new THREE.ConeGeometry(BODY_R_TOP, 4.5, 14), silverMat);
nose.position.y = BODY_H + 2.25;
rocketGroup.add(nose);

// Accent band
const band = new THREE.Mesh(
  new THREE.CylinderGeometry(BODY_R_TOP + 0.06, BODY_R_TOP + 0.06, 0.9, 14),
  accentMat,
);
band.position.y = BODY_H * 0.7;
rocketGroup.add(band);

// Viewport window
const win = new THREE.Mesh(new THREE.SphereGeometry(0.28, 8, 8), windowMat);
win.position.set(BODY_R_TOP + 0.05, BODY_H * 0.82, 0);
rocketGroup.add(win);

// Engine nozzle
const nozzle = new THREE.Mesh(
  new THREE.CylinderGeometry(0.7, 0.45, 2.2, 12),
  darkMat,
);
nozzle.position.y = -1.1;
rocketGroup.add(nozzle);

// Fins — 4 fins at base, angled for an aerodynamic look
[-1, 1].forEach(side => {
  [0, Math.PI / 2].forEach(rotY => {
    const fin = new THREE.Mesh(
      new THREE.BoxGeometry(3.8, 4.5, 0.18),
      darkMat,
    );
    fin.position.set(side * (BODY_R_BOT + 1.7), 2.25, 0);
    fin.rotation.y = rotY;
    fin.castShadow = true;
    rocketGroup.add(fin);
  });
});

// ── Flame ─────────────────────────────────────────────────────────────────────
const flameGroup = new THREE.Group();
flameGroup.position.y = -2.2;   // nozzle exit
flameGroup.visible = false;
rocketGroup.add(flameGroup);

// Outer flame (orange)
const outerFlameMat = new THREE.MeshBasicMaterial({
  color: 0xff6600, transparent: true, opacity: 0.85,
});
const outerFlameMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.45, 1, 10),
  outerFlameMat,
);
outerFlameMesh.rotation.z = Math.PI;  // apex points down
flameGroup.add(outerFlameMesh);

// Inner flame (bright yellow core)
const innerFlameMat = new THREE.MeshBasicMaterial({ color: 0xffee88 });
const innerFlameMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.2, 1, 8),
  innerFlameMat,
);
innerFlameMesh.rotation.z = Math.PI;
flameGroup.add(innerFlameMesh);

// ── HUD elements ──────────────────────────────────────────────────────────────
const hT   = document.getElementById('h-t');
const hAlt = document.getElementById('h-alt');
const hVy  = document.getElementById('h-vy');
const hSpd = document.getElementById('h-spd');
const hTh  = document.getElementById('h-th');
const hM   = document.getElementById('h-m');
const hThr = document.getElementById('h-thr');
const tlBar = document.getElementById('timeline-bar');

function updateHUD(f, idx, total) {
  const spd = Math.hypot(f.vx, f.vy);
  const thr = f.thrust / 1000;
  hT.textContent   = f.t.toFixed(2)  + ' s';
  hAlt.textContent = Math.max(0, f.y).toFixed(1) + ' m';
  hVy.textContent  = f.vy.toFixed(2) + ' m/s';
  hSpd.textContent = spd.toFixed(2)  + ' m/s';
  hTh.textContent  = (f.theta * RAD2DEG).toFixed(1) + '°';
  hM.textContent   = f.m.toFixed(0)  + ' kg';
  hThr.textContent = thr.toFixed(1)  + ' kN';
  hThr.className   = 'val' + (thr > 15 ? ' warn' : '');
  tlBar.style.width = (idx / total * 100).toFixed(2) + '%';
}

// ── Camera follow (smooth lerp) ───────────────────────────────────────────────
const _camTarget = new THREE.Vector3();
const _camPos    = new THREE.Vector3();

function followCamera(rx, ry) {
  _camPos.set(rx, Math.max(ry + 50, 60), 190);
  _camTarget.set(rx, Math.max(ry + 8, 8), 0);
  camera.position.lerp(_camPos, 0.05);
  camera.lookAt(_camTarget);
}

// ── Playback state ────────────────────────────────────────────────────────────
let traj      = [];
let frameIdx  = 0;
let playing   = true;
let speed     = 1;
let lastTs    = 0;
const FRAME_MS = 1000 / 60;

// ── Controls ──────────────────────────────────────────────────────────────────
document.getElementById('btn-play').addEventListener('click', () => {
  playing = !playing;
  document.getElementById('btn-play').textContent = playing ? '⏸' : '▶';
});
document.getElementById('btn-restart').addEventListener('click', () => {
  frameIdx = 0; playing = true; lastTs = 0;
  document.getElementById('btn-play').textContent = '⏸';
});

const speedBtns = { 'btn-h': 0.5, 'btn-1': 1, 'btn-2': 2, 'btn-4': 4 };
Object.entries(speedBtns).forEach(([id, s]) => {
  document.getElementById(id).addEventListener('click', () => {
    speed = s;
    Object.keys(speedBtns).forEach(k => document.getElementById(k).classList.remove('active'));
    document.getElementById(id).classList.add('active');
  });
});

document.getElementById('timeline-wrap').addEventListener('click', e => {
  const r = e.currentTarget.getBoundingClientRect();
  frameIdx = Math.floor((e.clientX - r.left) / r.width * traj.length);
});

// ── Flame flicker ─────────────────────────────────────────────────────────────
let flickT = 0;

function updateFlame(thrustN) {
  const ratio = thrustN / MAX_THRUST;
  flameGroup.visible = ratio > 0.005;
  if (!flameGroup.visible) return;
  flickT += 0.25;
  const flicker = 1 + 0.12 * Math.sin(flickT * 11.3) + 0.08 * Math.sin(flickT * 6.7);
  const len = (3 + 5 * ratio) * flicker;
  outerFlameMesh.scale.set(0.6 + ratio * 0.5, len, 0.6 + ratio * 0.5);
  innerFlameMesh.scale.set(0.5 + ratio * 0.3, len * 0.65, 0.5 + ratio * 0.3);
  outerFlameMat.opacity = 0.65 + 0.3 * ratio;
}

// ── Render loop ───────────────────────────────────────────────────────────────
function renderLoop(ts) {
  requestAnimationFrame(renderLoop);

  if (traj.length === 0) { renderer.render(scene, camera); return; }

  if (playing) {
    if (lastTs === 0) lastTs = ts;
    const advance = Math.floor((ts - lastTs) / FRAME_MS * speed);
    if (advance > 0) {
      frameIdx = Math.min(frameIdx + advance, traj.length - 1);
      lastTs = ts;
    }
  }

  const f = traj[frameIdx];
  const ry = Math.max(0, f.y);

  rocketGroup.position.set(f.x, ry, 0);
  rocketGroup.rotation.z = f.theta;  // CCW positive, same convention as physics

  updateFlame(f.thrust);
  updateHUD(f, frameIdx, traj.length - 1);
  followCamera(f.x, ry);

  renderer.render(scene, camera);
}

// ── Fetch trajectory ──────────────────────────────────────────────────────────
(async () => {
  try {
    const res = await fetch('/api/trajectory');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    traj = await res.json();

    document.getElementById('loading').style.display = 'none';
    document.getElementById('hud').style.display      = 'block';
    document.getElementById('controls').style.display = 'flex';

    requestAnimationFrame(renderLoop);
  } catch (err) {
    document.getElementById('loading').textContent = 'ERROR: ' + err.message;
  }
})();

// ── Resize ────────────────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
