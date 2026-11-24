# Simulating multiple Crazyflies

One `crazysim.py` process simulates every drone in the same world, and each
drone gets its own firmware process. Drone *i* is reachable at
`udp://127.0.0.1:{19850 + i}`.

## Launch options

### Square grid: `-n`

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_square.sh -n 8 -m cf2x_T350
```

Drones are placed on a grid with **1 m spacing** and `ceil(sqrt(n))` columns,
starting at the origin: for `-n 4`, drone 0 is at (0, 0), drone 1 at (1, 0),
drone 2 at (0, 1), drone 3 at (1, 1).

Gazebo equivalent:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/gazebo/launch/sitl_multiagent_square.sh -n 8 -m crazyflie
```

### Your own layout: `-f spawn_file.txt`

A spawn file has one `x,y` line per drone; line order = drone index = port
offset. Files are looked up in
`tools/crazyflie-simulation/drone_spawn_list/`.

```text
-1.0,-1.0
 0.0,-1.0
 1.0,-1.0
-1.0, 0.0
 1.0, 0.0
-1.0, 1.0
 0.0, 1.0
 1.0, 1.0
```

Generate common layouts with `tools/make_spawn_file.py` — it also prints the
URI of each drone and warns if drones are too close:

```console
(container) $ cd ~/my_code
(container) $ python3 tools/make_spawn_file.py circle -n 6 --radius 1.0 -o circle_6.txt --install
(container) $ python3 tools/make_spawn_file.py grid --rows 2 --cols 4 --spacing 0.6 -o grid_8.txt --install
(container) $ cd ~/CrazySim/crazyflie-firmware
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_text.sh -m cf2x_T350 -f circle_6.txt
```

:::{warning}
`drone_spawn_list/` is inside the container, so files copied there disappear
after `docker compose down`. Keep the originals in `~/my_code` and re-run
`--install` (or `cp`) after restarting the container.
:::

All MuJoCo feature flags work in multi-agent mode. `--downwash` only matters
here — the upper drone's prop wash pushes down on drones below it:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_square.sh -n 4 \
      --downwash --sensor-noise --ground-effect
```

With `--sensor-noise` each drone gets its own random IMU bias and scale, so no
two simulated drones behave identically — just like a real swarm.

## Fly the swarm with cflib

`examples/swarm_formation.py` uses cflib's `Swarm` helper: it connects to all
drones in parallel, resets their estimators, takes off, flies a rotating circle
around the centroid of the spawn positions, returns everyone home and lands.

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_square.sh -n 4   # terminal 1
(container) $ python3 ~/my_code/examples/swarm_formation.py -n 4                                             # terminal 2
```

The core pattern:

```{literalinclude} ../../examples/swarm_formation.py
:language: python
:caption: examples/swarm_formation.py (excerpt)
:pyobject: main
```

Key `Swarm` methods:

| Method | Use |
|---|---|
| `Swarm(uris, factory=CachedCfFactory(rw_cache='./cache'))` | connect to all drones; the cache makes reconnects fast |
| `reset_estimators()` | reset Kalman on every drone and wait until it has converged |
| `get_estimated_positions()` | `{uri: position}` — useful to plan from the actual start poses |
| `parallel_safe(func, args_dict={uri: [args...]})` | run `func(scf, *args)` on all drones at once, re-raising any error |
| `sequential(func, ...)` | one drone at a time (e.g. staged take-off) |

### The 8-drone circling demo

The classic Bitcraze demo now lives in
[crazyflie-demos](https://github.com/bitcraze/crazyflie-demos/tree/main/demos/scripts/cflib/autonomy/circling_square_demo).
Save the 8 positions above as `circling_square.txt` in `drone_spawn_list/` and:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_text.sh \
      -m cf2x_T350 -f circling_square.txt -M 0.0379
```

In `circling_square_demo.py`, replace the eight `radio://...` URIs with
`udp://127.0.0.1:19850` … `udp://127.0.0.1:19857`, then run it in a second
terminal.

## Fly the swarm with Crazyswarm2 (ROS 2)

CrazySim ships a Crazyswarm2 fork as a submodule. Build it once inside the
container (add these lines to the `Dockerfile` to keep it across restarts):

```console
(container) $ cd ~/CrazySim/crazyswarm2_ws
(container) $ colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
(container) $ source install/setup.bash
```

Edit `~/CrazySim/crazyswarm2_ws/src/crazyswarm2/crazyflie/config/crazyflies.yaml`
so that each robot points at a simulated drone and its `initial_position`
matches where the simulator spawned it:

```yaml
robots:
  cf_1:
    enabled: true
    uri: udp://127.0.0.1:19850
    initial_position: [0.0, 0.0, 0.0]
    type: cf_sim
  cf_2:
    enabled: true
    uri: udp://127.0.0.1:19851
    initial_position: [1.0, 0.0, 0.0]
    type: cf_sim
  cf_3:
    enabled: true
    uri: udp://127.0.0.1:19852
    initial_position: [0.0, 1.0, 0.0]
    type: cf_sim
  cf_4:
    enabled: true
    uri: udp://127.0.0.1:19853
    initial_position: [1.0, 1.0, 0.0]
    type: cf_sim

robot_types:
  cf_sim:
    motion_capture:
      tracking: "vendor"
    big_quad: false
    firmware_logging:
      enabled: true
      default_topics:
        pose:
          frequency: 10
```

Disable (`enabled: false`) any other robots in the file. Then:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_square.sh -n 4   # terminal 1
(container) $ ros2 launch crazyflie launch.py backend:=cflib mocap:=False                                   # terminal 2
(container) $ ros2 run crazyflie_examples hello_world                                                        # terminal 3
```

`backend:=cpp` also works with the simulator (CrazySim added UDP support to
the C++ backend). The same YAML with `radio://` URIs and your real robot types
flies the hardware — see {doc}`sim2real`.

## Tips for swarms

- Keep at least **0.3 m** between drones at spawn, more if you enable `--downwash`.
- Staggering altitudes (e.g. 0.5 m / 0.8 m) is the easiest way to avoid
  collisions while testing, but turn on `--downwash` to see what flying
  directly above another drone really does.
- Simulation speed scales with the number of drones; if the real-time factor
  drops below 1, close other GPU-heavy programs or use fewer drones.
- `scan_interfaces()` only discovers ports 19850–19859; build URIs directly
  for bigger swarms.

Next: {doc}`ai-deck`.
