# From simulation to real Crazyflies (sim2real)

CrazySim runs the real firmware, so **your flight code does not change when you
move to hardware — only the URI does.** What changes is the physics and the
sensors around the firmware. This page is about closing that gap
deliberately: making the simulator look like your drone and your room, and
checking the things the simulator cannot model before the first real flight.

:::{admonition} Key lesson from the Makerspace digital twin
:class: important

Correct logic is not enough. The parameters that govern flight behaviour
(mass, thrust model, controller gains, estimator settings, velocity limits)
must be calibrated to the real drone, or code that is perfect in simulation
will still fly badly.
:::

## The workflow

| Stage | Where | What you check |
|---|---|---|
| 1. Logic | CrazySim, default flags | the script connects, sequences, lands; no crashes into the floor |
| 2. Realism | CrazySim + `--sensor-noise --ground-effect` (+ `--downwash` for swarms, wind if relevant), real mass with `-M` | still works with noise, bias and disturbances |
| 3. Digital twin | CrazySim in a scene of your real room ({doc}`adding-objects`, {doc}`3d-scanned-objects`) | clearances, sensor readings, camera view |
| 4. First hardware flight | one drone, low altitude (≤ 0.5 m), small area, slow speeds | estimator quality, hover thrust, drift |
| 5. Full mission | real arena | everything, with someone on the kill switch |

Only move down a row when the previous one is boringly reliable.

## 1. Make the simulated drone match yours

### Frame and motors

Pick the model that matches the hardware (see the table in
{doc}`single-crazyflie`): stock Crazyflie 2.x → `cf2x_L250`; Thrust Upgrade
bundle → `cf2x_T350`; Crazyflie 2.1 Brushless → `cf21B_500`.

### Mass

Weigh the drone **as it flies** — battery, decks, markers, payload — and pass
it with `-M` (kilograms):

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_singleagent.sh -m cf2x_T350 -M 0.0379
```

A Lighthouse deck + AI-deck + bigger battery can add 10–15 g to a ~30 g
drone. An under-weighted simulation hides the fact that the real drone hovers
at a much higher thrust and has little margin left.

### Sensors and positioning

The simulator must provide the same kind of position information as your real
setup:

| Real setup | Simulator setting | Notes |
|---|---|---|
| **Lighthouse** deck + base stations | default (external pose) | sim pose is perfect; real Lighthouse has mm-level noise and occlusion dropouts |
| **Motion capture** (Vicon, OptiTrack, Qualisys) | default (external pose) | real mocap adds latency; send at a steady rate |
| **Flow deck v2** only | `--flowdeck` | sim disables the external pose so the estimator runs on ToF + optical flow, like the real drone. Real flow needs a textured floor |
| **Multi-ranger** deck | always on (MuJoCo) | 4 m max range, 10 Hz, same log variables (`range.front`, ...) |
| **AI-deck** | `sitl_camera.sh` | see {doc}`ai-deck` for the differences |
| no positioning deck | — | the real drone cannot hold position; use attitude/thrust control only |

:::{warning}
The most common sim2real failure: the code works in simulation (which always
has perfect position) but the real drone was only carrying a Flow deck, or the
Lighthouse system was not calibrated. Simulate with `--flowdeck` if that's
what you fly with.
:::

## 2. Make the simulated world match your room

**Use the same coordinate frame in both.** In the simulator, the world origin
is where `-x 0 -y 0` spawns a drone, +Z is up. On hardware, the origin and axes
come from your positioning system (Lighthouse geometry, mocap calibration).

- Pick a physical origin and +X direction in the room (e.g. a tape cross on
  the floor) and calibrate Lighthouse/mocap to it.
- Place real drones on the floor at the **same coordinates** as the spawn file
  you used in simulation.
- Scan the room with the ZED starting on that origin, facing +X
  ({doc}`3d-scanned-objects`); the scan then lines up with no extra work. If
  not, use `scan_to_sim.py --yaw/--offset` until a known point (a table
  corner) has the same coordinates in both.
- Keep the same safety margins: if a shelf is at x = 2.6 m in the sim, it is
  at 2.6 m in reality.

## 3. Switch the code over

### URIs

| | Simulator | Real hardware |
|---|---|---|
| Drone *i* over radio | `udp://127.0.0.1:{19850+i}` | `radio://0/80/2M/E7E7E7E7xx` (channel / data rate / address set in cfclient) |
| AI-deck | `tcp://127.0.0.1:{5050+i}` | `tcp://192.168.4.1:5000` (AP mode) or `tcp://<deck IP>:5000` (station mode) |

Keep the URI out of the flight logic. Either pass it as an argument
(`fly_square.py --target real --uri ...`) or use cflib's environment-variable
helper:

```python
from cflib.utils import uri_helper
URI = uri_helper.uri_from_env(default='udp://127.0.0.1:19850')   # export CFLIB_URI=radio://0/80/2M/E7E7E7E701
```

For swarms, keep a small table of sim ↔ real URIs, or two `crazyflies.yaml`
files for Crazyswarm2 — one with `udp://` URIs and `type: cf_sim`, one with
your radio URIs and real robot types — and pass the right one with
`crazyflies_yaml_file:=...`.

### Arming

The SITL firmware auto-arms. The Crazyflie 2.1 Brushless and firmware built
with `CONFIG_MOTORS_REQUIRE_ARMING` need an explicit arming request. Put it in
your code from day one — it is harmless in simulation:

```python
cf.platform.send_arming_request(True)
time.sleep(1.0)
```

### Real-drone pre-flight checks

`fly_square.py` shows the pattern: before taking off, read the state estimate
and battery and refuse to fly if they are implausible.

```{literalinclude} ../../examples/fly_square.py
:language: python
:pyobject: preflight
```

On hardware also add: a maximum altitude and arena bounds that your code
never commands outside of, a `try/finally` that lands on any exception or
`Ctrl+C`, and a human with the cfclient or a gamepad **emergency stop**.

## 4. What the simulator does not model

| Gap | In simulation | On hardware | What to do |
|---|---|---|---|
| Battery | constant 4.2 V (`pm.vbat`) | voltage sags in flight; thrust drops as it does | land at ~3.2 V under load; test with half-charged batteries too |
| Motor/prop variation | identical, perfect | worn props, bent arms, unbalanced motors | replace damaged props; check hover thrust in logs |
| Positioning | perfect pose, no latency | noise, occlusions, latency | watch `kalman.varPX/Y/Z`; avoid occluding the base stations |
| Radio link | lossless, local | latency, packet loss, interference | don't stream setpoints faster than needed (≤ 100 Hz); use the high-level commander when possible |
| AI-deck | 20 fps clean grayscale | a few fps, noise, blur, auto-exposure, WiFi drops | lower `--cam-fps`; tolerate missing frames |
| Aerodynamics | simplified drag, ground effect, Gaussian downwash | turbulence near walls/ceiling, AC drafts | keep distance from walls; enable `--wind-speed`/`--turbulence` in sim |
| Collisions | rigid contacts | broken props, flips, crashes | fly slower near obstacles than you dare in sim |

## 5. Tune in sim, verify on hardware

**Controller gains.** Connect cfclient to the simulator, open the *Parameters*
tab, and tune `pid_rate.*`, `pid_attitude.*` or `posCtlPid.*` live while the
drone hovers. This is especially useful for modified drones (bigger battery,
more decks, upgraded motors). Treat the result as a **starting point**, apply
it on hardware with the drone at low altitude, and re-check step responses.
Gains can be stored on the real drone as persistent parameters (see
`persistent_params.py` in `crazyflie-lib-python/examples/parameters/`).

**Compare logs, not impressions.** Fly the same script in both and compare the
CSVs:

```console
(container) $ python3 fly_square.py --target sim               # writes square_sim.csv
(container) $ python3 fly_square.py --target real --uri radio://0/80/2M/E7E7E7E701   # square_real.csv
```

```python
import pandas as pd, matplotlib.pyplot as plt
sim  = pd.read_csv('square_sim.csv')
real = pd.read_csv('square_real.csv')
for df, name in [(sim, 'sim'), (real, 'real')]:
    plt.plot(df['stateEstimate.x'], df['stateEstimate.y'], label=name)
plt.axis('equal'); plt.legend(); plt.xlabel('x [m]'); plt.ylabel('y [m]'); plt.show()
```

Large differences in overshoot or settling time point to mass or gain
mismatches; a constant offset points to a frame-alignment problem; drift points
to the positioning system.

## 6. Learned policies (RL)

If you train policies (e.g. PPO for waypoint navigation) in a fast simulator
and validate them in CrazySim before hardware:

- **Randomize in training** what you can't match exactly: mass (±10–15 %),
  motor strength, sensor noise and bias, latency, wind.
- **Validate in CrazySim with the noise flags on** — this runs the policy
  against the real firmware's estimator and controller, which a pure
  physics simulator does not.
- **Act at the same interface as on hardware.** Have the policy output
  position/velocity setpoints (e.g. `cf.commander.send_position_setpoint` or
  `send_hover_setpoint`) at a fixed rate (10–50 Hz) rather than motor
  commands. The firmware's controller then absorbs much of the reality gap.
- **Use the same observations.** Build the observation from log variables
  (`stateEstimate.*`, `range.*`) with the same logging period you'll get over
  the radio.
- Clip actions to safe limits in the deployment wrapper, not only in training.

## First-flight checklist

- [ ] Same model type and measured mass (`-M`) in the final sim runs
- [ ] Same positioning mode as hardware (`--flowdeck` if Flow-deck only)
- [ ] Script passed with `--sensor-noise --ground-effect` (+ `--downwash` for swarms)
- [ ] Real drones placed at the simulated spawn coordinates; frame origin/axes verified
- [ ] Firmware on the drones is up to date; decks detected in cfclient
- [ ] Battery charged; props intact; arena clear; nets/cage if available
- [ ] Arming request in code; safety envelope and land-on-exception in code
- [ ] Someone ready on the emergency stop
- [ ] First flight: one drone, low and slow
