import * as THREE from 'three';

const MAX_THRUST  = 30_000;
const RAD2DEG     = 180 / Math.PI;
const BODY_H      = 20;
const BODY_R_TOP  = 0.5;
const BODY_R_BOT  = 0.7;
const LEG_DEPLOY_START = 30;  // m — legs begin to extend
const LEG_DEPLOY_FULL  = 5;   // m — legs fully extended

// ── Renderer ──────────────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

// ── Scene ─────────────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x04080f);
scene.fog = new THREE.FogExp2(0x04080f, 0.0004);

// ── Camera ────────────────────────────────────────────────────────────────────
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 5000);
camera.position.set(0, 130, 210);
camera.lookAt(0, 90, 0);

// ── Lights ────────────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x1a2a40, 2.0));

// Moonlight — cool blue-white from high angle
const moon = new THREE.DirectionalLight(0xb0c8e8, 0.6);
moon.position.set(-200, 600, 300);
moon.castShadow = true;
moon.shadow.mapSize.setScalar(2048);
moon.shadow.camera.near = 1;
moon.shadow.camera.far  = 1500;
moon.shadow.camera.left = moon.shadow.camera.bottom = -250;
moon.shadow.camera.right = moon.shadow.camera.top   =  250;
scene.add(moon);

// Engine glow light — follows the rocket nozzle
const engineLight = new THREE.PointLight(0xff7700, 0, 120);
scene.add(engineLight);

// ── Stars ─────────────────────────────────────────────────────────────────────
{
  const pos = [];
  for (let i = 0; i < 4000; i++) {
    const r = 1500 + Math.random() * 800;
    const t = Math.random() * 2 * Math.PI;
    const p = Math.acos(2 * Math.random() - 1);
    pos.push(r * Math.sin(p) * Math.cos(t), r * Math.cos(p), r * Math.sin(p) * Math.sin(t));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({
    color: 0xffffff, size: 1.8, sizeAttenuation: false,
  })));
}

// ── KSC Ground — concrete ─────────────────────────────────────────────────────
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(4000, 4000),
  new THREE.MeshLambertMaterial({ color: 0x1a1a18 }),
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// Concrete apron around the landing zone
{
  const apron = new THREE.Mesh(
    new THREE.PlaneGeometry(160, 160),
    new THREE.MeshLambertMaterial({ color: 0x252520 }),
  );
  apron.rotation.x = -Math.PI / 2;
  apron.position.y = 0.01;
  scene.add(apron);
}

// KSC Landing Zone 1 — SpaceX RTLS pad
{
  const concreteMat = new THREE.MeshLambertMaterial({ color: 0x2e2e2b });
  const whiteMat    = new THREE.MeshBasicMaterial({ color: 0xddddcc, side: THREE.DoubleSide });
  const yellowMat   = new THREE.MeshBasicMaterial({ color: 0xd4a017, side: THREE.DoubleSide });

  // Pad surface
  const pad = new THREE.Mesh(new THREE.CylinderGeometry(18, 18, 0.2, 48), concreteMat);
  pad.position.y = 0.1;
  pad.receiveShadow = true;
  scene.add(pad);

  // Outer ring stripe
  const outerRing = new THREE.Mesh(
    new THREE.RingGeometry(16.5, 18.2, 48),
    whiteMat,
  );
  outerRing.rotation.x = -Math.PI / 2;
  outerRing.position.y = 0.22;
  scene.add(outerRing);

  // Inner target circle
  const innerRing = new THREE.Mesh(
    new THREE.RingGeometry(5.5, 6.5, 48),
    yellowMat,
  );
  innerRing.rotation.x = -Math.PI / 2;
  innerRing.position.y = 0.22;
  scene.add(innerRing);

  // SpaceX X marking — two crossing bars
  [-Math.PI / 4, Math.PI / 4].forEach(a => {
    const bar = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 2.2),
      yellowMat,
    );
    bar.rotation.x = -Math.PI / 2;
    bar.rotation.z = a;
    bar.position.y = 0.22;
    scene.add(bar);
  });

  // Compass tick marks
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    const tick = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 3), whiteMat);
    tick.rotation.x = -Math.PI / 2;
    tick.rotation.z = angle;
    tick.position.set(Math.sin(angle) * 14, 0.22, Math.cos(angle) * 14);
    scene.add(tick);
  }
}

// ── KSC Environment ───────────────────────────────────────────────────────────

// Horizon glow — light pollution from the facility
{
  const glowMat = new THREE.MeshBasicMaterial({
    color: 0x1a2a1a, transparent: true, opacity: 0.5,
    side: THREE.BackSide,
  });
  const glowDome = new THREE.Mesh(new THREE.SphereGeometry(1800, 32, 8, 0, Math.PI * 2, 0, 0.3), glowMat);
  scene.add(glowDome);
}

// Florida treeline — scrub pine silhouettes ringing the pad
{
  const treeMat  = new THREE.MeshBasicMaterial({ color: 0x060c06 });
  const trunkMat = new THREE.MeshBasicMaterial({ color: 0x050905 });
  const rng = (a, b) => a + Math.random() * (b - a);

  for (let i = 0; i < 320; i++) {
    const angle  = rng(0, Math.PI * 2);
    const dist   = rng(230, 420);
    const x      = Math.cos(angle) * dist;
    const z      = Math.sin(angle) * dist;
    const h      = rng(12, 32);
    const isPalm = Math.random() < 0.2;

    if (isPalm) {
      // Slender palm trunk
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.5, h * 0.85, 5), trunkMat);
      trunk.position.set(x, h * 0.425, z);
      scene.add(trunk);
      // Palm canopy — flat wide cone
      const canopy = new THREE.Mesh(new THREE.ConeGeometry(rng(4, 7), h * 0.2, 6), treeMat);
      canopy.position.set(x, h * 0.85 + h * 0.1, z);
      scene.add(canopy);
    } else {
      // Florida scrub pine — tall narrow cone
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.6, h * 0.35, 5), trunkMat);
      trunk.position.set(x, h * 0.175, z);
      scene.add(trunk);
      const canopy = new THREE.Mesh(new THREE.ConeGeometry(rng(2.5, 4.5), h * 0.72, 6), treeMat);
      canopy.position.set(x, h * 0.35 + h * 0.36, z);
      scene.add(canopy);
    }
  }
}

// Vehicle Assembly Building (VAB) silhouette — NW of LZ-1, ~5 km away
{
  const silMat = new THREE.MeshBasicMaterial({ color: 0x090d12 });

  // Main VAB box
  const vab = new THREE.Mesh(new THREE.BoxGeometry(55, 110, 45), silMat);
  vab.position.set(-320, 55, -480);
  scene.add(vab);

  // Smaller adjacent structure (Low Bay)
  const lowBay = new THREE.Mesh(new THREE.BoxGeometry(35, 55, 40), silMat);
  lowBay.position.set(-370, 27, -475);
  scene.add(lowBay);

  // Launch Control Centre
  const lcc = new THREE.Mesh(new THREE.BoxGeometry(50, 28, 28), silMat);
  lcc.position.set(-240, 14, -440);
  scene.add(lcc);
}

// Floodlight towers around the pad
{
  const towerMat = new THREE.MeshLambertMaterial({ color: 0x303030 });
  const armMat   = new THREE.MeshBasicMaterial({ color: 0x252525 });
  const floodPositions = [[-55, -55], [55, -55], [-55, 55], [55, 55]];

  floodPositions.forEach(([tx, tz]) => {
    // Tower mast
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.7, 28, 6), towerMat);
    mast.position.set(tx, 14, tz);
    scene.add(mast);

    // Horizontal arm
    const arm = new THREE.Mesh(new THREE.BoxGeometry(6, 0.5, 0.5), armMat);
    arm.position.set(tx, 28.5, tz);
    scene.add(arm);

    // Warm floodlight
    const flood = new THREE.PointLight(0xfff5d0, 1.2, 160);
    flood.position.set(tx, 30, tz);
    scene.add(flood);
  });
}

// Banana River — flat dark water plane to the east
{
  const waterMat = new THREE.MeshLambertMaterial({ color: 0x06100e, transparent: true, opacity: 0.85 });
  const water = new THREE.Mesh(new THREE.PlaneGeometry(800, 600), waterMat);
  water.rotation.x = -Math.PI / 2;
  water.position.set(500, 0.05, 100);
  scene.add(water);
}

// ── Materials ─────────────────────────────────────────────────────────────────
const silverMat = new THREE.MeshPhongMaterial({ color: 0xd5d8dc, shininess: 130, specular: 0x555555 });
const darkMat   = new THREE.MeshPhongMaterial({ color: 0x1a1a28, shininess: 50 });
const accentMat = new THREE.MeshPhongMaterial({ color: 0x1a4d99, shininess: 120 });
const windowMat = new THREE.MeshPhongMaterial({ color: 0x88ccff, emissive: 0x224466, shininess: 200 });

// ── Rocket ────────────────────────────────────────────────────────────────────
const rocketGroup = new THREE.Group();
rocketGroup.scale.setScalar(2.5);
scene.add(rocketGroup);

// Body
const body = new THREE.Mesh(new THREE.CylinderGeometry(BODY_R_TOP, BODY_R_BOT, BODY_H, 14), silverMat);
body.position.y = BODY_H / 2;
body.castShadow = true;
rocketGroup.add(body);

// Nose cone
const nose = new THREE.Mesh(new THREE.ConeGeometry(BODY_R_TOP, 4.5, 14), silverMat);
nose.position.y = BODY_H + 2.25;
rocketGroup.add(nose);

// Accent band
const band = new THREE.Mesh(
  new THREE.CylinderGeometry(BODY_R_TOP + 0.06, BODY_R_TOP + 0.06, 0.9, 14), accentMat,
);
band.position.y = BODY_H * 0.7;
rocketGroup.add(band);

// Viewport window
const win = new THREE.Mesh(new THREE.SphereGeometry(0.28, 8, 8), windowMat);
win.position.set(BODY_R_TOP + 0.05, BODY_H * 0.82, 0);
rocketGroup.add(win);

// Engine nozzle
const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.45, 2.2, 12), darkMat);
nozzle.position.y = -1.1;
rocketGroup.add(nozzle);

// Fins — 4 at base
[-1, 1].forEach(side => {
  [0, Math.PI / 2].forEach(rotY => {
    const fin = new THREE.Mesh(new THREE.BoxGeometry(3.8, 4.5, 0.18), darkMat);
    fin.position.set(side * (BODY_R_BOT + 1.7), 2.25, 0);
    fin.rotation.y = rotY;
    fin.castShadow = true;
    rocketGroup.add(fin);
  });
});

// ── Landing legs ─────────────────────────────────────────────────────────────
// Each leg pivots at the body; rotation.z controls deploy angle.
const legPivots = [];
[0, Math.PI / 2, Math.PI, 3 * Math.PI / 2].forEach(rotY => {
  const pivot = new THREE.Group();
  pivot.rotation.y = rotY;
  pivot.position.y = 2.5;

  // Main strut
  const strut = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 7, 6), darkMat);
  strut.position.set(1.2, -3.5, 0);
  strut.rotation.z = -0.18;
  pivot.add(strut);

  // Foot pad
  const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.25, 8), darkMat);
  foot.position.set(2.6, -7, 0);
  pivot.add(foot);

  rocketGroup.add(pivot);
  legPivots.push(pivot);
});

// ── Flame ─────────────────────────────────────────────────────────────────────
const flameGroup = new THREE.Group();
flameGroup.position.y = -2.2;
flameGroup.visible = false;
rocketGroup.add(flameGroup);

// Soft glow sprite (large semitransparent disc behind the flame)
const glowSprite = new THREE.Sprite(new THREE.SpriteMaterial({
  color: 0xff5500,
  transparent: true,
  opacity: 0.18,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
}));
glowSprite.scale.set(18, 18, 1);
glowSprite.position.y = -3;
flameGroup.add(glowSprite);

// Outer flame cone
const outerFlameMat = new THREE.MeshBasicMaterial({
  color: 0xff6600, transparent: true, opacity: 0.85,
});
const outerFlameMesh = new THREE.Mesh(new THREE.ConeGeometry(0.45, 1, 10), outerFlameMat);
outerFlameMesh.rotation.z = Math.PI;
flameGroup.add(outerFlameMesh);

// Inner core (bright yellow)
const innerFlameMat = new THREE.MeshBasicMaterial({ color: 0xffee88 });
const innerFlameMesh = new THREE.Mesh(new THREE.ConeGeometry(0.2, 1, 8), innerFlameMat);
innerFlameMesh.rotation.z = Math.PI;
flameGroup.add(innerFlameMesh);

// ── Exhaust particles ─────────────────────────────────────────────────────────
const MAX_PARTS = 800;
let numParts = 0;
const px  = new Float32Array(MAX_PARTS), py  = new Float32Array(MAX_PARTS), pz  = new Float32Array(MAX_PARTS);
const pvx = new Float32Array(MAX_PARTS), pvy = new Float32Array(MAX_PARTS), pvz = new Float32Array(MAX_PARTS);
const pLife = new Float32Array(MAX_PARTS), pDecay = new Float32Array(MAX_PARTS);

const partPos  = new Float32Array(MAX_PARTS * 3);
const partCol  = new Float32Array(MAX_PARTS * 3);
const partGeo  = new THREE.BufferGeometry();
partGeo.setAttribute('position', new THREE.BufferAttribute(partPos, 3));
partGeo.setAttribute('color',    new THREE.BufferAttribute(partCol, 3));
const partMat = new THREE.PointsMaterial({
  size: 3.5, vertexColors: true,
  transparent: true, opacity: 0.95,
  blending: THREE.AdditiveBlending, depthWrite: false,
});
scene.add(new THREE.Points(partGeo, partMat));

const _nozzleWorld = new THREE.Vector3();

function emitExhaust(thrustN, count) {
  flameGroup.getWorldPosition(_nozzleWorld);
  const ratio = thrustN / MAX_THRUST;
  for (let i = 0; i < count && numParts < MAX_PARTS; i++) {
    const idx = numParts++;
    px[idx]  = _nozzleWorld.x + (Math.random() - 0.5) * 0.6;
    py[idx]  = _nozzleWorld.y;
    pz[idx]  = _nozzleWorld.z + (Math.random() - 0.5) * 0.6;
    const spd = (6 + Math.random() * 18) * ratio;
    pvx[idx] = (Math.random() - 0.5) * 0.4 * spd;
    pvy[idx] = -spd;
    pvz[idx] = (Math.random() - 0.5) * 0.4 * spd;
    pLife[idx]  = 1.0;
    pDecay[idx] = 0.012 + Math.random() * 0.022;
  }
}

function updateParticles(dtSec) {
  let alive = 0;
  for (let i = 0; i < numParts; i++) {
    pLife[i] -= pDecay[i];
    if (pLife[i] <= 0) continue;
    px[i] += pvx[i] * dtSec;  py[i] += pvy[i] * dtSec;  pz[i] += pvz[i] * dtSec;
    pvy[i] += 3 * dtSec;      // exhaust decelerates (against rocket direction)
    pvx[i] *= 0.97;            pvz[i] *= 0.97;
    if (alive !== i) {
      px[alive]=px[i]; py[alive]=py[i]; pz[alive]=pz[i];
      pvx[alive]=pvx[i]; pvy[alive]=pvy[i]; pvz[alive]=pvz[i];
      pLife[alive]=pLife[i]; pDecay[alive]=pDecay[i];
    }
    alive++;
  }
  numParts = alive;

  for (let i = 0; i < MAX_PARTS; i++) {
    if (i < numParts) {
      const l = pLife[i], t = 1 - l;
      partPos[i*3]=px[i]; partPos[i*3+1]=py[i]; partPos[i*3+2]=pz[i];
      // yellow → orange → dark red; multiply by life to fade
      partCol[i*3]   = l * 1.0;
      partCol[i*3+1] = l * Math.max(0, 0.75 - t * 0.9);
      partCol[i*3+2] = l * Math.max(0, 0.15 - t * 0.2);
    } else {
      partPos[i*3]=partPos[i*3+1]=partPos[i*3+2]=0;
      partCol[i*3]=partCol[i*3+1]=partCol[i*3+2]=0;
    }
  }
  partGeo.attributes.position.needsUpdate = true;
  partGeo.attributes.color.needsUpdate    = true;
}

// ── Trajectory trail ──────────────────────────────────────────────────────────
// Populated after trajectory loads; draw range updated each frame.
let trailLine = null;

function buildTrail(traj) {
  const pos = new Float32Array(traj.length * 3);
  traj.forEach((f, i) => { pos[i*3]=f.x; pos[i*3+1]=Math.max(0,f.y); pos[i*3+2]=0; });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setDrawRange(0, 0);
  trailLine = new THREE.Line(geo, new THREE.LineBasicMaterial({
    color: 0x3366cc, transparent: true, opacity: 0.45,
  }));
  scene.add(trailLine);
}

// ── Touchdown effects ─────────────────────────────────────────────────────────
let touchdownDone = false;

const shockwave = new THREE.Mesh(
  new THREE.RingGeometry(0.5, 1, 40),
  new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 1,
    side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false,
  }),
);
shockwave.rotation.x = -Math.PI / 2;
shockwave.position.y = 0.15;
shockwave.visible = false;
scene.add(shockwave);
let shockwaveScale = 0;

function triggerTouchdown(wx, wy) {
  if (touchdownDone) return;
  touchdownDone = true;

  // Spark burst
  for (let i = 0; i < 120; i++) {
    const idx = numParts < MAX_PARTS ? numParts++ : MAX_PARTS - 1;
    const angle = Math.random() * 2 * Math.PI;
    const spd   = 3 + Math.random() * 18;
    px[idx]  = wx; py[idx] = 0.5; pz[idx] = 0;
    pvx[idx] = Math.cos(angle) * spd;
    pvy[idx] = 4 + Math.random() * 12;
    pvz[idx] = Math.sin(angle) * spd;
    pLife[idx]  = 1.0;
    pDecay[idx] = 0.02 + Math.random() * 0.03;
  }

  // Shockwave ring
  shockwave.visible = true;
  shockwaveScale = 0.1;
}

// ── HUD ───────────────────────────────────────────────────────────────────────
const hT          = document.getElementById('h-t');
const hAlt        = document.getElementById('h-alt');
const hVy         = document.getElementById('h-vy');
const hSpd        = document.getElementById('h-spd');
const hTh         = document.getElementById('h-th');
const hM          = document.getElementById('h-m');
const hThr        = document.getElementById('h-thr');
const thrustFill  = document.getElementById('thrust-fill');
const missionStatus = document.getElementById('mission-status');
const tlBar       = document.getElementById('timeline-bar');

function updateHUD(f, idx, total) {
  const spd = Math.hypot(f.vx, f.vy);
  hT.textContent   = f.t.toFixed(2)  + ' s';
  hAlt.textContent = Math.max(0, f.y).toFixed(1) + ' m';
  hVy.textContent  = f.vy.toFixed(2) + ' m/s';
  hSpd.textContent = spd.toFixed(2)  + ' m/s';
  hTh.textContent  = (f.theta * RAD2DEG).toFixed(1) + '°';
  hM.textContent   = f.m.toFixed(0)  + ' kg';
  const thrKN    = f.thrust / 1000;
  const thrRatio = f.thrust / MAX_THRUST;
  hThr.textContent = thrKN.toFixed(1) + ' kN';
  hThr.className   = 'val' + (thrKN > 15 ? ' hot' : '');
  thrustFill.style.width = (thrRatio * 100).toFixed(1) + '%';
  thrustFill.classList.toggle('hot', thrRatio > 0.5);
  tlBar.style.width = (idx / total * 100).toFixed(2) + '%';
}

function updateMissionStatus(f) {
  const alt = Math.max(0, f.y);
  if (alt <= 0.5) {
    missionStatus.textContent = '● LANDED';
    missionStatus.className   = '';
  } else if (alt <= 30 && f.thrust > 500) {
    missionStatus.textContent = '● LANDING BURN';
    missionStatus.className   = 'warn';
  } else {
    missionStatus.textContent = '● NOMINAL';
    missionStatus.className   = '';
  }
}

// ── Camera follow + shake ─────────────────────────────────────────────────────
const _camDest   = new THREE.Vector3();
const _camLook   = new THREE.Vector3();
const _shakeOff  = new THREE.Vector3();

function followCamera(rx, ry, thrustN) {
  const shakeAmp = (thrustN / MAX_THRUST) * 0.35;
  _shakeOff.set(
    (Math.random() - 0.5) * shakeAmp,
    (Math.random() - 0.5) * shakeAmp * 0.5,
    0,
  );
  _camDest.set(rx + _shakeOff.x, Math.max(ry + 48, 55) + _shakeOff.y, 190);
  _camLook.set(rx, Math.max(ry + 8, 8), 0);
  camera.position.lerp(_camDest, 0.05);
  camera.lookAt(_camLook);
}

// ── Playback state ────────────────────────────────────────────────────────────
let traj     = [];
let frameIdx = 0;
let playing  = true;
let speed    = 1;
let lastTs   = 0;
const FRAME_MS = 1000 / 60;
let prevFrameY = 9999;

// ── Controls ──────────────────────────────────────────────────────────────────
document.getElementById('btn-play').addEventListener('click', () => {
  playing = !playing;
  document.getElementById('btn-play').textContent = playing ? 'PAUSE' : 'PLAY';
});
document.getElementById('btn-restart').addEventListener('click', () => {
  frameIdx = 0; playing = true; lastTs = 0; prevFrameY = 9999;
  touchdownDone = false;
  shockwave.visible = false;
  numParts = 0;
  document.getElementById('btn-play').textContent = 'PAUSE';
});

const speedMap = { 'btn-h': 0.5, 'btn-1': 1, 'btn-2': 2, 'btn-4': 4 };
Object.entries(speedMap).forEach(([id, s]) => {
  document.getElementById(id).addEventListener('click', () => {
    speed = s;
    Object.keys(speedMap).forEach(k => document.getElementById(k).classList.remove('active'));
    document.getElementById(id).classList.add('active');
  });
});
document.getElementById('timeline-wrap').addEventListener('click', e => {
  const r = e.currentTarget.getBoundingClientRect();
  frameIdx = Math.floor((e.clientX - r.left) / r.width * traj.length);
});

// ── Flame helpers ─────────────────────────────────────────────────────────────
let flickT = 0;

function updateFlame(thrustN) {
  const ratio = thrustN / MAX_THRUST;
  flameGroup.visible = ratio > 0.005;
  if (!flameGroup.visible) return;
  flickT += 0.3;
  const flicker = 1 + 0.15 * Math.sin(flickT * 11.3) + 0.09 * Math.sin(flickT * 7.1);
  const len = (2.5 + 6 * ratio) * flicker;
  outerFlameMesh.scale.set(0.6 + ratio * 0.5, len, 0.6 + ratio * 0.5);
  innerFlameMesh.scale.set(0.5 + ratio * 0.3, len * 0.6, 0.5 + ratio * 0.3);
  outerFlameMat.opacity = 0.65 + 0.3 * ratio;
  glowSprite.material.opacity = 0.08 + 0.18 * ratio * flicker;
  glowSprite.scale.setScalar(10 + 14 * ratio);
}

// ── Render loop ───────────────────────────────────────────────────────────────
let prevTs = 0;

function renderLoop(ts) {
  requestAnimationFrame(renderLoop);

  if (traj.length === 0) { renderer.render(scene, camera); return; }

  const dtMs  = Math.min(ts - prevTs, 50);   // cap at 50 ms to avoid spiral
  const dtSec = dtMs / 1000;
  prevTs = ts;

  if (playing) {
    if (lastTs === 0) lastTs = ts;
    const advance = Math.floor((ts - lastTs) / FRAME_MS * speed);
    if (advance > 0) { frameIdx = Math.min(frameIdx + advance, traj.length - 1); lastTs = ts; }
  }

  const f  = traj[frameIdx];
  const ry = Math.max(0, f.y);

  // Rocket transform
  rocketGroup.position.set(f.x, ry, 0);
  rocketGroup.rotation.z = f.theta;

  // Landing legs — deploy as altitude decreases
  const deployT = THREE.MathUtils.clamp(
    (LEG_DEPLOY_START - f.y) / (LEG_DEPLOY_START - LEG_DEPLOY_FULL), 0, 1,
  );
  legPivots.forEach(p => { p.rotation.z = deployT * 0.55; });

  // Flame
  updateFlame(f.thrust);

  // Engine light follows nozzle in world space
  const lightY = ry - 2.2 * Math.cos(f.theta);
  const lightX = f.x  - 2.2 * Math.sin(f.theta);
  engineLight.position.set(lightX, lightY, 0);
  engineLight.intensity = (f.thrust / MAX_THRUST) * 6;
  engineLight.distance  = 50 + (f.thrust / MAX_THRUST) * 100;

  // Exhaust particles (emit when thrusting, update every frame)
  if (playing && f.thrust > 500) {
    const emitCount = Math.ceil((f.thrust / MAX_THRUST) * 5);
    emitExhaust(f.thrust, emitCount);
  }
  updateParticles(dtSec * speed);

  // Trajectory trail
  if (trailLine) trailLine.geometry.setDrawRange(0, frameIdx + 1);

  // Touchdown detection
  if (prevFrameY > 0.5 && ry <= 0.5) triggerTouchdown(f.x, ry);
  prevFrameY = ry;

  // Shockwave animation
  if (shockwave.visible) {
    shockwaveScale += 0.8;
    shockwave.scale.set(shockwaveScale, shockwaveScale, 1);
    shockwave.material.opacity = Math.max(0, 1 - shockwaveScale / 25);
    if (shockwaveScale > 25) shockwave.visible = false;
  }

  updateHUD(f, frameIdx, traj.length - 1);
  updateMissionStatus(f);
  followCamera(f.x, ry, f.thrust);

  renderer.render(scene, camera);
}

// ── Fetch trajectory and start ────────────────────────────────────────────────
(async () => {
  try {
    const res = await fetch('/api/trajectory');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    traj = await res.json();

    buildTrail(traj);

    document.getElementById('loading').style.display       = 'none';
    document.getElementById('hud').style.display           = 'block';
    document.getElementById('status-panel').style.display  = 'block';
    document.getElementById('controls').style.display      = 'flex';

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
