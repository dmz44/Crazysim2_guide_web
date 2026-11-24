# Launch script reference

All scripts are run from `~/CrazySim/crazyflie-firmware` inside the
container. Run any of them with `-h` for its built-in help.

Paths below are abbreviated:
`MJ = tools/crazyflie-simulation/simulator_files/mujoco/launch`,
`GZ = tools/crazyflie-simulation/simulator_files/gazebo/launch`.

## MuJoCo

| Script | Purpose |
|---|---|
| `$MJ/sitl_singleagent.sh` | one drone at `-x`, `-y` |
| `$MJ/sitl_multiagent_square.sh` | `-n` drones on a 1 m grid |
| `$MJ/sitl_multiagent_text.sh` | drones at positions from a spawn file (`-f`) |
| `$MJ/sitl_camera.sh` | one drone with AI-deck camera + CPX bridge (`tcp://127.0.0.1:5050`) |

### Common options

| Option | Default | Scripts | Meaning |
|---|---|---|---|
| `-m <model>` | `cf2x_T350` | all | `cf2x_T350`, `cf2x_L250`, `cf2x_P250`, `cf21B_500` |
| `-s <scene.xml>` | `scene.xml` | all | absolute path, relative path, or file in the `mujoco/` folder |
| `-x <m>` / `-y <m>` | 0 / 0 | single | spawn position |
| `-n <N>` | — | square | number of drones |
| `-f <file>` | `single_origin.txt` | text | file in `tools/crazyflie-simulation/drone_spawn_list/` |
| `-M <kg>` | model default (0.0379 for T350) | single, square, text | override take-off mass |
| `-d <s>` | 0.001 | single, square, text | physics time step |

### Physics and sensor flags

| Flag | Scripts | Meaning |
|---|---|---|
| `--sensor-noise` | all | BMI088 IMU noise: white noise, random per-drone bias and scale, bias random walk |
| `--ground-effect` | all | extra thrust near the ground |
| `--downwash` | square, text | prop-wash interaction between drones |
| `--flowdeck` | single, square, text | simulate Flow deck v2 (ToF + optical flow); disables the external pose |
| `--wind-speed <m/s>` | single, square, text | constant wind |
| `--wind-direction <deg>` | single, square, text | 0 = +X, 90 = +Y, 180 = −X, 270 = −Y |
| `--gust-intensity <m/s>` | single, square, text | random gusts |
| `--turbulence <level>` | single, square, text | `none`, `light`, `moderate`, `severe` (Dryden) |

### `crazysim.py` directly

The launch scripts start `cf2` firmware instances and then
`crazysim.py`. Running it yourself is useful for custom setups (see
`examples/launch_camera_swarm.sh`):

```text
python3 crazysim.py [--model-type M] [--port 19950] [--vis] [--dt 0.001]
                    [--scene FILE] [--mass KG] [--spawn-file FILE]
                    [--sensor-noise] [--ground-effect] [--downwash] [--flowdeck]
                    [--wind-speed V] [--wind-direction DEG] [--gust-intensity V]
                    [--turbulence LEVEL]
                    [--camera] [--cam-width 324] [--cam-height 244] [--cam-fps 20] [--cam-port 5200]
                    -- X0,Y0 [X1,Y1 ...]
```

`--port` is the firmware port of drone 0; drone *i* uses `port + i` and cflib
port `port − 100 + i`. Start one `cf2 <19950+i>` per drone (from its own
working directory) before `crazysim.py`.

### `crazysim_cpx.py`

| Option | Default | Meaning |
|---|---|---|
| `--cpx-port` | 5050 | TCP port your AI-deck client connects to |
| `--cflib-port` | 19850 | the drone's cflib UDP port (CRTP bridged over CPX) |
| `--frame-port` | 5200 | UDP port the drone's camera frames arrive on |

## Gazebo

| Script | Options |
|---|---|
| `$GZ/sitl_singleagent.sh` | `-m crazyflie\|crazyflie_thrust_upgrade`, `-x`, `-y`, `-w <world>` |
| `$GZ/sitl_multiagent_square.sh` | `-n`, `-m`, `-w` |
| `$GZ/sitl_multiagent_text.sh` | `-m`, `-w`, `-f` |

`-w` is a world name in `tools/crazyflie-simulation/simulator_files/gazebo/worlds/`
(default `crazysim_default`); the file must be `<name>.sdf` and contain
`<world name="<name>">`.

## Ports

| Port | Protocol | Use |
|---|---|---|
| 19850 + i | UDP | cflib / cfclient / Crazyswarm2 → drone *i* |
| 19950 + i | UDP | firmware ↔ simulator (internal) |
| 5200 + i | UDP | camera frames simulator → CPX bridge (internal) |
| 5050 (+ i) | TCP | AI-deck CPX stream |
