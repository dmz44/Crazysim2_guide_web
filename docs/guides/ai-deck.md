# Simulating the AI-deck camera

The MuJoCo backend simulates the AI-deck's forward-facing camera and its WiFi
link. A small bridge, `crazysim_cpx.py`, plays the role of the deck's ESP32: it
speaks the same **CPX** protocol over TCP as real hardware, so AI-deck client
code (Bitcraze's `fpv.py`, your OpenCV pipeline) runs **unchanged** against the
simulator.

```{image} ../_static/img/aideck_fpv_lab.png
:alt: Simulated AI-deck frame, 324 x 244 grayscale
:align: center
```

## How it works

1. `crazysim.py --camera` renders each drone's `fpv_cam` with MuJoCo's
   offscreen renderer at **324 × 244, grayscale, 20 fps** (the Himax HM01B0
   sensor size) and pushes the raw frames over UDP to port `5200 + i`.
2. `crazysim_cpx.py` wraps each frame in a CPX APP packet with the standard
   `0xBC` image header and serves it on **`tcp://127.0.0.1:5050`**.
3. CRTP traffic on the same TCP link (connect, params, logs, setpoints) is
   bridged to the drone's normal cflib port, so you can **fly the drone over
   the WiFi link** just like a real AI-deck in WiFi mode.

The camera sits 3 cm in front of the body centre, looking along +X, with a
70° vertical field of view.

## Run it

Terminal 1 — simulator, firmware and CPX bridge in one go:

```console
(container) $ bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_camera.sh -s scene_obstacles.xml
```

`sitl_camera.sh` takes `-m <model>`, `-s <scene>`, `--sensor-noise` and
`--ground-effect`. Use a scene with something to look at — the default empty
scene is just a floor.

Terminal 2 — Bitcraze's FPV viewer (keyboard flight + live video):

```console
(container) $ python3 ~/crazyflie-demos/demos/scripts/cflib/aideck/fpv/fpv.py tcp://127.0.0.1:5050
```

:::{note}
`fpv.py` used to be at `crazyflie-lib-python/examples/aideck/fpv.py`. It moved
to [crazyflie-demos](https://github.com/bitcraze/crazyflie-demos) in 2026; see
the Dockerfile additions in {doc}`../getting-started/container`.
:::

## Your own vision code: OpenCV

`examples/aideck_opencv_viewer.py` is a minimal, dependency-light client: it
reassembles CPX image packets into NumPy arrays and hands them to OpenCV. Use it
as the starting point for detection, tracking or dataset collection.

```console
(container) $ python3 ~/my_code/examples/aideck_opencv_viewer.py                    # live window
(container) $ python3 ~/my_code/examples/aideck_opencv_viewer.py --edges            # + Canny edges
(container) $ python3 ~/my_code/examples/aideck_opencv_viewer.py --save ~/my_code/frames --headless
```

The heart of it is the frame reassembly loop:

```{literalinclude} ../../examples/aideck_opencv_viewer.py
:language: python
:pyobject: FrameGrabber.run
```

A few things to know when you write your own client:

- Connect with `Crazyflie().open_link('tcp://...')` and use `cf.link.cpx` —
  the image stream is CPX function `APP`.
- Don't rely on the header's `depth` byte: the simulator sends `8` (bits per
  pixel) while the GAP8 examples send `1` (bytes per pixel). Infer the channel
  count from `size / (width × height)` as the example does.
- `format` is `0` for raw and `1` for JPEG (some real-deck streamer builds).
- The receive thread should only keep the latest frame; processing in that
  thread makes frames back up.

### Collecting a dataset

Because the stream is identical to the real deck, simulated frames are a cheap
way to bootstrap a vision model. Fly a scripted path in one terminal
(`fly_square.py`, or your own) while saving frames in another with `--save`,
then fine-tune on a smaller set of real images. Vary the scene (objects,
textures, lighting with `scene_dark.xml` and the drone's headlight) to make the
model robust.

## Several drones with cameras

`sitl_camera.sh` starts one drone. For more, use
`examples/launch_camera_swarm.sh`, which starts one firmware process and one
CPX bridge per drone:

```console
(container) $ bash ~/my_code/examples/launch_camera_swarm.sh -s ~/my_code/scenes/scene_lab_example.xml -- -2,-1 -2,0
drone 0 at (-2,-1): udp://127.0.0.1:19850  tcp://127.0.0.1:5050
drone 1 at (-2,0): udp://127.0.0.1:19851  tcp://127.0.0.1:5051
```

Each drone's video is then on `tcp://127.0.0.1:{5050 + i}`. Rendering several
cameras is GPU-heavy; reduce `--cam-fps` (edit the script) if the simulation
slows down.

Under the hood it runs:

```bash
cf2 19950+i                                                     # one per drone
crazysim_cpx.py --cpx-port 5050+i --cflib-port 19850+i --frame-port 5200+i   # one per drone
crazysim.py --port 19950 --vis --camera --scene <scene> -- X0,Y0 X1,Y1 ...   # one for all
```

## Camera options

`crazysim.py` accepts these (edit the launch script to pass them):

| Option | Default | Notes |
|---|---|---|
| `--camera` | off | enable the FPV camera(s) |
| `--cam-width` / `--cam-height` | 324 / 244 | match the HM01B0; change for experiments only |
| `--cam-fps` | 20 | real decks stream far slower over WiFi (see below) |
| `--cam-port` | 5200 | base UDP port for frames (drone *i* uses +i) |

## Simulated vs. real AI-deck

| | Simulator | Real AI-deck |
|---|---|---|
| URI | `tcp://127.0.0.1:5050` | `tcp://192.168.4.1:5000` (AP mode) or `tcp://<deck IP>:5000` (station mode) |
| Image | clean 324×244 grayscale | grayscale or raw Bayer (color version), sensor noise, motion blur, auto-exposure |
| Frame rate | 20 fps (configurable) | typically a few fps over WiFi; ~2–6 fps is realistic for full-frame grayscale |
| Latency / drops | none | WiFi latency and dropped packets |
| Needs | nothing extra | up-to-date ESP32, STM32 and GAP8 firmware — see [aideck_fixes](https://github.com/dmz44/aideck_fixes) |

To make simulated vision code robust, **lower `--cam-fps` to what your real
deck achieves**, add noise/blur in your pipeline during training, and make
your code tolerate missing frames. See {doc}`sim2real`.
