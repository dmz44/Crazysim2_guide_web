# Simulating a single Crazyflie

This page gets one simulated Crazyflie flying from Python. Run every command
**inside the container** (`docker exec -it remote_pc_humble bash`), from
`~/CrazySim/crazyflie-firmware`.

## 1. Start the simulator

**MuJoCo** (recommended):

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh -m cf2x_T350 -x 0 -y 0
```

**Gazebo**:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/gazebo/launch/sitl_singleagent.sh -m crazyflie -x 0 -y 0
```

A window opens with the drone sitting at the origin. The script starts one
`cf2` firmware process and the physics process; `Ctrl+C` stops both.

Pick the model that matches your hardware:

| MuJoCo `-m` | Gazebo `-m` | Real drone | Max thrust / motor |
|---|---|---|---|
| `cf2x_L250` | `crazyflie` | Crazyflie 2.x, standard configuration | 0.12 N |
| `cf2x_P250` | — | Crazyflie 2.x, performance variant | 0.12 N |
| `cf2x_T350` *(default)* | `crazyflie_thrust_upgrade` | Crazyflie 2.x with the Thrust Upgrade bundle | 0.18 N |
| `cf21B_500` | — | Crazyflie 2.1 Brushless | 0.20 N |

If you have added decks, a bigger battery or a payload, pass the real take-off
mass in kg with `-M` (e.g. `-M 0.0379`). See {doc}`../reference/launch-options`
for every flag.

## 2. Check the connection with cfclient (optional)

```console
(container) $ cfclient
```

Tick **SITL**, click **Scan**, pick `udp://127.0.0.1:19850`, and **Connect**.
You can now watch log variables, change parameters and fly with a gamepad —
handy for tuning PID gains in simulation before touching hardware.

## 3. Fly from Python

The guide repository ships starter scripts in `examples/` (copy them to
`~/my_code` as described in {doc}`../getting-started/container`).

### The cflib tutorial

`cflib_tutorial.py` contains seven small, standalone demos. Start with the ones
that don't spin the motors:

```console
(container) $ cd ~/my_code/examples
(container) $ python3 cflib_tutorial.py list
(container) $ python3 cflib_tutorial.py 2 --uri udp://127.0.0.1:19850   # parameters
(container) $ python3 cflib_tutorial.py 3 --uri udp://127.0.0.1:19850   # logging (sync)
(container) $ python3 cflib_tutorial.py 5 --uri udp://127.0.0.1:19850   # MotionCommander flight
```

| # | Demo | What you learn |
|---|---|---|
| 1 | connect | `init_drivers()`, `SyncCrazyflie`, reading firmware info |
| 2 | params | reading/writing parameters (`commander.enHighLevel`, ...) |
| 3 | logging (sync) | `LogConfig` + `SyncLogger` for telemetry |
| 4 | logging (async) | callbacks for logging inside a bigger program |
| 5 | motion commander | relative moves: `forward`, `left`, `turn_left`, ... |
| 6 | position commander | absolute waypoints with `PositionHlCommander` |
| 7 | fly and log | the shape of most experiments: command, record, analyse |

:::{note}
Demo 1 calls `scan_interfaces()`, which also probes USB radios and can take a
few seconds inside the container. If it seems stuck, skip to demo 2.
:::

### A minimal flight

The essentials of every flight script are: init drivers → connect → reset the
estimator → enable the high-level commander → take off → move → land.

```python
import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

URI = 'udp://127.0.0.1:19850'   # simulator, drone 0

cflib.crtp.init_drivers()
with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
    cf = scf.cf
    cf.param.set_value('kalman.resetEstimation', '1'); time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0'); time.sleep(2)
    cf.param.set_value('commander.enHighLevel', '1')
    cf.platform.send_arming_request(True)   # auto-armed in SITL; required on newer hardware

    hl = cf.high_level_commander
    hl.takeoff(0.5, 2.0);            time.sleep(2.5)
    hl.go_to(0.5, 0.0, 0.5, 0, 2.0); time.sleep(2.5)
    hl.go_to(0.0, 0.0, 0.5, 0, 2.0); time.sleep(2.5)
    hl.land(0.0, 2.0);               time.sleep(2.5)
    hl.stop()
```

### A sim-to-real-ready script

`fly_square.py` does the same with logging to CSV, a safety envelope, and
pre-flight checks, and runs unchanged on hardware with `--target real`:

```console
(container) $ python3 fly_square.py --size 0.5 --height 0.5
(container) $ python3 fly_square.py --target real --uri radio://0/80/2M/E7E7E7E701   # later
```

```{literalinclude} ../../examples/fly_square.py
:language: python
:caption: examples/fly_square.py
:lines: 1-25
```

## 4. Make the simulation harder (MuJoCo)

All physics and sensor features are **off by default**. Turn them on once your
code works in the ideal case — this is the cheapest way to find out whether it
will survive real hardware.

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh \
      --sensor-noise --ground-effect --wind-speed 1.5 --wind-direction 90 --turbulence light
```

| Flag | Effect |
|---|---|
| `--sensor-noise` | BMI088 IMU model: white noise, per-drone random bias and scale, bias random walk |
| `--ground-effect` | Extra thrust close to the floor (felt on take-off/landing) |
| `--wind-speed <m/s>` / `--wind-direction <deg>` | Constant wind (0° = +X, 90° = +Y) |
| `--gust-intensity <m/s>` | Random gusts (Ornstein–Uhlenbeck) |
| `--turbulence none/light/moderate/severe` | Dryden turbulence |
| `--flowdeck` | Simulated Flow deck v2 (ToF + optical flow). Disables the external pose, so the estimator runs on flow only — like a real drone without Lighthouse/mocap |

The **Multi-ranger deck** is always simulated in MuJoCo (front/back/left/right/up
rays at 10 Hz, 4 m max range). Try it with the obstacle scene:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh -s scene_obstacles.xml
```

and read `range.front`, `range.left`, ... from cflib, or run
`multiranger_pointcloud.py` from
[crazyflie-demos](https://github.com/bitcraze/crazyflie-demos/tree/main/demos/scripts/cflib/multiranger)
with its URI changed to `udp://127.0.0.1:19850`.

## 5. LEDs and the dark scene

The top and bottom color-LED decks are rendered (and light up the scene).
Set their color from cflib or cfclient and launch with `-s scene_dark.xml` to
see the effect.

Next: {doc}`multiple-crazyflies`.
