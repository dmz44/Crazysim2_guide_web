# Troubleshooting

## Display and GPU

**`cannot open display` / `Authorization required` / no window appears**
: Run `xhost +local:root` on the host (after every reboot), then restart the
  container. Check `echo $DISPLAY` inside the container matches the host.

**The simulator window is black or extremely slow**
: The container is not using the GPU. Check `nvidia-smi` on the host, that the
  NVIDIA Container Toolkit is installed and `nvidia-ctk runtime configure`
  was run, and restart Docker. Laptops with hybrid graphics may need the
  NVIDIA GPU selected (`prime-select nvidia`).

**`Could not load the Qt platform plugin "xcb"`** (cfclient / fpv.py)
: Usually caused by `opencv-python` and PyQt6 fighting over Qt plugins when
  both are imported in one process. Keep OpenCV and Qt GUIs in separate
  scripts (as the examples do), or use `opencv-python-headless` with a Qt viewer.

## Connecting

**cflib hangs on connect / `Too many packets lost`**
: Is the simulator actually running, and did it print
  `firmware connected` for every drone? Check the URI port
  (`19850 + i`, not `19950 + i`). Make sure no old `cf2` processes are left
  over: `pkill -x cf2`, or `docker compose down && docker compose up -d`.

**`scan_interfaces()` is slow or finds nothing**
: It also probes USB radios. Connect directly by URI instead.

**cfclient doesn't list the simulated drone**
: Tick the **SITL** checkbox before scanning. Only ports 19850–19859 are scanned.

**Some drones in a swarm never connect**
: Each drone needs its own firmware process. Look in
  `sitl_make/build/<i>/out.log` and `error.log` for the failing index. With many
  drones, give the swarm more time to connect (or connect in smaller batches).

## Flight

**Drone takes off and immediately drifts or flips**
: Reset the estimator before every flight (`kalman.resetEstimation`) and wait
  for it to converge (`Swarm.reset_estimators()` does this for you). With
  `--flowdeck`, the floor needs texture for optical flow.

**High-level commander does nothing**
: Set `commander.enHighLevel = 1` first. On real hardware, also send an
  arming request.

**Drone can't lift a payload / sinks slowly**
: The model's thrust limit is too low for the mass. Use `cf2x_T350` or
  `cf21B_500`, or reduce the payload.

## Scenes and objects

**`XML Error` when starting with `-s`**
: Open the scene alone first: `python3 -m mujoco.viewer --mjcf=<scene.xml>`.
  The error message gives the line number.

**`mass and inertia of moving bodies must be larger than mjMINVAL`**
: A body with a joint has no `<inertial>`. CrazySim scenes use
  `inertiafromgeom="false"`, so add an `<inertial>` to every moving body.

**`Error opening file '...obj'`**
: Mesh paths are relative to the **main** scene file (also for included
  files). Keep the asset folder next to the scene, or use absolute paths.

**The drone collides with "air" around a mesh**
: MuJoCo collides with a mesh's convex hull. Use primitive collision shapes,
  `scan_to_sim.py --collision decompose`, or make the mesh visual-only.

**Simulation runs slower than real time with a scan loaded**
: Decimate it (`--target-faces`) and use `--collision none` plus primitives.

## AI-deck

**`fpv.py: No such file or directory`**
: It moved to [crazyflie-demos](https://github.com/bitcraze/crazyflie-demos);
  see {doc}`../getting-started/container`.

**`Not connecting with WiFi` / no frames**
: Use a `tcp://` URI to the CPX port (`tcp://127.0.0.1:5050`), and start the
  simulator with `sitl_camera.sh` (or `--camera` plus `crazysim_cpx.py`).
  Only one client can be connected to a CPX bridge at a time.

**Image looks scrambled or has the wrong shape**
: Don't use the header's `depth` field to size the buffer — infer it from
  `size / (width × height)` (see {doc}`../guides/ai-deck`).

## Real hardware

**Real AI-deck: no WiFi network, stream stalls, or colors look wrong**
: See the troubleshooting table in {doc}`../guides/real-ai-deck`.

**Crazyradio not found inside the container**
: Install the udev rules on the host (see
  {doc}`../getting-started/installation`), plug the radio in **before**
  starting the container (or restart it), and close cfclient on the host —
  only one program can use the radio.
