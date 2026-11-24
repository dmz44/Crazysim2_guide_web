#!/usr/bin/env python3
"""
scan_to_sim.py — turn a 3D scan (ZED2 / ZEDfu / phone LiDAR / photogrammetry)
into simulator assets for CrazySim (MuJoCo and Gazebo).

What it does
------------
1. Loads a mesh (.obj, .ply, .stl, .glb). A PLY point cloud with no faces is
   meshed with Poisson reconstruction if Open3D is installed.
2. Re-orients it so +Z is up (``--up-axis``), applies ``--scale``, ``--yaw``
   and ``--offset``, and by default drops it so its lowest point sits on z=0.
3. Optionally decimates it to ``--target-faces`` triangles.
4. Builds collision geometry (``--collision``):
     none       visual only — drones fly through it, but range sensors and the
                AI-deck camera still see it
     hull       one convex hull (fast, good for compact objects)
     decompose  convex decomposition with CoACD (good for chairs, rooms, ...)
5. Writes:
     <out>/<name>/meshes/visual.obj (+ texture), collision_XX.obj
     <out>/<name>/<name>_mujoco.xml   MuJoCo <include> snippet
     <out>/scene_<name>.xml           ready-to-run MuJoCo scene (use with -s)
     <out>/<name>/model.sdf + model.config   Gazebo model (model://<name>)

Example
-------
    python3 scan_to_sim.py scan.obj --name lab_table --target-faces 20000 \
        --collision decompose --out ~/my_code/scenes

    bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh \
        -s ~/my_code/scenes/scene_lab_table.xml

Requires: numpy, trimesh. Optional: fast_simplification (decimation),
coacd (decomposition), open3d (point clouds), Pillow (textures).
"""

import argparse
import math
import os
import shutil
import sys
from xml.sax.saxutils import quoteattr

import numpy as np

try:
    import trimesh
except ImportError:
    sys.exit('trimesh is required:  pip install trimesh')


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_geometry(path):
    """Load a mesh; mesh PLY point clouds with Poisson if possible."""
    geom = trimesh.load(path, process=False)

    if isinstance(geom, trimesh.Scene):
        if not geom.geometry:
            sys.exit(f'{path}: file contains no geometry')
        # Bake node transforms and merge into one mesh.
        geom = geom.to_geometry() if hasattr(geom, 'to_geometry') else geom.dump(concatenate=True)

    if isinstance(geom, trimesh.PointCloud) or len(getattr(geom, 'faces', [])) == 0:
        return poisson_from_points(path)

    return geom


def poisson_from_points(path):
    try:
        import open3d as o3d
    except ImportError:
        sys.exit(
            f'{path} is a point cloud (no faces). Either export a *mesh* from '
            'the ZED (spatial mapping -> MESH, or ZEDfu "Mesh" mode), or '
            'install open3d so this script can mesh it:  pip install open3d')
    print('[scan_to_sim] point cloud detected - running Poisson reconstruction')
    pcd = o3d.io.read_point_cloud(path)
    pcd.estimate_normals()
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
    dens = np.asarray(dens)
    mesh.remove_vertices_by_mask(dens < np.quantile(dens, 0.05))  # trim bubbles
    v = np.asarray(mesh.vertices)
    f = np.asarray(mesh.triangles)
    colors = np.asarray(mesh.vertex_colors)
    m = trimesh.Trimesh(v, f, process=False)
    if len(colors):
        m.visual.vertex_colors = (np.clip(colors, 0, 1) * 255).astype(np.uint8)
    return m


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

_UP = {
    'z': np.eye(3),
    '-z': np.diag([1.0, -1.0, -1.0]),
    # rotate +Y onto +Z (rotation of +90 deg about X)
    'y': np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float),
    # rotate -Y onto +Z (ZED "IMAGE" frame is y-down)
    '-y': np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float),
    'x': np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], dtype=float),
    '-x': np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=float),
}


def transform(mesh, up_axis, scale, yaw_deg, offset, floor, center):
    T = np.eye(4)
    T[:3, :3] = _UP[up_axis] * scale
    mesh.apply_transform(T)

    if yaw_deg:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(yaw_deg), [0, 0, 1]))

    lo, hi = mesh.bounds
    shift = np.zeros(3)
    if center:
        shift[:2] = -(lo[:2] + hi[:2]) / 2.0
    if floor:
        shift[2] = -lo[2]
    shift += np.asarray(offset, dtype=float)
    mesh.apply_translation(shift)
    return mesh


def decimate(mesh, target_faces):
    if target_faces <= 0 or len(mesh.faces) <= target_faces:
        return mesh
    has_uv = (getattr(mesh.visual, 'kind', None) == 'texture'
              and getattr(mesh.visual, 'uv', None) is not None)
    if has_uv:
        print('[scan_to_sim] note: decimation drops UV texture coordinates; '
              'the mesh will use its average colour instead. Use a lower '
              'mapping resolution on the ZED to keep textures.')
    try:
        out = mesh.simplify_quadric_decimation(face_count=target_faces)
    except TypeError:
        out = mesh.simplify_quadric_decimation(target_faces)
    except Exception as exc:  # missing fast_simplification, etc.
        print(f'[scan_to_sim] decimation skipped ({exc}). '
              'pip install fast_simplification')
        return mesh
    print(f'[scan_to_sim] decimated {len(mesh.faces)} -> {len(out.faces)} faces')
    return out


def mean_rgba(mesh):
    vis = mesh.visual
    try:
        if vis.kind == 'vertex' and len(vis.vertex_colors):
            c = np.asarray(vis.vertex_colors, dtype=float).mean(axis=0) / 255.0
            return [float(c[0]), float(c[1]), float(c[2]), 1.0]
        if vis.kind == 'texture':
            mat = vis.material
            img = getattr(mat, 'image', None) or getattr(mat, 'baseColorTexture', None)
            if img is not None:
                c = np.asarray(img.convert('RGB'), dtype=float).reshape(-1, 3).mean(axis=0) / 255.0
                return [float(c[0]), float(c[1]), float(c[2]), 1.0]
    except Exception:
        pass
    return [0.7, 0.7, 0.7, 1.0]


# ---------------------------------------------------------------------------
# Collision
# ---------------------------------------------------------------------------

def build_collision(mesh, mode, threshold, max_hulls):
    if mode == 'none':
        return []
    if mode == 'hull':
        return [mesh.convex_hull]
    try:
        import coacd
    except ImportError:
        print('[scan_to_sim] coacd not installed - falling back to one convex '
              'hull. pip install coacd')
        return [mesh.convex_hull]
    print('[scan_to_sim] running CoACD convex decomposition (may take a while)')
    cm = coacd.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces))
    parts = coacd.run_coacd(cm, threshold=threshold, max_convex_hull=max_hulls)
    hulls = [trimesh.Trimesh(v, f, process=True) for v, f in parts]
    print(f'[scan_to_sim] {len(hulls)} convex parts')
    return hulls


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def export_visual(mesh, mesh_dir):
    """Export visual.obj; return texture file name (or None)."""
    path = os.path.join(mesh_dir, 'visual.obj')
    tex_name = None
    if getattr(mesh.visual, 'kind', None) == 'texture':
        img = getattr(mesh.visual.material, 'image', None)
        if img is None:
            img = getattr(mesh.visual.material, 'baseColorTexture', None)
        if img is not None:
            tex_name = 'visual_texture.png'
            img.convert('RGB').save(os.path.join(mesh_dir, tex_name))
    mesh.export(path, include_texture=tex_name is not None)
    return tex_name


def inertial_xml(mesh, mass):
    """<inertial> for a free body. CrazySim scenes use inertiafromgeom="false",
    so MuJoCo will NOT compute inertia from geoms — we must write it."""
    com, I = mass_properties(mesh, mass)
    full = ' '.join(f'{v:.6g}' for v in (I[0, 0], I[1, 1], I[2, 2],
                                          I[0, 1], I[0, 2], I[1, 2]))
    return (f'      <inertial pos="{com[0]:.4f} {com[1]:.4f} {com[2]:.4f}" '
            f'mass="{mass:g}" fullinertia="{full}"/>')


def mujoco_snippet(name, n_hulls, tex, rgba, mass, pos, rel, inertial=None):
    """MuJoCo file that can be <include>d into a scene.

    ``rel`` is the mesh folder relative to the *including* scene file.
    """
    a = []
    a.append(f'    <mesh name="{name}_visual" file="{rel}/visual.obj"/>')
    for i in range(n_hulls):
        a.append(f'    <mesh name="{name}_col{i:02d}" file="{rel}/collision_{i:02d}.obj"/>')
    if tex:
        a.append(f'    <texture name="{name}_tex" type="2d" file="{rel}/{tex}"/>')
        a.append(f'    <material name="{name}_mat" texture="{name}_tex"/>')
    else:
        a.append(f'    <material name="{name}_mat" rgba="{" ".join(f"{c:.3f}" for c in rgba)}"/>')

    b = []
    dynamic = mass is not None
    b.append(f'    <body name="{name}" pos="{pos[0]:g} {pos[1]:g} {pos[2]:g}">')
    if dynamic:
        b.append('      <freejoint/>')
        b.append(inertial)
    # Visual geom: group 2, no contacts. Range sensors and cameras still see it.
    b.append(f'      <geom name="{name}_visual" type="mesh" mesh="{name}_visual" '
             f'material="{name}_mat" contype="0" conaffinity="0" group="2"'
             + '/>')
    for i in range(n_hulls):
        b.append(f'      <geom name="{name}_col{i:02d}" type="mesh" mesh="{name}_col{i:02d}" '
                 f'group="3" rgba="1 0.3 0.3 0.4" contype="1" conaffinity="1"/>')
    b.append('    </body>')

    return ('<mujoco>\n  <asset>\n' + '\n'.join(a) + '\n  </asset>\n'
            '  <worldbody>\n' + '\n'.join(b) + '\n  </worldbody>\n</mujoco>\n')


SCENE_TEMPLATE = """<mujoco model="CrazySim scene with {name}">
  <!-- Generated by scan_to_sim.py. Physics options match CrazySim's scene.xml. -->
  <option integrator="RK4" density="1.225" viscosity="1.8e-5" timestep="0.001"/>
  <compiler inertiafromgeom="false" autolimits="true"/>
  <statistic center="0 0 1" extent="3"/>

  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.5 0.5 0.5" specular="0 0 0"/>
    <global azimuth="0" elevation="-20" ellipsoidinertia="true" offwidth="1280" offheight="720"/>
  </visual>

  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0"
             width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge"
             rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
             markrgb="0.8 0.8 0.8" width="512" height="512"/>
    <material name="groundplane" texture="groundplane" texuniform="true"
              texrepeat="2 2" reflectance="0.2"/>
  </asset>

  <worldbody>
    <light pos="0 0 3" dir="0 0 -1" directional="true"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="groundplane"/>
  </worldbody>

  <include file="{name}/{name}_mujoco.xml"/>
</mujoco>
"""


def mass_properties(mesh, mass):
    """(com, 3x3 inertia about com) of the convex hull scaled to `mass`."""
    hull = mesh.convex_hull
    hull.density = mass / max(hull.volume, 1e-9)
    I = hull.moment_inertia
    if not np.all(np.diag(I) > 0):
        I = np.eye(3) * 1e-4
    return hull.center_mass, I


def gazebo_model(name, n_hulls, rgba, mass, static, textured=False, mprops=None):
    def mesh_geom(file):
        return (f'<geometry><mesh><uri>model://{name}/meshes/{file}</uri>'
                '</mesh></geometry>')

    cols = '\n'.join(
        f'      <collision name="col{i:02d}">{mesh_geom(f"collision_{i:02d}.obj")}</collision>'
        for i in range(n_hulls))
    inertial = ''
    if not static and mass is not None:
        com, I = mprops
        inertial = (f'      <inertial><pose>{com[0]:.4f} {com[1]:.4f} {com[2]:.4f} 0 0 0</pose>'
                    f'<mass>{mass:g}</mass><inertia>'
                    f'<ixx>{I[0, 0]:.6g}</ixx><ixy>{I[0, 1]:.6g}</ixy><ixz>{I[0, 2]:.6g}</ixz>'
                    f'<iyy>{I[1, 1]:.6g}</iyy><iyz>{I[1, 2]:.6g}</iyz><izz>{I[2, 2]:.6g}</izz>'
                    '</inertia></inertial>\n')
    r, g, b, a = rgba
    # Textured OBJ: let Gazebo use the .mtl texture instead of a flat colour.
    material = '' if textured else (
        f'\n        <material><diffuse>{r:.3f} {g:.3f} {b:.3f} {a:.3f}</diffuse>'
        f'<ambient>{r:.3f} {g:.3f} {b:.3f} {a:.3f}</ambient></material>')
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name={quoteattr(name)}>
    <static>{'true' if static else 'false'}</static>
    <link name="link">
{inertial}      <visual name="visual">
        {mesh_geom('visual.obj')}{material}
      </visual>
{cols}
    </link>
  </model>
</sdf>
"""


def gazebo_config(name):
    return f"""<?xml version="1.0"?>
<model>
  <name>{name}</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <description>3D-scanned object generated by scan_to_sim.py</description>
</model>
"""


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', help='mesh or point cloud (.obj .ply .stl .glb)')
    ap.add_argument('--name', default=None, help='asset name (default: file stem)')
    ap.add_argument('--out', default='.', help='output directory (default: .)')
    ap.add_argument('--up-axis', default='z', choices=sorted(_UP),
                    help='which axis is "up" in the input file (default: z; '
                         'use y for Y-up exports, -y for the ZED IMAGE frame)')
    ap.add_argument('--scale', type=float, default=1.0,
                    help='uniform scale, e.g. 0.001 for millimetres (default: 1)')
    ap.add_argument('--yaw', type=float, default=0.0, help='rotate about +Z [deg]')
    ap.add_argument('--offset', type=float, nargs=3, default=[0, 0, 0],
                    metavar=('X', 'Y', 'Z'), help='translate after alignment [m]')
    ap.add_argument('--no-floor', action='store_true',
                    help='do not move the lowest point to z=0')
    ap.add_argument('--center', action='store_true',
                    help='centre the footprint on x=y=0 (good for single objects)')
    ap.add_argument('--target-faces', type=int, default=50000,
                    help='decimate visual mesh to this many faces (0 = keep all)')
    ap.add_argument('--collision', default='hull',
                    choices=['none', 'hull', 'decompose'],
                    help='collision geometry (default: hull)')
    ap.add_argument('--coacd-threshold', type=float, default=0.08,
                    help='CoACD concavity threshold; lower = more, tighter parts')
    ap.add_argument('--max-hulls', type=int, default=32,
                    help='upper bound on CoACD parts (-1 = unlimited)')
    ap.add_argument('--mass', type=float, default=None,
                    help='make the object dynamic (free body) with this mass [kg]')
    args = ap.parse_args()

    name = args.name or os.path.splitext(os.path.basename(args.input))[0]
    name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)

    mesh = load_geometry(args.input)
    print(f'[scan_to_sim] loaded {len(mesh.vertices)} vertices / {len(mesh.faces)} faces')

    mesh = transform(mesh, args.up_axis, args.scale, args.yaw, args.offset,
                     floor=not args.no_floor, center=args.center)
    rgba = mean_rgba(mesh)          # before decimation, which may drop UVs/colours
    mesh = decimate(mesh, args.target_faces)

    lo, hi = mesh.bounds
    size = hi - lo
    print(f'[scan_to_sim] bounds  min={np.round(lo, 3)}  max={np.round(hi, 3)}')
    print(f'[scan_to_sim] size    {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f} m')
    if size.max() > 50 or size.max() < 0.02:
        print('[scan_to_sim] WARNING: that size looks wrong - check --scale '
              '(ZED exports are in metres only if coordinate_units=METER).')

    hulls = build_collision(mesh, args.collision, args.coacd_threshold, args.max_hulls)

    out = os.path.abspath(os.path.expanduser(args.out))
    asset_dir = os.path.join(out, name)
    mesh_dir = os.path.join(asset_dir, 'meshes')
    if os.path.isdir(mesh_dir):
        shutil.rmtree(mesh_dir)
    os.makedirs(mesh_dir)

    tex = export_visual(mesh, mesh_dir)
    for i, h in enumerate(hulls):
        h.export(os.path.join(mesh_dir, f'collision_{i:02d}.obj'))

    # MuJoCo. Mesh paths are resolved relative to the top-level scene file,
    # which lives in <out>/, so the snippet references "<name>/meshes/...".
    with open(os.path.join(asset_dir, f'{name}_mujoco.xml'), 'w') as f:
        f.write(mujoco_snippet(
            name, len(hulls), tex, rgba, args.mass, (0, 0, 0), f'{name}/meshes',
            inertial=inertial_xml(mesh, args.mass) if args.mass else None))
    scene_path = os.path.join(out, f'scene_{name}.xml')
    with open(scene_path, 'w') as f:
        f.write(SCENE_TEMPLATE.format(name=name))

    # Gazebo
    with open(os.path.join(asset_dir, 'model.sdf'), 'w') as f:
        f.write(gazebo_model(name, len(hulls), rgba, args.mass, args.mass is None,
                             textured=tex is not None,
                             mprops=mass_properties(mesh, args.mass) if args.mass else None))
    with open(os.path.join(asset_dir, 'model.config'), 'w') as f:
        f.write(gazebo_config(name))

    print('\n[scan_to_sim] wrote:')
    print(f'  MuJoCo scene  : {scene_path}')
    print(f'  MuJoCo include: {os.path.join(asset_dir, name + "_mujoco.xml")}')
    print(f'  Gazebo model  : {asset_dir}/model.sdf  (add {out} to GZ_SIM_RESOURCE_PATH)')
    print('\nTry it:')
    print('  bash tools/crazyflie-simulation/simulator_files/mujoco/launch/'
          f'sitl_singleagent.sh -s {scene_path}')


if __name__ == '__main__':
    main()
