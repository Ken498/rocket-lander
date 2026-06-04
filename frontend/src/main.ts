import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// ── Scene ─────────────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080818);
scene.fog = new THREE.FogExp2(0x080818, 0.0015);

// ── Camera ────────────────────────────────────────────────────────────────────
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 5000);
camera.position.set(80, 60, 120);

// ── Renderer ──────────────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;
document.body.appendChild(renderer.domElement);

// ── Lights ────────────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x334466, 1.0));

const sun = new THREE.DirectionalLight(0xfff0dd, 2.5);
sun.position.set(200, 400, 100);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(2048);
sun.shadow.camera.near = 1;
sun.shadow.camera.far = 1500;
[-200, 200].forEach(v => {
  sun.shadow.camera.left = sun.shadow.camera.bottom = v;
  sun.shadow.camera.right = sun.shadow.camera.top = -v;
});
scene.add(sun);

// ── Ground ────────────────────────────────────────────────────────────────────
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(2000, 2000),
  new THREE.MeshLambertMaterial({ color: 0x111a11 })
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

scene.add(new THREE.GridHelper(2000, 100, 0x1a3a1a, 0x111a11));

// ── Landing pad ───────────────────────────────────────────────────────────────
const padMat = new THREE.MeshLambertMaterial({ color: 0xaa8800 });
const pad = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 0.3, 48), padMat);
pad.position.y = 0.15;
pad.receiveShadow = true;
scene.add(pad);

// X markings on pad
const xMat = new THREE.MeshLambertMaterial({ color: 0xff8800 });
[0, 1].forEach(i => {
  const arm = new THREE.Mesh(new THREE.BoxGeometry(14, 0.4, 1.2), xMat);
  arm.position.y = 0.4;
  arm.rotation.y = i * Math.PI / 2;
  scene.add(arm);
});

// ── Rocket model ──────────────────────────────────────────────────────────────
// Group origin = center of mass. Y-axis = body axis (up when theta=0).
// Dimensions match physics/rocket.py RocketParams:
//   body_length = 20 m  →  body spans y = -10 to +10
//   nozzle_arm  = 10 m  →  nozzle exit at y ≈ -12
export const rocketGroup = new THREE.Group();

// Body
const bodyMat = new THREE.MeshPhongMaterial({ color: 0x5a9ae8, shininess: 60 });
const body = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 20, 32), bodyMat);
body.castShadow = true;
rocketGroup.add(body);

// Nose cone — tip at y = +14
const noseMat = new THREE.MeshPhongMaterial({ color: 0xe05050, shininess: 80 });
const nose = new THREE.Mesh(new THREE.ConeGeometry(1.5, 4, 32), noseMat);
nose.position.y = 12;
nose.castShadow = true;
rocketGroup.add(nose);

// Engine nozzle bell
const nozzleMat = new THREE.MeshPhongMaterial({ color: 0x777788, shininess: 120 });
const nozzleBell = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 2.0, 3, 32), nozzleMat);
nozzleBell.position.y = -11.5;
nozzleBell.castShadow = true;
rocketGroup.add(nozzleBell);

// Landing legs (4 legs, splayed outward)
const legMat = new THREE.MeshPhongMaterial({ color: 0x666677 });
for (let i = 0; i < 4; i++) {
  const angle = (i / 4) * Math.PI * 2;
  const leg = new THREE.Mesh(new THREE.BoxGeometry(0.4, 8, 0.4), legMat);
  leg.position.set(Math.sin(angle) * 2.5, -9, Math.cos(angle) * 2.5);
  leg.rotation.z =  Math.sin(angle) * 0.35;
  leg.rotation.x = -Math.cos(angle) * 0.35;
  leg.castShadow = true;
  rocketGroup.add(leg);
}

rocketGroup.position.set(0, 110, 0);   // 110 m above ground to start
scene.add(rocketGroup);

// ── Orbit controls (temporary — will be replaced by tracking camera) ───────
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0, 60, 0);

// ── Resize handler ────────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ── Animation loop ────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
