# Adding objects to the simulator

The default world is an empty floor. This page shows how to build your own
environment — walls, furniture, obstacles, gates, objects the drones can push —
for both backends. For importing real-world geometry from a 3D camera, see
{doc}`3d-scanned-objects`.

```{image} ../_static/img/lab_example.png
:alt: The example lab scene: walls, workbench, shelf, gate, landing pad and a pushable box
:align: center
```

## MuJoCo

### The workflow

1. Copy a built-in scene into your shared folder so it survives container restarts:

   ```console
   (container) $ mkdir -p ~/my_code/scenes
   (container) $ cp tools/crazyflie-simulation/simulator_files/mujoco/scene.xml ~/my_code/scenes/my_lab.xml
   ```

   (or start from `scenes/scene_lab_example.xml` from the guide repository).

2. Add objects inside `<worldbody>` (examples below).

3. Preview it **without** the drones or firmware — this catches XML errors in
   seconds:

   ```console
   (container) $ python3 -m mujoco.viewer --mjcf=$HOME/my_code/scenes/my_lab.xml
   ```

4. Fly in it — every MuJoCo launch script takes `-s`:

   ```console
   (container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh -s ~/my_code/scenes/my_lab.xml
   (container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_square.sh -n 4 -s ~/my_code/scenes/my_lab.xml
   ```

   `-s` accepts an absolute path, a path relative to the current directory, or
   just a file name in the `mujoco/` folder (`-s scene_obstacles.xml`).

The drones are added to your scene automatically at the spawn positions; do not
put drones in the scene file.

:::{important}
Keep the header of `scene.xml` — in particular

```xml
<option integrator="RK4" density="1.225" viscosity="1.8e-5" timestep="0.001"/>
<compiler inertiafromgeom="false" autolimits="true"/>
```

`crazysim.py` runs the firmware loop at 1 kHz and relies on air density for
rotor drag. `inertiafromgeom="false"` also means **every moving body needs an
explicit `<inertial>`** (see below).
:::

### Built-in scenes

| File | Contents |
|---|---|
| `scene.xml` | empty floor (default) |
| `scene_walls.xml` | 6 m × 6 m room, semi-transparent walls |
| `scene_obstacles.xml` | room + pillars, partitions, crates, overhead beam |
| `scene_dark.xml` | dark scene to show off the LEDs and headlight |

### Static obstacles

Anything placed directly in `<worldbody>` (or in a `<body>` *without* a joint)
is fixed in the world. Sizes are **half-extents** in metres; `pos` is the
centre.

```xml
<worldbody>
  <light pos="0 0 3" dir="0 0 -1" directional="true"/>
  <geom name="floor" size="0 0 0.05" type="plane" material="groundplane"/>

  <!-- 2 m-tall wall, 6 m long, 10 cm thick, centred 3 m north of the origin -->
  <geom name="wall_n" type="box" size="3 0.05 1" pos="0 3 1" rgba="0.75 0.75 0.78 1"/>

  <!-- pillar: radius 0.12 m, half-height 1 m -->
  <geom name="pillar" type="cylinder" size="0.12 1" pos="1.2 1.2 1" rgba="0.5 0.35 0.25 1"/>

  <!-- several geoms that belong together: a table, rotated 30 deg about Z -->
  <body name="table" pos="1.5 -1 0" euler="0 0 30">
    <geom type="box" size="0.6 0.3 0.02"  pos="0 0 0.74"/>
    <geom type="box" size="0.02 0.02 0.36" pos=" 0.55  0.25 0.36"/>
    <geom type="box" size="0.02 0.02 0.36" pos="-0.55  0.25 0.36"/>
    <geom type="box" size="0.02 0.02 0.36" pos=" 0.55 -0.25 0.36"/>
    <geom type="box" size="0.02 0.02 0.36" pos="-0.55 -0.25 0.36"/>
  </body>
</worldbody>
```

Available primitives: `box`, `sphere`, `cylinder`, `capsule`, `ellipsoid`,
`plane`. Primitives are cheap and give exact collisions — prefer them for walls
and furniture.

### Objects the drones can move

Give the body a `<freejoint/>` and an `<inertial>`:

```xml
<body name="box_to_push" pos="1.0 -1.0 0.15">
  <freejoint/>
  <!-- solid 0.3 m cube of 50 g: I = m (a^2 + a^2) / 12 -->
  <inertial pos="0 0 0" mass="0.05" diaginertia="7.5e-4 7.5e-4 7.5e-4"/>
  <geom type="box" size="0.15 0.15 0.15" rgba="0.7 0.55 0.35 1" friction="0.6 0.005 0.0001"/>
</body>
```

Use a hinge (`<joint type="hinge" axis="0 0 1"/>`) for doors, or a slide
joint for drawers.

Drones are added to your scene when the simulator starts, as bodies named
`cf0_drone`, `cf1_drone`, …, and your scene may refer to them. For example, to
hang a payload 0.5 m below drone 0 with a ball joint–like constraint:

```xml
<equality>
  <connect body1="payload" body2="cf0_drone" anchor="0 0 0.5"/>
</equality>
```

(`anchor` is in `body1`'s frame.) The payload's mass comes from its own
`<inertial>`; make sure the drone model has the thrust margin to carry it
(`cf21B_500` and `cf2x_T350` have the most, 0.20 and 0.18 N per motor).

### Visual-only objects and sensors

Collision is controlled by `contype`/`conaffinity`. Setting both to `0`
makes a geom something the drone flies *through* — but it is still seen by the
**Multi-ranger rays, the Flow-deck ToF ray and the AI-deck camera**, because
those use ray casting and rendering, not contacts:

```xml
<!-- checkerboard marker on a wall, for the camera / optical flow -->
<texture name="marker" type="2d" builtin="checker" rgb1="0 0 0" rgb2="1 1 1" width="64" height="64"/>
<material name="marker" texture="marker" texuniform="true" texrepeat="8 8"/>
...
<geom name="wall_marker" type="box" size="0.3 0.005 0.3" pos="0 2.94 1.0"
      material="marker" contype="0" conaffinity="0"/>
```

Textured surfaces matter when you simulate the **Flow deck** or the
**AI-deck**: a plain-coloured floor gives an optical-flow sensor nothing to
track in reality, and your vision code nothing to detect.

### Meshes (STL / OBJ)

Put the mesh next to your scene (e.g. `~/my_code/scenes/meshes/`) and
reference it relative to the scene file:

```xml
<asset>
  <mesh name="bracket" file="meshes/bracket.stl" scale="0.001 0.001 0.001"/>   <!-- CAD in mm -->
</asset>
<worldbody>
  <geom type="mesh" mesh="bracket" pos="0.5 0.5 0" rgba="0.8 0.8 0.8 1"/>
</worldbody>
```

:::{warning}
MuJoCo collides with the **convex hull** of a mesh. A U-shaped bracket, a
chair or a scanned room becomes a solid blob for collisions. Either build the
collision shape from primitives, or split the mesh into convex parts —
`tools/scan_to_sim.py --collision decompose` does this for you (see
{doc}`3d-scanned-objects`).
:::

### Reusing objects across scenes

Put objects in their own file with a `<mujoco>` root and pull them in with
`<include>`. File paths inside included files are resolved relative to the
**main** scene file.

```xml
<!-- my_lab.xml -->
<mujoco model="my lab">
  ...
  <include file="objects/workbench.xml"/>
  <include file="objects/gate.xml"/>
</mujoco>
```

## Gazebo

### Worlds

Gazebo worlds live in
`tools/crazyflie-simulation/simulator_files/gazebo/worlds/` and are chosen with
`-w <world name>` (default: `crazysim_default`). The launch scripts load
`worlds/<name>.sdf` and spawn drones through `/world/<name>/create`, so **the
file name and the `<world name="...">` inside it must match**.

```console
(container) $ cd tools/crazyflie-simulation/simulator_files/gazebo/worlds
(container) $ cp crazysim_default.sdf ~/my_code/worlds/my_lab.sdf
(container) $ sed -i 's/<world name="crazysim_default">/<world name="my_lab">/' ~/my_code/worlds/my_lab.sdf
(container) $ ln -sf ~/my_code/worlds/my_lab.sdf my_lab.sdf          # re-create after container restarts
(container) $ cd ~/CrazySim/crazyflie-firmware
(container) $ bash tools/crazyflie-simulation/simulator_files/gazebo/launch/sitl_singleagent.sh -m crazyflie -w my_lab
```

Add static models inside `<world>`:

```xml
<model name="pillar">
  <static>true</static>
  <pose>1.2 1.2 1.0 0 0 0</pose>
  <link name="link">
    <collision name="collision"><geometry><cylinder><radius>0.12</radius><length>2.0</length></cylinder></geometry></collision>
    <visual name="visual">
      <geometry><cylinder><radius>0.12</radius><length>2.0</length></cylinder></geometry>
      <material><diffuse>0.5 0.35 0.25 1</diffuse></material>
    </visual>
  </link>
</model>
```

Note that in SDF, box `<size>` is the **full** size, unlike MuJoCo's half sizes.

### Models and meshes

Reusable models are folders with `model.config` and `model.sdf`, referenced as
`model://<name>`. Gazebo finds them through `GZ_SIM_RESOURCE_PATH`; the launch
scripts *append* CrazySim's paths to whatever you export, so you can keep your
models in the shared folder:

```console
(container) $ export GZ_SIM_RESOURCE_PATH=$HOME/my_code/gz_models
```

```xml
<include>
  <uri>model://lab_table</uri>
  <pose>1.5 -1.0 0 0 0 0.5</pose>
</include>
```

You can also add a model to a running simulation:

```console
(container) $ gz service -s /world/my_lab/create --reqtype gz.msgs.EntityFactory \
    --reptype gz.msgs.Boolean --timeout 1000 \
    --req 'sdf_filename: "'$HOME'/my_code/gz_models/lab_table/model.sdf", pose: {position: {x: 1.5, y: -1.0, z: 0}}, name: "table1"'
```

Next: {doc}`3d-scanned-objects`.
