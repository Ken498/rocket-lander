import * as THREE from 'three';
import { EffectComposer } from '/pp/EffectComposer.js';
import { RenderPass }     from '/pp/RenderPass.js';
import { UnrealBloomPass } from '/pp/UnrealBloomPass.js';

const MAX_THRUST  = 30_000;
const RAD2DEG     = 180 / Math.PI;
const BODY_H      = 20;
const BODY_R_TOP  = 0.5;
const BODY_R_BOT  = 0.7;
const LEG_DEPLOY_START = 30;  // m — legs begin to extend
const LEG_DEPLOY_FULL  = 5;   // m — legs fully extended
const FIN_DEPLOY_START = 150; // m — grid fins begin to deploy
const FIN_DEPLOY_FULL  = 80;  // m — grid fins fully deployed

// ── Renderer ──────────────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
document.body.appendChild(renderer.domElement);

// ── Scene ─────────────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0f1a);
scene.fog = new THREE.Fog(0x0a0f1a, 50, 400);

// ── Camera ────────────────────────────────────────────────────────────────────
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 5000);
camera.position.set(0, 130, 210);
camera.lookAt(0, 90, 0);

// ── Post-processing ───────────────────────────────────────────────────────────
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.6,    // strength
  0.4,    // radius
  0.85,   // luminanceThreshold
);
composer.addPass(bloomPass);

// ── Lights ────────────────────────────────────────────────────────────────────
// Hemisphere ambient — deep sky / dark ground
scene.add(new THREE.HemisphereLight(0x1a1f2e, 0x0a0a0a, 0.3));

// Key light — warm front-left, casts soft shadows
const keyLight = new THREE.DirectionalLight(0xffd9a0, 1.2);
keyLight.position.set(-80, 120, 180);
keyLight.castShadow = true;
keyLight.shadow.mapSize.setScalar(2048);
keyLight.shadow.camera.near = 1;
keyLight.shadow.camera.far  = 800;
keyLight.shadow.camera.left = keyLight.shadow.camera.bottom = -300;
keyLight.shadow.camera.right = keyLight.shadow.camera.top   =  300;
scene.add(keyLight);

// Fill light — cool blue, back-right, low angle
const fillLight = new THREE.DirectionalLight(0x4a6fa5, 0.4);
fillLight.position.set(120, 30, -200);
scene.add(fillLight);

// Engine thrust light — tight pool under nozzle, scales with thrust
const engineLight = new THREE.PointLight(0xff7a40, 0, 40);
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

// ── Ground — flat concrete ────────────────────────────────────────────────────
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(4000, 4000),
  new THREE.MeshLambertMaterial({ color: 0x2a2d33 }),
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// ── Octagonal landing pad — 30 m wide, 0.5 m raised ──────────────────────────
{
  const padMat = new THREE.MeshLambertMaterial({ color: 0x3c3f46 });
  const pad = new THREE.Mesh(new THREE.CylinderGeometry(15, 15, 0.5, 8), padMat);
  pad.position.y = 0.25;
  pad.receiveShadow = true;
  scene.add(pad);

  // Octagonal hazard stripe border — 16 custom quads, 2 per face, yellow/black
  {
    const outerR = 15.0, innerR = 12.8, Y = 0.51;
    const hColors = [0xd4a500, 0x141414];
    for (let s = 0; s < 16; s++) {
      const fI = Math.floor(s / 2), sub = s % 2;
      const a0 = (fI / 8) * Math.PI * 2, a1 = ((fI + 1) / 8) * Math.PI * 2;
      // Outer & inner octagon edge points for this face
      const oA = [outerR * Math.sin(a0), outerR * Math.cos(a0)];
      const oB = [outerR * Math.sin(a1), outerR * Math.cos(a1)];
      const oM = [(oA[0]+oB[0])/2, (oA[1]+oB[1])/2];
      const iA = [innerR * Math.sin(a0), innerR * Math.cos(a0)];
      const iB = [innerR * Math.sin(a1), innerR * Math.cos(a1)];
      const iM = [(iA[0]+iB[0])/2, (iA[1]+iB[1])/2];
      const [ox0,oz0] = sub===0 ? oA : oM;
      const [ox1,oz1] = sub===0 ? oM : oB;
      const [ix0,iz0] = sub===0 ? iA : iM;
      const [ix1,iz1] = sub===0 ? iM : iB;
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(
        new Float32Array([ox0,Y,oz0, ox1,Y,oz1, ix1,Y,iz1, ix0,Y,iz0]), 3));
      geo.setIndex([0,1,2, 0,2,3]);
      geo.computeVertexNormals();
      scene.add(new THREE.Mesh(geo,
        new THREE.MeshBasicMaterial({ color: hColors[s%2], side: THREE.DoubleSide })));
    }
  }

  // Centre crosshair arms
  const crossMat = new THREE.MeshBasicMaterial({ color: 0xc8a000, side: THREE.DoubleSide });
  [0, Math.PI / 2].forEach(rot => {
    const arm = new THREE.Mesh(new THREE.PlaneGeometry(20, 1.0), crossMat);
    arm.rotation.x = -Math.PI / 2;
    arm.rotation.z = rot;
    arm.position.y = 0.52;
    scene.add(arm);
  });

  // Inner aim ring
  const aimRing = new THREE.Mesh(
    new THREE.RingGeometry(3.0, 3.9, 32),
    new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide }),
  );
  aimRing.rotation.x = -Math.PI / 2;
  aimRing.position.y = 0.52;
  scene.add(aimRing);
}

// ── Lightning rod towers — ~80 m, left and right of pad ───────────────────────
{
  const tMat = new THREE.MeshLambertMaterial({ color: 0x5a6880 });

  function buildTower(px, pz) {
    // Each segment: [y_bottom, y_top, half_width_bottom, half_width_top]
    const segs = [
      [0,  16, 3.2, 2.5],
      [16, 32, 2.5, 1.8],
      [32, 46, 1.8, 1.2],
      [46, 58, 1.2, 0.7],
      [58, 68, 0.7, 0.28],
    ];

    segs.forEach(([y0, y1, hw0, hw1]) => {
      const sh = y1 - y0, midHw = (hw0 + hw1) / 2;

      // Four corner columns
      [-1, 1].forEach(sx => [-1, 1].forEach(sz => {
        const col = new THREE.Mesh(new THREE.BoxGeometry(0.38, sh, 0.38), tMat);
        col.position.set(px + sx * midHw, y0 + sh / 2, pz + sz * midHw);
        scene.add(col);
      }));

      // Horizontal ring at top of each segment
      const hw = hw1;
      [-1, 1].forEach(s => {
        const bx = new THREE.Mesh(new THREE.BoxGeometry(hw * 2 + 0.4, 0.28, 0.28), tMat);
        bx.position.set(px, y1, pz + s * hw);
        scene.add(bx);
        const bz = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.28, hw * 2 + 0.4), tMat);
        bz.position.set(px + s * hw, y1, pz);
        scene.add(bz);
      });
    });

    // Tapered spike
    const spike = new THREE.Mesh(new THREE.CylinderGeometry(0, 0.32, 10, 4), tMat);
    spike.position.set(px, 73, pz);
    scene.add(spike);

    // Aviation warning light
    const bulb = new THREE.Mesh(
      new THREE.SphereGeometry(0.55, 6, 4),
      new THREE.MeshBasicMaterial({ color: 0xff2200 }),
    );
    bulb.position.set(px, 78.2, pz);
    scene.add(bulb);
  }

  buildTower(-42, 4);
  buildTower( 42, 4);
}

// ── Fuel storage spheres — three in mid-background ────────────────────────────
{
  const sphereMat = new THREE.MeshLambertMaterial({ color: 0xdde0e4 });
  const bandMat   = new THREE.MeshLambertMaterial({ color: 0xbb2200 });
  const baseMat   = new THREE.MeshLambertMaterial({ color: 0x3a3c40 });

  [[-44, -92], [0, -108], [44, -92]].forEach(([sx, sz]) => {
    // Concrete pedestal
    const base = new THREE.Mesh(new THREE.CylinderGeometry(5.5, 6.5, 3, 8), baseMat);
    base.position.set(sx, 1.5, sz);
    scene.add(base);

    // Low-poly sphere body
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(7.5, 12, 8), sphereMat);
    sphere.position.set(sx, 3 + 7.5, sz);
    scene.add(sphere);

    // Red equatorial band
    const band = new THREE.Mesh(new THREE.TorusGeometry(7.5, 0.9, 4, 16), bandMat);
    band.position.set(sx, 3 + 7.5, sz);
    scene.add(band);
  });
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
    const flood = new THREE.PointLight(0xfff5d0, 4.0, 250);
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

// ── Rocket materials ──────────────────────────────────────────────────────────
const rocketWhiteMat    = new THREE.MeshPhongMaterial({ color: 0xf0f0f0, shininess: 90, specular: 0x333333 });
const interstageGrayMat = new THREE.MeshPhongMaterial({ color: 0xd0d0d0, shininess: 60, specular: 0x222222 });
const engineSectionMat  = new THREE.MeshPhongMaterial({ color: 0x505050, shininess: 60, specular: 0x111111 });
const engineMat         = new THREE.MeshPhongMaterial({ color: 0x303030, shininess: 80, specular: 0x111111 });
const engineBellMat     = new THREE.MeshPhongMaterial({ color: 0x3a2000, emissive: 0x180e00, shininess: 40 });
const legMat            = new THREE.MeshPhongMaterial({ color: 0x2a2a2a, shininess: 30 });
const footMat           = new THREE.MeshPhongMaterial({ color: 0xcccccc, shininess: 50 });
const logoMat           = new THREE.MeshPhongMaterial({ color: 0x1a1a1a, shininess: 10 });

// Grid fin canvas lattice texture
const gridFinMat = new THREE.MeshPhongMaterial({ color: 0x3a3a3a, shininess: 40 });
{
  const c = document.createElement('canvas');
  c.width = 64; c.height = 64;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#2a2a2a';
  ctx.fillRect(0, 0, 64, 64);
  ctx.strokeStyle = '#555555';
  ctx.lineWidth = 1.5;
  for (let i = 0; i <= 8; i++) {
    ctx.beginPath(); ctx.moveTo(i * 8, 0); ctx.lineTo(i * 8, 64); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i * 8); ctx.lineTo(64, i * 8); ctx.stroke();
  }
  const finTex = new THREE.CanvasTexture(c);
  finTex.wrapS = finTex.wrapT = THREE.RepeatWrapping;
  finTex.repeat.set(2, 2);
  gridFinMat.map = finTex;
}

// ── Rocket group ──────────────────────────────────────────────────────────────
// Origin = base of engine section (y=0). Total height 45 m, diameter 3.7 m.
const rocketGroup = new THREE.Group();
scene.add(rocketGroup);

// Engine section (y=0→5, slightly flared skirt, dark grey)
const engineSec = new THREE.Mesh(
  new THREE.CylinderGeometry(1.85, 2.05, 5, 16), engineSectionMat,
);
engineSec.position.y = 2.5;
engineSec.castShadow = true;
rocketGroup.add(engineSec);

// Main fuselage (y=5→40, straight, white)
const fuselage = new THREE.Mesh(
  new THREE.CylinderGeometry(1.85, 1.85, 35, 16), rocketWhiteMat,
);
fuselage.position.y = 22.5;
fuselage.castShadow = true;
rocketGroup.add(fuselage);

// Interstage / nose (y=40→45, tapers to point)
const interstage = new THREE.Mesh(
  new THREE.CylinderGeometry(0.05, 1.85, 5, 16), interstageGrayMat,
);
interstage.position.y = 42.5;
interstage.castShadow = true;
rocketGroup.add(interstage);

// SpaceX logo placeholder — dark rectangle on the fuselage
const logoPlate = new THREE.Mesh(new THREE.BoxGeometry(3, 1, 0.06), logoMat);
logoPlate.position.set(1.87, 25, 0);
rocketGroup.add(logoPlate);

// ── Merlin octaweb engine cluster ─────────────────────────────────────────────
// 1 center + 8 ring engines hanging below the engine section
{
  const ringOffsets = [];
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    ringOffsets.push([Math.cos(a) * 1.0, Math.sin(a) * 1.0]);
  }
  [[0, 0], ...ringOffsets].forEach(([ex, ez]) => {
    // Engine housing cylinder
    const eng = new THREE.Mesh(
      new THREE.CylinderGeometry(0.35, 0.30, 1.5, 8), engineMat,
    );
    eng.position.set(ex, -0.75, ez);
    rocketGroup.add(eng);
    // Bell nozzle with faint orange emissive
    const bell = new THREE.Mesh(
      new THREE.CylinderGeometry(0.50, 0.28, 0.7, 8), engineBellMat,
    );
    bell.position.set(ex, -1.85, ez);
    rocketGroup.add(bell);
  });
}

// ── Grid fins ─────────────────────────────────────────────────────────────────
// 4 fins near top of fuselage; finPivots.rotation.z drives fold/deploy animation.
const finPivots = [];
[0, Math.PI / 2, Math.PI, 3 * Math.PI / 2].forEach(rotY => {
  const pivot = new THREE.Group();
  pivot.rotation.y = rotY;
  pivot.position.y = 38;

  const finBox = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.5, 0.3), gridFinMat);
  finBox.position.x = 2.35;
  pivot.add(finBox);

  rocketGroup.add(pivot);
  finPivots.push(pivot);
});
finPivots.forEach(fp => { fp.rotation.z = Math.PI / 2; }); // start folded upward

// ── Landing legs ─────────────────────────────────────────────────────────────
// Each leg pivots at the body; rotation.z controls deploy angle.
const legPivots = [];
[0, Math.PI / 2, Math.PI, 3 * Math.PI / 2].forEach(rotY => {
  const pivot = new THREE.Group();
  pivot.rotation.y = rotY;
  pivot.position.y = 2.0;

  // Primary strut
  const strut = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.06, 7, 6), legMat);
  strut.position.set(1.8, -3.5, 0);
  strut.rotation.z = -0.18;
  pivot.add(strut);

  // A-frame brace (Falcon 9 style)
  const brace = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 4.5, 6), legMat);
  brace.position.set(2.5, -1.5, 0);
  brace.rotation.z = -0.65;
  pivot.add(brace);

  // Foot pad (light grey contact disk)
  const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.2, 8), footMat);
  foot.position.set(3.8, -7.0, 0);
  pivot.add(foot);

  rocketGroup.add(pivot);
  legPivots.push(pivot);
});

// ── Flame ─────────────────────────────────────────────────────────────────────
const flameGroup = new THREE.Group();
flameGroup.position.y = -2.5;
flameGroup.visible = false;
rocketGroup.add(flameGroup);

// Broad glow disc — blooms around the nozzle cluster
const glowSprite = new THREE.Sprite(new THREE.SpriteMaterial({
  color: 0xff8040,
  transparent: true, opacity: 0.15,
  blending: THREE.AdditiveBlending, depthWrite: false,
}));
glowSprite.scale.set(22, 22, 1);
flameGroup.add(glowSprite);

// Thrust plume anchor — tip fixed at y=0, base extends downward on scale.y
const thrustConeAnchor = new THREE.Group();
flameGroup.add(thrustConeAnchor);

// Unit cone: height=1, tip at y=0 after translate, base at y=-1
// Vertex colours: white-hot at tip → orange-red at base (additive blend)
const _thrustGeo = new THREE.ConeGeometry(2, 1, 16, 6, true);
_thrustGeo.translate(0, -0.5, 0);
{
  const pos = _thrustGeo.attributes.position.array;
  const n   = pos.length / 3;
  const col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const norm = Math.max(0, Math.min(1, -pos[i * 3 + 1])); // 0=tip, 1=base
    col[i * 3]     = 1.0;
    col[i * 3 + 1] = 1.0 - norm * 0.78;
    col[i * 3 + 2] = 0.9 - norm * 0.9;
  }
  _thrustGeo.setAttribute('color', new THREE.BufferAttribute(col, 3));
}
const thrustConeMesh = new THREE.Mesh(_thrustGeo, new THREE.MeshBasicMaterial({
  vertexColors: true, transparent: true, opacity: 0.92,
  blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
}));
thrustConeAnchor.add(thrustConeMesh);

// Outer diffuse plume — slightly wider, orange, softer
const _outerGeo = new THREE.ConeGeometry(3, 1, 12, 4, true);
_outerGeo.translate(0, -0.5, 0);
thrustConeAnchor.add(new THREE.Mesh(_outerGeo, new THREE.MeshBasicMaterial({
  color: 0xff3300, transparent: true, opacity: 0.30,
  blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
})));

// ── Exhaust particles ─────────────────────────────────────────────────────────
const MAX_PARTS = 800;
let numParts = 0;
const px  = new Float32Array(MAX_PARTS), py  = new Float32Array(MAX_PARTS), pz  = new Float32Array(MAX_PARTS);
const pvx = new Float32Array(MAX_PARTS), pvy = new Float32Array(MAX_PARTS), pvz = new Float32Array(MAX_PARTS);
const pLife = new Float32Array(MAX_PARTS), pDecay = new Float32Array(MAX_PARTS);
const pIsDust = new Uint8Array(MAX_PARTS);

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
    pIsDust[idx] = 0;
  }
}

function emitDust(wx, count) {
  for (let i = 0; i < count && numParts < MAX_PARTS; i++) {
    const idx = numParts++;
    const angle = Math.random() * 2 * Math.PI;
    const r = Math.random() * 10;
    px[idx]  = wx + Math.cos(angle) * r;
    py[idx]  = 0.4;
    pz[idx]  = Math.sin(angle) * r;
    pvx[idx] = Math.cos(angle) * (2 + Math.random() * 6);
    pvy[idx] = 0.5 + Math.random() * 2.5;
    pvz[idx] = Math.sin(angle) * (2 + Math.random() * 6);
    pLife[idx]  = 1.0;
    pDecay[idx] = 0.008 + Math.random() * 0.012;
    pIsDust[idx] = 1;
  }
}

function updateParticles(dtSec) {
  let alive = 0;
  for (let i = 0; i < numParts; i++) {
    pLife[i] -= pDecay[i];
    if (pLife[i] <= 0) continue;
    px[i] += pvx[i] * dtSec;  py[i] += pvy[i] * dtSec;  pz[i] += pvz[i] * dtSec;
    pvy[i] += 3 * dtSec;
    pvx[i] *= 0.97;            pvz[i] *= 0.97;
    if (alive !== i) {
      px[alive]=px[i]; py[alive]=py[i]; pz[alive]=pz[i];
      pvx[alive]=pvx[i]; pvy[alive]=pvy[i]; pvz[alive]=pvz[i];
      pLife[alive]=pLife[i]; pDecay[alive]=pDecay[i];
      pIsDust[alive]=pIsDust[i];
    }
    alive++;
  }
  numParts = alive;

  for (let i = 0; i < MAX_PARTS; i++) {
    if (i < numParts) {
      const l = pLife[i], t = 1 - l;
      partPos[i*3]=px[i]; partPos[i*3+1]=py[i]; partPos[i*3+2]=pz[i];
      if (pIsDust[i]) {
        // Sandy/concrete dust: #b8a48a fading out
        partCol[i*3]   = l * 0.72;
        partCol[i*3+1] = l * 0.64;
        partCol[i*3+2] = l * 0.54;
      } else {
        // Exhaust: yellow → orange → dark red
        partCol[i*3]   = l * 1.0;
        partCol[i*3+1] = l * Math.max(0, 0.75 - t * 0.9);
        partCol[i*3+2] = l * Math.max(0, 0.15 - t * 0.2);
      }
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
    pIsDust[idx] = 0;
  }

  // Shockwave ring
  shockwave.visible = true;
  shockwaveScale = 0.1;
}

// Wrap radians to the display range [-180°, +180°]
function normDeg(rad) {
  let d = (rad * RAD2DEG) % 360;
  if (d >  180) d -= 360;
  if (d < -180) d += 360;
  return d;
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
  hTh.textContent  = normDeg(f.theta).toFixed(1) + '°';
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
  const alt      = Math.max(0, f.y);
  const tiltDeg  = Math.abs(normDeg(f.theta));
  if (alt <= 0.5) {
    missionStatus.textContent = '● LANDED';
    missionStatus.className   = '';
  } else if (alt < 50 && tiltDeg > 45) {
    missionStatus.textContent = '● ANOMALY';
    missionStatus.className   = 'warn';
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
  const flicker = 1 + 0.12 * Math.sin(flickT * 11.3) + 0.07 * Math.sin(flickT * 7.1);

  // Plume: 0→12 m, narrows/widens with thrust, flickers
  const plumeLen = 12 * ratio * flicker;
  const plumeWid = (0.65 + ratio * 0.45) * flicker;
  thrustConeAnchor.scale.set(plumeWid, plumeLen, plumeWid);
  thrustConeMesh.material.opacity = 0.75 + 0.2 * ratio;

  // Glow disc scales and brightens with thrust
  glowSprite.material.opacity = 0.08 + 0.32 * ratio * flicker;
  glowSprite.scale.setScalar(14 + 28 * ratio);
}

// ── Render loop ───────────────────────────────────────────────────────────────
let prevTs = 0;

function renderLoop(ts) {
  requestAnimationFrame(renderLoop);

  if (traj.length === 0) { composer.render(); return; }

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

  // Grid fins — deploy before legs (higher altitude)
  const finDeployT = THREE.MathUtils.clamp(
    (FIN_DEPLOY_START - f.y) / (FIN_DEPLOY_START - FIN_DEPLOY_FULL), 0, 1,
  );
  finPivots.forEach(fp => { fp.rotation.z = (1 - finDeployT) * Math.PI / 2; });

  // Flame
  updateFlame(f.thrust);

  // Engine light follows nozzle in world space
  const lightY = ry - 2.5 * Math.cos(f.theta);
  const lightX = f.x  - 2.5 * Math.sin(f.theta);
  engineLight.position.set(lightX, lightY, 0);
  engineLight.intensity = (f.thrust / MAX_THRUST) * 12;

  // Exhaust particles (emit when thrusting, update every frame)
  if (playing && f.thrust > 500) {
    const emitCount = Math.ceil((f.thrust / MAX_THRUST) * 5);
    emitExhaust(f.thrust, emitCount);
    // Dust kickup when close to ground
    if (ry < 30) {
      const dustCount = Math.ceil((1 - ry / 30) * 4);
      emitDust(f.x, dustCount);
    }
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

  composer.render();
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
  composer.setSize(window.innerWidth, window.innerHeight);
  bloomPass.resolution.set(window.innerWidth, window.innerHeight);
});
