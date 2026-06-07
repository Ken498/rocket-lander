import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// ── Environment Setup ─────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87CEEB);
scene.fog = new THREE.FogExp2(0x87CEEB, 0.0012);

const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.1, 5000);
camera.position.set(80, 560, 120);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
document.body.appendChild(renderer.domElement);

// ── Lighting ──────────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x708090, 1.5));

const sun = new THREE.DirectionalLight(0xffffee, 2.5);
sun.position.set(200, 400, 100);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(2048);
sun.shadow.camera.near = 1; sun.shadow.camera.far = 1500;
sun.shadow.camera.left = sun.shadow.camera.bottom = -200;
sun.shadow.camera.right = sun.shadow.camera.top   =  200;
scene.add(sun);

// ── Ground and Landing Pad ────────────────────────────────────────────────────
// 1. The surrounding terrain (scrubland/grass)
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(2000, 2000),
  new THREE.MeshLambertMaterial({ color: 0x3b4d32 })
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

scene.add(new THREE.GridHelper(2000, 100, 0x182418, 0x223022));

// 2. The main concrete landing zone (Zone 1)
const concretePad = new THREE.Mesh(
  new THREE.CylinderGeometry(60, 60, 0.5, 64),
  new THREE.MeshLambertMaterial({ color: 0xaaaaaa })
);
concretePad.position.y = 0.25;
concretePad.receiveShadow = true;
scene.add(concretePad);

// 3. The center target
const centerPad = new THREE.Mesh(
  new THREE.CylinderGeometry(8, 8, 0.6, 48),
  new THREE.MeshLambertMaterial({ color: 0xddcc33 })
);
centerPad.position.y = 0.3;
centerPad.receiveShadow = true;
scene.add(centerPad);

// ── Rocket — Falcon 9 inspired ────────────────────────────────────────────────
const rocketGroup = new THREE.Group();

// Lower body — Scorched/Soot-stained from reentry
const lowerBody = new THREE.Mesh(
  new THREE.CylinderGeometry(1.5, 1.5, 10, 32),
  new THREE.MeshPhongMaterial({ color: 0x333338, shininess: 15 })
);
lowerBody.position.y = -5;
lowerBody.castShadow = true;
rocketGroup.add(lowerBody);

// Upper body — Clean white
const upperBody = new THREE.Mesh(
  new THREE.CylinderGeometry(1.5, 1.5, 10, 32),
  new THREE.MeshPhongMaterial({ color: 0xdedee8, shininess: 70 })
);
upperBody.position.y = 5;
upperBody.castShadow = true;
rocketGroup.add(upperBody);

// Interstage ring — Bold crimson red for visual contrast
const interstage = new THREE.Mesh(
  new THREE.CylinderGeometry(1.56, 1.56, 2, 32),
  new THREE.MeshPhongMaterial({ color: 0xcc3333, shininess: 40 })
);
interstage.position.y = 9;
rocketGroup.add(interstage);

// Nose cone — Match the white upper body
const nose = new THREE.Mesh(
  new THREE.ConeGeometry(1.5, 5, 32),
  new THREE.MeshPhongMaterial({ color: 0xdedee8, shininess: 70 })
);
nose.position.y = 12.5;
nose.castShadow = true;
rocketGroup.add(nose);

// Grid fins — Lighter titanium color
for (let i = 0; i < 4; i++) {
  const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
  const fin = new THREE.Mesh(
    new THREE.BoxGeometry(0.22, 2.5, 2.5),
    new THREE.MeshPhongMaterial({ color: 0x666677, shininess: 50 })
  );
  fin.position.set(Math.sin(a) * 1.78, 8.5, Math.cos(a) * 1.78);
  fin.rotation.y = a;
  fin.castShadow = true;
  rocketGroup.add(fin);
}

// Engine nozzle bell — Brightened metal
const nozzle = new THREE.Mesh(
  new THREE.CylinderGeometry(1.0, 2.2, 3.5, 32),
  new THREE.MeshPhongMaterial({ color: 0x888899, shininess: 120 })
);
nozzle.position.y = -11.75;
nozzle.castShadow = true;
rocketGroup.add(nozzle);

// ── Engine exhaust ────────────────────────────────────────────────────────────
const plumeMat = new THREE.MeshBasicMaterial({
  color: 0xff4400, transparent: true, opacity: 0.55,
  depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
});
const plume = new THREE.Mesh(
  new THREE.ConeGeometry(3.2, 26, 16, 1, true), plumeMat
);
plume.rotation.x = Math.PI;
plume.position.y = -25.5;
plume.visible = false;
rocketGroup.add(plume);

const coreMat = new THREE.MeshBasicMaterial({
  color: 0xffdd55, transparent: true, opacity: 0.85,
  depthWrite: false, blending: THREE.AdditiveBlending,
});
const core = new THREE.Mesh(
  new THREE.ConeGeometry(1.0, 10, 12, 1, true), coreMat
);
core.rotation.x = Math.PI;
core.position.y = -17.5;
core.visible = false;
rocketGroup.add(core);

const engineLight = new THREE.PointLight(0xff7700, 0, 120);
engineLight.position.y = -14;
rocketGroup.add(engineLight);

// ── Deployable landing legs ───────────────────────────────────────────────────
const legPivots: THREE.Group[]   = [];
const legAxes:   THREE.Vector3[] = [];

const LEG_FOLDED_ANGLE   = 0.08;
const LEG_DEPLOYED_ANGLE = 0.65;
const LEG_DEPLOY_ALT     = 250;
let   legProgress        = 0;

for (let i = 0; i < 4; i++) {
  const a = (i / 4) * Math.PI * 2;
  const pivot = new THREE.Group();
  pivot.position.set(Math.sin(a) * 1.5, -10, Math.cos(a) * 1.5);

  const strut = new THREE.Mesh(
    new THREE.CylinderGeometry(0.15, 0.20, 12, 8),
    new THREE.MeshPhongMaterial({ color: 0x111111, shininess: 50 })
  );
  strut.position.y = -6;
  pivot.add(strut);

  const foot = new THREE.Mesh(
    new THREE.CylinderGeometry(0.8, 0.8, 0.4, 8),
    new THREE.MeshPhongMaterial({ color: 0x111111, shininess: 50 })
  );
  foot.position.y = -12.2;
  pivot.add(foot);

  const axis = new THREE.Vector3(-Math.cos(a), 0, Math.sin(a));
  pivot.quaternion.setFromAxisAngle(axis, LEG_FOLDED_ANGLE);
  rocketGroup.add(pivot);
  legPivots.push(pivot);
  legAxes.push(axis);
}

rocketGroup.position.set(0, 500, 0);
scene.add(rocketGroup);

// ── Orbit controls ────────────────────────────────────────────────────────────
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0, 500, 0);

// ── Keyboard + WebSocket ──────────────────────────────────────────────────────
const MAX_THRUST = 20_000;
const MAX_GIMBAL = 0.26;
const keys       = new Set<string>();
let ws:          WebSocket | null = null;
let rocketAlt = 500;
let thrusting = false;

function sendCmd() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({
    thrust:       keys.has('ArrowUp')    ? MAX_THRUST  : 0,
    gimbal_yaw:   keys.has('ArrowLeft')  ?  MAX_GIMBAL :
                  keys.has('ArrowRight') ? -MAX_GIMBAL : 0,
    gimbal_pitch: keys.has('w') || keys.has('W') ?  MAX_GIMBAL :
                  keys.has('s') || keys.has('S') ? -MAX_GIMBAL : 0,
  }));
}

window.addEventListener('keydown', e => {
  if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key)) e.preventDefault();
  keys.add(e.key);
  sendCmd();
});
window.addEventListener('keyup', e => { keys.delete(e.key); sendCmd(); });

function connect() {
  ws = new WebSocket('ws://localhost:8765');
  ws.onopen  = () => { console.log('[ws] connected'); sendCmd(); };
  ws.onclose = () => { console.log('[ws] retrying...'); setTimeout(connect, 2000); };
  ws.onmessage = (e) => {
    const s = JSON.parse(e.data as string);
    rocketGroup.position.set(s.x, s.y, s.z);
    rocketGroup.quaternion.set(s.q1, s.q2, s.q3, s.q0);
    rocketAlt = s.y;
    thrusting = (s.thrust ?? 0) > 0;
  };
}
connect();

window.addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ── Animation loop ────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);

  // Trigger the landing burn automatically when below 150 altitude
  const landingBurnActive = rocketAlt < 150 && rocketAlt > 12;

  // Engine is on if you press Up, if the server says so, OR if doing the automatic landing burn
  const engineOn = thrusting || keys.has('ArrowUp') || landingBurnActive;

  plume.visible = engineOn;
  core.visible  = engineOn;

  if (engineOn) {
    const f = 0.88 + Math.random() * 0.22;
    // Scale the plume dynamically. Bigger burn if high up, throttling down as it lands.
    const throttle = landingBurnActive ? Math.max(0.4, (rocketAlt / 150)) : 1.0;
    plume.scale.setScalar(f * throttle);

    plumeMat.opacity      = 0.40 + Math.random() * 0.25;
    coreMat.opacity       = 0.65 + Math.random() * 0.30;
    engineLight.intensity = (3.0  + Math.random() * 2.5) * throttle;
  } else {
    engineLight.intensity = 0;
  }

  // Leg deployment
  const targetProg = rocketAlt < LEG_DEPLOY_ALT ? 1 : 0;
  legProgress += (targetProg - legProgress) * 0.025;
  for (let i = 0; i < 4; i++) {
    const angle = LEG_FOLDED_ANGLE + (LEG_DEPLOYED_ANGLE - LEG_FOLDED_ANGLE) * legProgress;
    legPivots[i].quaternion.setFromAxisAngle(legAxes[i], angle);
  }

  controls.target.lerp(rocketGroup.position, 0.05);
  controls.update();
  renderer.render(scene, camera);
}
animate();
