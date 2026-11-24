# How CrazySim works

CrazySim is a **software-in-the-loop (SITL)** simulator: the Crazyflie firmware
itself is compiled for Linux (`cf2`) and runs on your PC. A simulator process
replaces the hardware underneath it — it receives motor commands from the
firmware, integrates the physics, and sends back the sensor readings the
firmware would get from its IMU, barometer and decks.

```{image} ../_static/img/architecture.svg
:alt: CrazySim architecture: cflib talks UDP to crazysim.py, which talks UDP to the cf2 firmware instances
:align: center
```

Because the estimator, controller, high-level commander, parameters and log
variables are the real firmware code, anything you do from cflib in simulation
behaves the same way on a real Crazyflie (minus the physics gap — see
{doc}`../guides/sim2real`).

## Two physics backends

| | **MuJoCo** (recommended) | **Gazebo Garden** |
|---|---|---|
| Real-time performance | Better; runs well on laptops | Heavier |
| Drone models | `cf2x_T350` (default), `cf2x_L250`, `cf2x_P250`, `cf21B_500` | `crazyflie`, `crazyflie_thrust_upgrade` |
| Sensor noise, ground effect, downwash, wind, turbulence | Yes (flags) | No |
| Multi-ranger deck, Flow deck | Yes | No |
| AI-deck camera (CPX) | Yes | No |
| Color LEDs (top/bottom), headlight | Yes | No |
| World format | MJCF XML (`-s scene.xml`) | SDF world (`-w world_name`) |

Unless you specifically need Gazebo (e.g. an existing SDF world or ROS–Gazebo
tooling), use MuJoCo. Everything in this guide works on MuJoCo; Gazebo
equivalents are given where they exist.

## Ports and URIs

Each simulated drone *i* (0-based) gets two UDP ports:

| What | Port | Who uses it |
|---|---|---|
| Firmware ↔ simulator | `19950 + i` | internal — `cf2` and `crazysim.py` |
| **cflib ↔ simulator** | **`19850 + i`** | **your code**: `udp://127.0.0.1:19850` for drone 0, `…:19851` for drone 1, … |
| AI-deck frames (internal) | `5200 + i` | `crazysim.py` → `crazysim_cpx.py` |
| **AI-deck CPX** | **`5050`** | **your vision code**: `tcp://127.0.0.1:5050` |

`cflib.crtp.scan_interfaces()` and cfclient's *SITL* checkbox auto-discover
ports 19850–19859. For more than 10 drones, connect by URI directly.

:::{note}
The simulator sends the drone's true pose to the firmware as an *external
position* (like a motion-capture or Lighthouse system would), so the Kalman
estimate converges immediately and `stateEstimate.x/y/z` are in **world
coordinates**. Use `--flowdeck` to turn this off and fly on simulated Flow-deck
data instead.
:::

## Where things live inside the container

```text
/root/
├── my_code/                         ← shared with ~/crazyflie_docker/my_code on the host (persistent!)
├── CrazySim/
│   ├── crazyflie-firmware/          ← working directory when you enter the container
│   │   ├── sitl_make/build/cf2      ← SITL firmware binary
│   │   └── tools/crazyflie-simulation/
│   │       ├── drone_spawn_list/    ← spawn coordinate files (-f)
│   │       └── simulator_files/
│   │           ├── mujoco/          ← crazysim.py, crazysim_cpx.py, scene*.xml, launch/
│   │           └── gazebo/          ← worlds/, models/, launch/
│   ├── crazyflie-lib-python/        ← cflib (installed with pip)
│   └── crazyswarm2_ws/              ← Crazyswarm2 ROS 2 workspace (CrazySim fork)
└── crazyflie-clients-python/        ← cfclient
```

All launch commands in this guide are run from
`~/CrazySim/crazyflie-firmware` inside the container, which is where
`docker exec` drops you.

:::{important}
Everything outside `~/my_code` is reset when the container is removed
(`docker compose down`). Keep your scripts, scenes, spawn files and scans in
`~/my_code`.
:::
