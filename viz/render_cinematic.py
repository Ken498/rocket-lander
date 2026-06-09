"""
Cinematic Blender renderer for rocket-lander.
=============================================

Usage
-----
1. VS Code + Blender Development extension:
      Ctrl+Shift+P → "Blender: Run Script"

2. Headless render:
      blender --background --python viz/render_cinematic.py -- --render
      blender --background --python viz/render_cinematic.py -- --render --cycles

3. Custom sim parameters:
      blender --background --python viz/render_cinematic.py -- --x0 80 --y0 1200 --render

Coordinate mapping
------------------
  Physics:  x=East,  y=Up,   z=South
  Blender:  x=East,  y=North, z=Up

  Position:  bx=px,  by=-pz,  bz=py
  Rotation:  q_blender = Q_FRAME @ q_phys @ Q_FRAME.conjugated()
             Q_FRAME = +90 deg around Blender X
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

# ── project root on sys.path ──────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
for _p in (_SCRIPT_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

FPS = 60
ROCKET_RADIUS = 1.0
ROCKET_HEIGHT = 20.0
NOSE_HEIGHT = 5.0
ENGINE_BELL_R1 = 0.4
ENGINE_BELL_R2 = 0.7
ENGINE_BELL_H = 1.5

MAX_THRUST = 50_000.0
MAX_EXHAUST_LENGTH = 32.0
EXHAUST_BASE_DEPTH = 1.0
MAX_ENGINE_LIGHT_W = 8_000.0

# Landing legs
LEG_ANGLES = [45, 135, 225, 315]
LEG_LENGTH = 10.0
LEG_STOWED_ROT = 0.0
LEG_DEPLOYED_ROT = math.radians(115)
LEG_DEPLOY_ALT = 300.0
LEG_DEPLOY_FRAMES = 480

# Falcon 9 paint scheme
F9_WHITE = (0.90, 0.90, 0.92, 1.0)
F9_DARK = (0.14, 0.13, 0.15, 1.0)
F9_INTERSTAGE = (0.55, 0.55, 0.57, 1.0)
BAND_START = 0.38
BAND_END = 0.68
INTER_START = 0.96

_Q_FRAME: Quaternion | None = None


def _q_frame() -> Quaternion:
    global _Q_FRAME
    if _Q_FRAME is None:
        _Q_FRAME = Quaternion(Vector((1.0, 0.0, 0.0)), math.pi / 2)
    return _Q_FRAME


# ══════════════════════════════════════════════════════════════════════════════
# Coordinate helpers
# ══════════════════════════════════════════════════════════════════════════════


def p2b_pos(px: float, py: float, pz: float) -> tuple[float, float, float]:
    return (px, -pz, py)


def p2b_quat(q0: float, q1: float, q2: float, q3: float) -> Quaternion:
    qf = _q_frame()
    qp = Quaternion((q0, q1, q2, q3))
    return qf @ qp @ qf.conjugated()


# ══════════════════════════════════════════════════════════════════════════════
# Scene utilities
# ══════════════════════════════════════════════════════════════════════════════


def clear_scene() -> None:
    for col in [bpy.data.objects, bpy.data.meshes, bpy.data.lights, bpy.data.cameras]:
        for item in list(col):
            col.remove(item, do_unlink=True)


def _new_material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat


def _add_principled(mat: bpy.types.Material) -> bpy.types.Node:
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    out.location = (300, 0)
    bsdf.location = (0, 0)
    return bsdf


# ══════════════════════════════════════════════════════════════════════════════
# Falcon 9 body material
# ══════════════════════════════════════════════════════════════════════════════


def _falcon9_body_material() -> bpy.types.Material:
    """
    Procedural Falcon 9 paint scheme using object-space coordinates.
    Bands (bottom=0 to top=1 normalised):
      0.00-0.38 white, 0.38-0.68 dark, 0.68-0.96 white, 0.96-1.00 interstage
    """
    mat = _new_material("F9Body")
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    mr = nodes.new("ShaderNodeMapRange")
    ramp = nodes.new("ShaderNodeValToRGB")

    links.new(tc.outputs["Object"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    mr.inputs["From Min"].default_value = -ROCKET_HEIGHT / 2
    mr.inputs["From Max"].default_value = ROCKET_HEIGHT / 2
    mr.clamp = True

    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0
    cr.elements[0].color = F9_WHITE
    cr.elements[1].position = 1.0
    cr.elements[1].color = F9_WHITE
    cr.elements.new(BAND_START).color = F9_DARK
    cr.elements.new(BAND_END).color = F9_WHITE
    cr.elements.new(INTER_START).color = F9_INTERSTAGE

    bsdf.inputs["Metallic"].default_value = 0.25
    bsdf.inputs["Roughness"].default_value = 0.40

    for node, x in zip(
        [tc, sep, mr, ramp, bsdf, out],
        [-600, -400, -200, 0, 220, 480],
        strict=False,
    ):
        node.location = (x, 0)

    return mat


# ══════════════════════════════════════════════════════════════════════════════
# Rocket mesh
# ══════════════════════════════════════════════════════════════════════════════


def _build_grid_fins(root: bpy.types.Object) -> None:
    mat = _new_material("GridFin")
    bsdf = _add_principled(mat)
    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.6
    bsdf.inputs["Roughness"].default_value = 0.5

    fin_z = ROCKET_HEIGHT / 2 - 1.5
    fin_radial_w = 1.5
    fin_tangential = 0.15
    fin_height = 1.5

    for angle_deg in [0, 90, 180, 270]:
        a = math.radians(angle_deg)
        cx = (ROCKET_RADIUS + fin_radial_w / 2) * math.cos(a)
        cy = (ROCKET_RADIUS + fin_radial_w / 2) * math.sin(a)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, fin_z))
        fin = bpy.context.active_object
        fin.name = f"GridFin{angle_deg}"
        fin.scale = (fin_radial_w, fin_tangential, fin_height)
        fin.rotation_euler.z = a
        fin.data.materials.append(mat)
        fin.parent = root


def _build_landing_legs(root: bpy.types.Object) -> list[bpy.types.Object]:
    """
    4 landing legs at 45, 135, 225, 315 degrees.
    Each leg: radial_placer (static) -> leg_hinge (animated) -> leg_strut (mesh).
    hinge.rotation_euler.y = 0      -> stowed (points up)
    hinge.rotation_euler.y = 115deg -> deployed (splays outward)
    """
    mat = _new_material("LandingLeg")
    bsdf = _add_principled(mat)
    bsdf.inputs["Base Color"].default_value = (0.68, 0.68, 0.70, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.55

    leg_hinges: list[bpy.types.Object] = []

    for angle_deg in LEG_ANGLES:
        a = math.radians(angle_deg)

        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
        placer = bpy.context.active_object
        placer.name = f"LegPlacer{angle_deg}"
        placer.rotation_euler.z = a
        placer.parent = root

        bpy.ops.object.empty_add(
            type="PLAIN_AXES",
            location=(ROCKET_RADIUS, 0, -ROCKET_HEIGHT / 2),
        )
        hinge = bpy.context.active_object
        hinge.name = f"LegHinge{angle_deg}"
        hinge.rotation_mode = "XYZ"
        hinge.rotation_euler.y = LEG_STOWED_ROT
        hinge.parent = placer

        bpy.ops.mesh.primitive_cone_add(
            radius1=0.12,
            radius2=0.35,
            depth=LEG_LENGTH,
            vertices=8,
            location=(0, 0, LEG_LENGTH / 2),
        )
        strut = bpy.context.active_object
        strut.name = f"LegStrut{angle_deg}"
        strut.data.materials.append(mat)
        strut.parent = hinge

        leg_hinges.append(hinge)

    return leg_hinges


def build_falcon9() -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    """Build Falcon 9 first stage. Returns (rocket_root, leg_hinges)."""
    body_mat = _falcon9_body_material()

    mat_nose = _new_material("F9Nose")
    bsdf_n = _add_principled(mat_nose)
    bsdf_n.inputs["Base Color"].default_value = (0.88, 0.88, 0.90, 1.0)
    bsdf_n.inputs["Metallic"].default_value = 0.15
    bsdf_n.inputs["Roughness"].default_value = 0.50

    mat_bell = _new_material("EngineBell")
    bsdf_b = _add_principled(mat_bell)
    bsdf_b.inputs["Base Color"].default_value = (0.22, 0.18, 0.14, 1.0)
    bsdf_b.inputs["Metallic"].default_value = 1.0
    bsdf_b.inputs["Roughness"].default_value = 0.12

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.active_object
    root.name = "Rocket"

    bpy.ops.mesh.primitive_cylinder_add(
        radius=ROCKET_RADIUS, depth=ROCKET_HEIGHT, vertices=32, location=(0, 0, 0)
    )
    body = bpy.context.active_object
    body.name = "RocketBody"
    body.data.materials.append(body_mat)
    body.parent = root

    bpy.ops.mesh.primitive_cone_add(
        radius1=ROCKET_RADIUS,
        radius2=0.0,
        depth=NOSE_HEIGHT,
        vertices=32,
        location=(0, 0, ROCKET_HEIGHT / 2 + NOSE_HEIGHT / 2),
    )
    nose = bpy.context.active_object
    nose.name = "RocketNose"
    nose.data.materials.append(mat_nose)
    nose.parent = root

    bpy.ops.mesh.primitive_cone_add(
        radius1=ENGINE_BELL_R2,
        radius2=ENGINE_BELL_R1,
        depth=ENGINE_BELL_H,
        vertices=32,
        location=(0, 0, -(ROCKET_HEIGHT / 2 + ENGINE_BELL_H / 2)),
    )
    bell = bpy.context.active_object
    bell.name = "EngineBell"
    bell.data.materials.append(mat_bell)
    bell.parent = root

    _build_grid_fins(root)
    leg_hinges = _build_landing_legs(root)

    return root, leg_hinges


# ══════════════════════════════════════════════════════════════════════════════
# Exhaust plume
# ══════════════════════════════════════════════════════════════════════════════


def build_exhaust(root: bpy.types.Object) -> tuple[bpy.types.Object, bpy.types.Node]:
    """
    Two-layer exhaust: orange outer plume + white-yellow inner core.
    Inner core is parented to outer so it animates automatically.
    Returns (exhaust_outer, emit_node).
    """
    mat_outer = _new_material("ExhaustOuter")
    n_outer = mat_outer.node_tree.nodes
    lnk_outer = mat_outer.node_tree.links
    out_n = n_outer.new("ShaderNodeOutputMaterial")
    emit = n_outer.new("ShaderNodeEmission")
    emit.name = "ExhaustEmit"
    emit.inputs["Color"].default_value = (1.0, 0.38, 0.05, 1.0)
    emit.inputs["Strength"].default_value = 0.0
    lnk_outer.new(emit.outputs["Emission"], out_n.inputs["Surface"])

    nozzle_z = -(ROCKET_HEIGHT / 2 + ENGINE_BELL_H)

    bpy.ops.mesh.primitive_cone_add(
        radius1=0.0,
        radius2=ENGINE_BELL_R2,
        depth=EXHAUST_BASE_DEPTH,
        vertices=32,
        location=(0, 0, nozzle_z - EXHAUST_BASE_DEPTH / 2),
    )
    exhaust = bpy.context.active_object
    exhaust.name = "ExhaustPlume"
    exhaust.data.materials.append(mat_outer)
    exhaust.parent = root
    exhaust.scale = (0.0, 0.0, 0.0)

    # Inner hot core — parented to outer, scales with it automatically
    mat_core = _new_material("ExhaustCore")
    nc = mat_core.node_tree.nodes
    lc = mat_core.node_tree.links
    out_c = nc.new("ShaderNodeOutputMaterial")
    emit_c = nc.new("ShaderNodeEmission")
    emit_c.inputs["Color"].default_value = (1.0, 0.95, 0.72, 1.0)
    emit_c.inputs["Strength"].default_value = 28.0
    lc.new(emit_c.outputs["Emission"], out_c.inputs["Surface"])

    bpy.ops.mesh.primitive_cone_add(
        radius1=0.0,
        radius2=ENGINE_BELL_R2 * 0.45,
        depth=EXHAUST_BASE_DEPTH,
        vertices=24,
        location=(0, 0, 0),
    )
    core = bpy.context.active_object
    core.name = "ExhaustCore"
    core.data.materials.append(mat_core)
    core.parent = exhaust
    core.scale = (1.0, 1.0, 0.80)

    return exhaust, emit


def build_engine_light(root: bpy.types.Object) -> bpy.types.Object:
    nozzle_z = -(ROCKET_HEIGHT / 2 + ENGINE_BELL_H)
    bpy.ops.object.light_add(type="POINT", location=(0, 0, nozzle_z - 2))
    light = bpy.context.active_object
    light.name = "EngineLight"
    light.data.color = (1.0, 0.55, 0.12)
    light.data.energy = 0.0
    light.data.shadow_soft_size = 3.0
    light.parent = root
    return light


# ══════════════════════════════════════════════════════════════════════════════
# Ground + environment
# ══════════════════════════════════════════════════════════════════════════════


def build_ground() -> None:
    """
    Procedural Florida coastal landscape.
    One 12km terrain plane with noise-driven grass/water/dirt zones,
    a raised concrete landing pad with rings and X markings,
    and 16 warm amber perimeter flood lights.
    """

    # Assuming you are working with an active object's material
    mat = bpy.context.active_object.active_material

    # Ensure the material is actually set to use nodes
    mat.use_nodes = True

    # DEFINE 'nodes' before you use it
    nodes = mat.node_tree.nodes

    # Now you can actually add your texture node
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(_SCRIPT_DIR, "assets", "launch_site.jpg"))
    tex.extension = "EXTEND"

    # ── 2. Ocean ─────────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_plane_add(size=8000, location=(0, -3000, -2.0))
    ocean = bpy.context.active_object
    ocean.name = "Ocean"
    mat_o = _new_material("OceanMat")
    bsdf_o = _add_principled(mat_o)
    bsdf_o.inputs["Base Color"].default_value = (0.03, 0.08, 0.18, 1.0)
    bsdf_o.inputs["Roughness"].default_value = 0.04
    bsdf_o.inputs["Metallic"].default_value = 0.0
    bsdf_o.inputs["Specular IOR Level"].default_value = 1.0
    ocean.data.materials.append(mat_o)

    # ── 3. Landing pad ───────────────────────────────────────────────────
    mat_conc = _new_material("Concrete")
    bsdf_c = _add_principled(mat_conc)
    bsdf_c.inputs["Base Color"].default_value = (0.42, 0.41, 0.39, 1.0)
    bsdf_c.inputs["Roughness"].default_value = 0.90

    mat_white = _new_material("PadWhite")
    bsdf_w = _add_principled(mat_white)
    bsdf_w.inputs["Base Color"].default_value = (0.88, 0.87, 0.84, 1.0)
    bsdf_w.inputs["Roughness"].default_value = 0.75

    mat_yellow = _new_material("PadYellow")
    bsdf_y = _add_principled(mat_yellow)
    bsdf_y.inputs["Base Color"].default_value = (0.85, 0.62, 0.04, 1.0)
    bsdf_y.inputs["Roughness"].default_value = 0.70

    bpy.ops.mesh.primitive_cylinder_add(radius=21, depth=1.4, vertices=64, location=(0, 0, -0.7))
    bpy.context.active_object.name = "PadBase"
    bpy.context.active_object.data.materials.append(mat_conc)

    bpy.ops.mesh.primitive_circle_add(radius=20, fill_type="NGON", location=(0, 0, 0.01))
    bpy.context.active_object.name = "PadSurface"
    bpy.context.active_object.data.materials.append(mat_conc)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=15.0,
        minor_radius=0.55,
        major_segments=64,
        minor_segments=8,
        location=(0, 0, 0.02),
    )
    bpy.context.active_object.name = "RingOuter"
    bpy.context.active_object.data.materials.append(mat_white)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=10.5,
        minor_radius=0.35,
        major_segments=64,
        minor_segments=8,
        location=(0, 0, 0.02),
    )
    bpy.context.active_object.name = "RingMid"
    bpy.context.active_object.data.materials.append(mat_white)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=7.0,
        minor_radius=0.45,
        major_segments=64,
        minor_segments=8,
        location=(0, 0, 0.02),
    )
    bpy.context.active_object.name = "RingInner"
    bpy.context.active_object.data.materials.append(mat_yellow)

    for angle_deg in [45, -45]:
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0.02))
        bar = bpy.context.active_object
        bar.name = f"XBar{angle_deg}"
        bar.scale = (26.0, 1.3, 1.0)
        bar.rotation_euler.z = math.radians(angle_deg)
        bar.data.materials.append(mat_white)

    bpy.ops.mesh.primitive_plane_add(size=3.8, location=(0, 0, 0.02))
    bpy.context.active_object.name = "PadCentre"
    bpy.context.active_object.data.materials.append(mat_white)

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, -600, 0.01))
    road = bpy.context.active_object
    road.name = "Road"
    road.scale = (5.0, 700.0, 1.0)
    road.data.materials.append(mat_conc)

    # ── 4. Perimeter flood lights ─────────────────────────────────────────
    mat_fix = _new_material("FixtureGlow")
    nf = mat_fix.node_tree.nodes
    lf = mat_fix.node_tree.links
    out_f = nf.new("ShaderNodeOutputMaterial")
    emit_f = nf.new("ShaderNodeEmission")
    emit_f.inputs["Color"].default_value = (1.0, 0.78, 0.38, 1.0)
    emit_f.inputs["Strength"].default_value = 8.0
    lf.new(emit_f.outputs["Emission"], out_f.inputs["Surface"])

    num_lights = 16
    light_r = 17.5

    for i in range(num_lights):
        a = 2 * math.pi * i / num_lights
        lx = light_r * math.cos(a)
        ly = light_r * math.sin(a)

        bpy.ops.object.light_add(type="POINT", location=(lx, ly, 0.5))
        pl = bpy.context.active_object
        pl.name = f"PerimLight{i:02d}"
        pl.data.color = (1.0, 0.72, 0.28)
        pl.data.energy = 600.0
        pl.data.shadow_soft_size = 0.10

        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.18, segments=8, ring_count=6, location=(lx, ly, 0.5)
        )
        fix = bpy.context.active_object
        fix.name = f"Fixture{i:02d}"
        fix.data.materials.append(mat_fix)

    print("[render_cinematic] Florida landscape + landing pad built.")


# ══════════════════════════════════════════════════════════════════════════════
# World + lighting
# ══════════════════════════════════════════════════════════════════════════════


def build_world() -> None:
    """Physically-based sky using Blender 5.x Sky Texture (Multiple Scattering)."""
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    sky = nodes.new("ShaderNodeTexSky")

    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(6)
    sky.sun_rotation = math.radians(220)

    links.new(sky.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])
    bg.inputs["Strength"].default_value = 1.0

    sky.location = (-300, 0)
    bg.location = (0, 0)
    out.location = (250, 0)


def build_sun() -> None:
    """Golden hour key light + cool sky fill."""
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 200))
    sun = bpy.context.active_object
    sun.name = "SunKey"
    sun.rotation_euler = (math.radians(84), 0.0, math.radians(220))
    sun.data.energy = 4.0
    sun.data.angle = math.radians(0.5)
    sun.data.color = (1.0, 0.82, 0.58)

    bpy.ops.object.light_add(type="SUN", location=(0, 0, 200))
    fill = bpy.context.active_object
    fill.name = "SkyFill"
    fill.rotation_euler = (math.radians(25), 0.0, math.radians(40))
    fill.data.energy = 0.8
    fill.data.angle = math.radians(120)
    fill.data.color = (0.55, 0.70, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# Camera
# ══════════════════════════════════════════════════════════════════════════════


def build_camera(rocket_root: bpy.types.Object) -> bpy.types.Object:
    """Elevated tracking camera — shows pad + terrain + sky."""
    bpy.ops.object.camera_add(location=(80, -150, 250))
    cam = bpy.context.active_object
    cam.name = "CinematicCamera"
    cam.data.lens = 35
    cam.data.clip_end = 20_000

    con = cam.constraints.new(type="TRACK_TO")
    con.target = rocket_root
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    bpy.context.scene.camera = cam
    return cam


# ══════════════════════════════════════════════════════════════════════════════
# Viewport helper — forces rendered mode so you see results immediately
# ══════════════════════════════════════════════════════════════════════════════


def force_viewport_rendered() -> None:
    """Switch every 3D viewport to Rendered mode and fix clip distance."""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.clip_end = 20000.0
                    space.shading.type = "RENDERED"
                    space.shading.use_scene_lights = True
                    space.shading.use_scene_world = True
                    space.overlay.show_overlays = False  # hide grid


# ══════════════════════════════════════════════════════════════════════════════
# Animation
# ══════════════════════════════════════════════════════════════════════════════


def animate(
    trajectory: list[dict],
    rocket_root: bpy.types.Object,
    exhaust: bpy.types.Object,
    emit_node: bpy.types.Node,
    engine_light: bpy.types.Object,
    frame_step: int = 1,
) -> None:
    rocket_root.rotation_mode = "QUATERNION"
    nozzle_z = -(ROCKET_HEIGHT / 2 + ENGINE_BELL_H)
    total = len(trajectory)

    print(f"[render_cinematic] Keying {total} frames (step={frame_step}) ...")

    for i, frame in enumerate(trajectory):
        if i % frame_step != 0 and i != total - 1:
            continue

        bf = i + 1

        rocket_root.location = p2b_pos(frame["x"], frame["y"], frame["z"])
        rocket_root.keyframe_insert("location", frame=bf)

        rocket_root.rotation_quaternion = p2b_quat(
            frame["q0"], frame["q1"], frame["q2"], frame["q3"]
        )
        rocket_root.keyframe_insert("rotation_quaternion", frame=bf)

        thrust_norm = min(frame["thrust"] / MAX_THRUST, 1.0)

        if thrust_norm < 0.01:
            exhaust.scale = (0.0, 0.0, 0.0)
            exhaust.location = (0.0, 0.0, nozzle_z - EXHAUST_BASE_DEPTH / 2)
            emit_node.inputs["Strength"].default_value = 0.0
            engine_light.data.energy = 0.0
        else:
            scale_z = thrust_norm * (MAX_EXHAUST_LENGTH / EXHAUST_BASE_DEPTH)
            scale_xy = 0.35 + 0.65 * thrust_norm
            exhaust.scale = (scale_xy, scale_xy, scale_z)
            exhaust.location = (0.0, 0.0, nozzle_z - EXHAUST_BASE_DEPTH / 2 * scale_z)
            emit_node.inputs["Strength"].default_value = 4.0 + thrust_norm * 18.0
            engine_light.data.energy = thrust_norm * MAX_ENGINE_LIGHT_W

        exhaust.keyframe_insert("scale", frame=bf)
        exhaust.keyframe_insert("location", frame=bf)
        emit_node.inputs["Strength"].keyframe_insert("default_value", frame=bf)
        engine_light.data.keyframe_insert("energy", frame=bf)

        if i % 1000 == 0:
            print(
                f"  ... {i}/{total}  alt={frame['altitude']:.0f} m  thrust={frame['thrust']:.0f} N"
            )

    print("[render_cinematic] Keyframing complete.")


def _animate_legs(
    leg_hinges: list[bpy.types.Object],
    trajectory: list[dict],
) -> None:
    deploy_idx = next(
        (i for i, f in enumerate(trajectory) if f["altitude"] < LEG_DEPLOY_ALT),
        len(trajectory) - 1,
    )
    deploy_bf = deploy_idx + 1
    deployed_bf = min(deploy_bf + LEG_DEPLOY_FRAMES, len(trajectory))

    for hinge in leg_hinges:
        hinge.rotation_mode = "XYZ"
        hinge.rotation_euler.y = LEG_STOWED_ROT
        hinge.keyframe_insert("rotation_euler", frame=1)
        hinge.rotation_euler.y = LEG_STOWED_ROT
        hinge.keyframe_insert("rotation_euler", frame=max(1, deploy_bf - 1))
        hinge.rotation_euler.y = LEG_DEPLOYED_ROT
        hinge.keyframe_insert("rotation_euler", frame=deployed_bf)

    print(
        f"[render_cinematic] Legs deploy frames {deploy_bf}-{deployed_bf} "
        f"(alt ~{trajectory[deploy_idx]['altitude']:.0f} m)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Render settings
# ══════════════════════════════════════════════════════════════════════════════


def setup_render(
    total_frames: int,
    output_dir: str,
    use_cycles: bool = False,
    resolution: tuple[int, int] = (1920, 1080),
) -> None:
    scene = bpy.context.scene
    render = scene.render

    render.resolution_x, render.resolution_y = resolution
    render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.frame_current = 1

    render.image_settings.file_format = "PNG"
    render.filepath = os.path.join(output_dir, "frame_####")

    if use_cycles:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 128
        scene.cycles.use_denoising = True
        print("[render_cinematic] Renderer: Cycles (128 samples + denoising)")
    else:
        for engine_id in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = engine_id
                break
            except TypeError:
                continue
        try:
            scene.eevee.taa_render_samples = 64
        except AttributeError:
            pass
        print(f"[render_cinematic] Renderer: {scene.render.engine}")

    _setup_bloom(scene)


def _setup_bloom(scene: bpy.types.Scene) -> None:
    try:
        scene.use_nodes = True
        tree = scene.node_tree
        nodes = tree.nodes
        links = tree.links

        rl = next((n for n in nodes if n.type == "R_LAYERS"), None)
        comp = next((n for n in nodes if n.type == "COMPOSITE"), None)
        if rl is None:
            rl = nodes.new("CompositorNodeRLayers")
            rl.location = (-400, 0)
        if comp is None:
            comp = nodes.new("CompositorNodeComposite")
            comp.location = (600, 0)

        for lnk in list(links):
            if lnk.from_node == rl and lnk.to_node == comp:
                links.remove(lnk)

        glare = nodes.new("CompositorNodeGlare")
        glare.location = (100, 0)
        glare.glare_type = "BLOOM"
        glare.threshold = 0.85
        glare.size = 8
        glare.mix = 0.25

        links.new(rl.outputs["Image"], glare.inputs["Image"])
        links.new(glare.outputs["Image"], comp.inputs["Image"])
        print("[render_cinematic] Compositor bloom enabled.")

    except Exception as exc:  # noqa: BLE001
        print(f"[render_cinematic] Could not set up compositor bloom: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════


def _parse_args() -> dict:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []

    parser = argparse.ArgumentParser(prog="render_cinematic")
    parser.add_argument("--x0", type=float, default=50.0)
    parser.add_argument("--y0", type=float, default=1000.0)
    parser.add_argument("--z0", type=float, default=0.0)
    parser.add_argument("--output", type=str, default="/tmp/rocket_frames")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--cycles", action="store_true")
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--trajectory", type=str, default="trajectory.json")
    return vars(parser.parse_args(argv))


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    args = _parse_args()

    traj_path = args["trajectory"]
    print(f"[render_cinematic] Loading trajectory from {traj_path} ...")
    with open(traj_path) as f:
        trajectory = json.load(f)
    final = trajectory[-1]
    print(
        f"[render_cinematic] {len(trajectory)} frames  |  "
        f"touchdown x={final['x']:.2f} m  z={final['z']:.2f} m  vy={final['vy']:.2f} m/s"
    )

    clear_scene()
    build_world()
    build_sun()
    build_ground()

    rocket_root, leg_hinges = build_falcon9()
    exhaust, emit_node = build_exhaust(rocket_root)
    engine_light = build_engine_light(rocket_root)
    build_camera(rocket_root)

    animate(trajectory, rocket_root, exhaust, emit_node, engine_light, frame_step=args["step"])
    _animate_legs(leg_hinges, trajectory)

    os.makedirs(args["output"], exist_ok=True)
    setup_render(
        total_frames=len(trajectory),
        output_dir=args["output"],
        use_cycles=args["cycles"],
        resolution=(args["width"], args["height"]),
    )

    # Auto-switch viewport to rendered mode and hide grid overlay
    force_viewport_rendered()

    if args["render"]:
        print(f"[render_cinematic] Rendering {len(trajectory)} frames -> {args['output']}")
        bpy.ops.render.render(animation=True)
        print("[render_cinematic] Done.")
    else:
        print("[render_cinematic] Scene ready. Press Space to preview.")


main()
