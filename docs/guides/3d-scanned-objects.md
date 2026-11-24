# Adding 3D-scanned objects (ZED 2)

Hand-modelling a cluttered lab is slow. A stereo depth camera such as the
**Stereolabs ZED 2 / ZED 2i** can scan a room or an object in minutes and
produce a textured mesh. This page turns that mesh into simulator assets so
your simulated drone flies — and its range sensors and AI-deck camera see — the
same environment as the real one.

```{image} ../_static/img/scanned_table.png
:alt: A scanned table imported into CrazySim with scan_to_sim.py
:align: center
```

## The pipeline

```text
 ZED 2  ──►  mesh (.obj/.ply)  ──►  tools/scan_to_sim.py  ──►  MuJoCo scene (-s)  ──►  fly
 (ZEDfu or                          align, scale, decimate,     Gazebo model (model://)
  zed_spatial_map.py)               collision hulls
```

## 1. Capture the scan

You need the [ZED SDK](https://www.stereolabs.com/developers/release) and an
NVIDIA GPU on the machine the camera is plugged into. This can be the host, a
Jetson, or a separate ZED container (e.g.
[dmz44/zed_camera_docker](https://github.com/dmz44/zed_camera_docker)) — it does
**not** have to be the CrazySim container.

### Option A — ZEDfu (GUI)

ZEDfu ships with the ZED SDK (`/usr/local/zed/tools/ZEDfu`). Choose **Mesh**
mapping, set the resolution (*Medium* for rooms, *High* for objects), press
**Start**, walk the scan, press **Stop**, then **Filter** and **Save** as `.obj`
with texture.

### Option B — `tools/zed_spatial_map.py` (scriptable)

```console
$ python3 tools/zed_spatial_map.py -o lab.obj                                 # live, Ctrl+C to finish
$ python3 tools/zed_spatial_map.py --svo lab.svo2 -o lab.obj                  # from a recording
$ python3 tools/zed_spatial_map.py -o part.obj --resolution 0.01 --range 2    # small object
```

The script asks the SDK for a **Z-up, X-forward, metre** coordinate system —
the same convention as MuJoCo, Gazebo and the Crazyflie — so the output needs
no axis conversion. Recording an SVO first (with ZED Explorer) and mapping it
afterwards lets you retry with different settings without rescanning.

:::{admonition} Scanning tips
:class: tip

- **Start where you want the origin.** The mesh origin is where the camera
  was when tracking started, facing +X. If you start on your Lighthouse/mocap
  origin, pointing along its +X axis, the scan already lines up with your real
  flight arena (see {doc}`sim2real`).
- Move slowly, keep overlap between passes, and **return to where you started**
  so the tracker can close the loop.
- Cover the floor and the tops of tables — anything the drone may fly over.
- Even, diffuse lighting; avoid glass, mirrors and glossy black surfaces (no
  depth) and people walking through the scene.
- Mapping resolution: ~3–5 cm for rooms, ~1 cm for objects. Finer is not
  better for rooms — it only makes the mesh heavier.
:::

## 2. Convert it with `scan_to_sim.py`

`tools/scan_to_sim.py` (run inside the CrazySim container, with the
packages from the recommended Dockerfile additions) does the clean-up that
every scan needs:

1. loads `.obj`, `.ply`, `.stl` or `.glb` (a point-cloud PLY is meshed with
   Poisson reconstruction if Open3D is installed);
2. rotates it Z-up (`--up-axis`), scales it (`--scale`), rotates/translates it
   (`--yaw`, `--offset`) and by default drops its lowest point onto `z = 0`;
3. decimates it to `--target-faces` triangles;
4. builds collision geometry (`--collision none | hull | decompose`);
5. writes a MuJoCo include file, a ready-to-run MuJoCo scene, and a Gazebo
   model.

### A single object

```console
(container) $ cd ~/my_code
(container) $ python3 tools/scan_to_sim.py scans/cart.obj --name cart \
      --center --collision decompose --target-faces 20000 --out scenes
[scan_to_sim] size    0.910 x 0.520 x 0.980 m
...
  MuJoCo scene  : /root/my_code/scenes/scene_cart.xml
(container) $ cd ~/CrazySim/crazyflie-firmware
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh \
      -s ~/my_code/scenes/scene_cart.xml -x -1.5 -y 0
```

**Always check the printed size** against a tape measure. If it is 1000× too
big, the file was in millimetres (`--scale 0.001`); if the object lies on its
side, it was exported Y-up (`--up-axis y`).

Add `--mass 2.0` to make the object a free body that can be pushed around
(the script computes its inertia from the convex hull).

### A whole room

```console
(container) $ python3 tools/scan_to_sim.py scans/lab.obj --name lab \
      --collision none --target-faces 150000 --out scenes
```

For rooms, `--collision none` plus a few primitive boxes for the walls and
large furniture is usually best: the scan stays visible to the camera and the
range sensors, while contacts stay fast and exact. Add those boxes to the
generated `scene_lab.xml` as shown in {doc}`adding-objects`. If you prefer
automatic collision geometry, `--collision decompose --max-hulls 64` works but
can take a few minutes for a large scan.

:::{note}
The generated scene keeps CrazySim's flat floor plane for contacts. If your
scanned floor shows through or flickers against it, lower the scan by a
centimetre with `--offset 0 0 -0.01`.
:::

### Options

| Option | Default | Meaning |
|---|---|---|
| `--name` | file name | asset name (letters, digits, `_`) |
| `--out` | `.` | output folder; put it in `~/my_code` |
| `--up-axis` | `z` | up axis of the input: `z`, `y`, `-y`, `x`, … |
| `--scale` | `1` | uniform scale (`0.001` for mm) |
| `--yaw` / `--offset X Y Z` | 0 | align with your world frame after rotation |
| `--no-floor` | off | keep the original height instead of moving the lowest point to `z = 0` |
| `--center` | off | centre the footprint on the origin (objects) |
| `--target-faces` | 50000 | decimate the visual mesh (`0` keeps all) |
| `--collision` | `hull` | `none` (visual only), `hull` (one convex hull), `decompose` (CoACD convex parts) |
| `--coacd-threshold` | 0.08 | lower = more, tighter convex parts |
| `--max-hulls` | 32 | cap on convex parts |
| `--mass` | — | make it a free (movable) body with this mass in kg |

### What gets written

```text
scenes/
├── scene_cart.xml            # complete MuJoCo scene → use with -s
└── cart/
    ├── cart_mujoco.xml       # <include> this into your own scenes
    ├── model.sdf, model.config   # Gazebo model (model://cart)
    └── meshes/
        ├── visual.obj (+ texture png)
        └── collision_00.obj ... collision_NN.obj
```

In MuJoCo the visual mesh is in geom **group 2** with contacts disabled, and
the collision hulls are in **group 3**, which the viewer hides by default.
Press <kbd>3</kbd> in the MuJoCo viewer to show the hulls and check that they
fit.

To put the object into an existing scene instead, include it (paths are
relative to the main scene file, so keep the `cart/` folder next to it):

```xml
<include file="cart/cart_mujoco.xml"/>
```

To place several copies, or move it, edit the `pos` of the `<body>` in
`cart_mujoco.xml`.

### Gazebo

```console
(container) $ export GZ_SIM_RESOURCE_PATH=$HOME/my_code/scenes
```

then add `<include><uri>model://cart</uri><pose>1 0 0 0 0 0</pose></include>`
to your world (see {doc}`adding-objects`).

## 3. Check it from the drone's point of view

Launch with the AI-deck camera and look through it — if the scan is aligned
and to scale, the view should match what the real deck sees from the same
position:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_camera.sh -s ~/my_code/scenes/scene_cart.xml
(container) $ python3 ~/my_code/examples/aideck_opencv_viewer.py
```

```{image} ../_static/img/scanned_table_fpv.png
:alt: AI-deck view of the scanned table
:align: center
```

## Textures and colours

- MuJoCo and Gazebo render **textured OBJ** meshes (UV + image). Export with
  texture from ZEDfu, or keep texture on in `zed_spatial_map.py`.
- Vertex-coloured PLY meshes are rendered in their **average colour** (neither
  simulator draws per-vertex colours).
- Decimation discards UVs, so a textured mesh that gets decimated falls back to
  its average colour. To keep the texture, map at a coarser resolution instead,
  or pass `--target-faces 0`.

## Performance

| Mesh size | Effect |
|---|---|
| < 50 k faces | no noticeable cost |
| 50 k – 300 k | fine for rendering; Multi-ranger / Flow-deck rays get slower |
| > 300 k | decimate — the simulation may drop below real time |

Ray-based sensors (multiranger, flow-deck ToF) test against the scan's
triangles, so a huge scan slows them down even when collisions are off.
