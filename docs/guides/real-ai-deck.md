# Real AI-deck: AP mode and the color camera

The simulated AI-deck works as soon as you start `sitl_camera.sh`. A real
AI-deck needs three chips to agree before you get a stable video stream:

- the **ESP32**, which runs the WiFi;
- the **STM32** on the Crazyflie, which tells the ESP32 at boot to start as an
  access point;
- the **GAP8**, which captures the images and sends them.

This page sets up a deck the way the lab uses it: in **access-point (AP)
mode**, where the drone creates its own WiFi network and your laptop joins it,
with the **color camera** streaming reliably. It follows the fixes in
[dmz44/aideck_fixes](https://github.com/dmz44/aideck_fixes) and otherwise keeps
**Bitcraze's defaults** everywhere:

| Setting | Bitcraze default used on this page |
|---|---|
| Crazyflie radio URI | `radio://0/80/2M/E7E7E7E7E7` |
| AI-deck WiFi mode | Access point |
| WiFi SSID / password (`menuconfig` defaults) | `myssid` / `mypassword` |
| AI-deck IP address and port | **`192.168.4.1`**, port **`5000`** |
| cflib URI for the deck | `tcp://192.168.4.1:5000` |
| Viewer | Bitcraze's `opencv-viewer.py` from the WiFi streamer example |

:::{tip}
With several drones in one room, every drone with default settings
advertises the same `myssid` network. Give each drone its own radio address
and SSID (e.g. `cf-02`) so you know which network belongs to which drone.
Everything else on this page stays the same: in AP mode the deck is always
`192.168.4.1`.
:::

:::{admonition} Version warning: the color streamer is based on an older Bitcraze example
:class: warning

The color streamer file
[`wifi_img_streamer_colorcam_QQVGA.c`](https://github.com/dmz44/aideck_fixes/blob/main/wifi_img_streamer_colorcam_QQVGA.c)
is a modified copy of Bitcraze's **single-file** WiFi streamer from August
2025 ([aideck-gap8-examples](https://github.com/bitcraze/aideck-gap8-examples)
commit `725a350`), tested in May 2026. In July–August 2026 Bitcraze rewrote
that example into several files (`camera_pipeline.c`, `cpx_stream.c`,
`stream_config.h`, …). **The file does not drop into the new version.**

This page therefore builds the GAP8 code from the pinned old commit. If you
want to use newer Bitcraze GAP8 examples or firmware, you have to port the
changes yourself (see [Porting to newer firmware](#porting-to-newer-firmware)),
and test the result again.
:::

## What you end up with

| | Value |
|---|---|
| WiFi network | created by the drone (`myssid` by default) |
| Deck address | `192.168.4.1:5000` |
| Color stream | 162 × 122 raw Bayer (QQVGA), about 2–3 fps |
| Grayscale stream | up to about 6 fps over WiFi |

## Prerequisites (host PC, Ubuntu 24.04)

```console
$ sudo apt update
$ sudo apt install git make curl libncurses-dev gcc-arm-none-eabi libnewlib-arm-none-eabi
$ python3 -m venv ~/cf-venv && source ~/cf-venv/bin/activate   # Ubuntu 24 blocks system-wide pip
$ pip install cflib cfclient opencv-python                       # cfloader comes with cflib
```

You also need Docker for the GAP8 build (already installed if you followed
{doc}`../getting-started/installation`), a Crazyradio with the udev rules from
that page, and the AI-deck mounted on the Crazyflie.

## Step 1: Update the ESP32 (WiFi chip)

With the AI-deck attached, flash the **latest official Crazyflie release**
from cfclient: *Connect → Bootloader*, pick the newest release, then
*Program*. The release package also updates the AI-deck's ESP32, so you get
current WiFi firmware without opening the deck.

## Step 2: Build the STM32 firmware in AP mode

The STM32 sends the WiFi setup to the ESP32 at boot. That setup is a
build-time option, so you choose AP mode when you compile the Crazyflie
firmware.

```console
$ git clone --recursive https://github.com/bitcraze/crazyflie-firmware.git
$ cd crazyflie-firmware
$ make cf2_defconfig          # Crazyflie 2.x  (use cfbl_defconfig for the 2.1 Brushless)
$ make menuconfig
```

In `menuconfig`:

1. **Expansion deck configuration → Support the AI deck**: leave it on (the
   default).
2. **WiFi setup at startup**: choose **Act as Access Point**.
3. **Credentials for access-point**: the defaults are **WiFi SSID** `myssid`
   and **WiFi Password** `mypassword`. If you change the password, it must be
   **at least 8 characters**, or the network won't come up.
4. Save and exit.

Check what you set, then build and flash:

```console
$ grep -E 'CONFIG_DECK_AI(_WIFI_SETUP_AP|_SSID|_PASSWORD)?=' .config
CONFIG_DECK_AI=y
CONFIG_DECK_AI_WIFI_SETUP_AP=y
CONFIG_DECK_AI_SSID="myssid"
CONFIG_DECK_AI_PASSWORD="mypassword"
$ make clean
$ make -j$(nproc)
$ cfloader flash build/cf2.bin stm32-fw -w radio://0/80/2M/E7E7E7E7E7
```

After the drone reboots, cfclient's *Console* tab shows
`AI-deck will become access point`.

:::{note}
This guide only covers AP mode. The other option, *Connect to a WiFi network*
(station mode), joins an existing router instead; the deck then gets an
address from the router rather than `192.168.4.1`.
:::

## Step 3: Flash the color-camera streamer to the GAP8

### Why the color camera needs a code change

The grayscale and color AI-decks use the same Himax HM01B0 sensor, but the
color version has a **Bayer filter**: each pixel sees only red, green *or*
blue, in a repeating 2 × 2 mosaic. A color image is reconstructed on your PC
by *debayering* that mosaic.

That changes what the streamer can do:

1. **Color frames can't be JPEG-compressed on the deck.** The GAP8 JPEG
   encoder treats its input as an 8-bit grayscale image. Compressing a Bayer
   mosaic as if it were grayscale blurs neighbouring red, green and blue
   pixels into each other, and the colors can't be recovered afterwards. The
   fix that helps the grayscale deck (stream JPEG instead of raw) therefore
   doesn't work for color. Color has to be sent **raw**.
2. **Raw full-size frames are too big for the WiFi link.** The stock streamer
   sends raw QVGA frames of 324 × 244 = **79,056 bytes**, split into about 80
   CPX packets of roughly 1 KB each, and it starts the next frame immediately.
   The path from the GAP8 through the ESP32 to WiFi can't keep up. Packets back
   up and get dropped. Because a frame is just a header followed by chunks,
   one lost chunk makes the viewer misread pixel data as the next header. The
   result is a stuck or garbled stream, viewer crashes (wrong buffer size), or
   a deck that stops streaming.
3. **The fix sends less data per frame, and paces it.** Switching the sensor
   to QQVGA (162 × 122 = **19,764 bytes**, about 20 packets) cuts the data per
   frame by 4×. Waiting 400 ms after each frame lets the ESP32 empty its
   buffers before the next one arrives.

### What changed in the code

Compared with Bitcraze's streamer at commit `725a350`, the color streamer
changes exactly three things:

```diff
-#define CAM_WIDTH 324
-#define CAM_HEIGHT 244
+#define CAM_WIDTH 162          // QQVGA
+#define CAM_HEIGHT 122
 ...
-  cam_conf.format = PI_CAMERA_QVGA;
+  cam_conf.format = PI_CAMERA_QQVGA;
 ...
       cpxPrintToConsole(LOG_TO_CRTP, "capture=%dms, encoding=%d ms (%d bytes), transfer=%d ms\n", ...);
+      vTaskDelay(400);         // pace the stream: let the WiFi link drain between frames
```

The streamer keeps Bitcraze's default `streamerMode = RAW_ENCODING`, for the
reason above. The 400 ms delay is deliberately conservative and caps the
stream at roughly 2–3 fps. Lower it step by step for more fps once the stream
is stable.

### Build and flash

```console
$ git clone https://github.com/bitcraze/aideck-gap8-examples.git
$ cd aideck-gap8-examples
$ git checkout 725a350          # single-file streamer the color fix is based on (see warning above)
$ curl -L -o examples/other/wifi-img-streamer/wifi-img-streamer.c \
    https://raw.githubusercontent.com/dmz44/aideck_fixes/main/wifi_img_streamer_colorcam_QQVGA.c
$ docker run --rm -v ${PWD}:/module bitcraze/aideck \
    tools/build/make-example examples/other/wifi-img-streamer image
$ cfloader flash \
    examples/other/wifi-img-streamer/BUILD/GAP8_V2/GCC_RISCV_FREERTOS/target.board.devices.flash.img \
    deck-bcAI:gap8-fw -w radio://0/80/2M/E7E7E7E7E7
```

:::{warning}
**Only one chip should configure the WiFi.** Bitcraze's streamer can also start
its own open access point ("WiFi streaming example") when built with
`SETUP_WIFI_AP=1`. Don't use that here: the STM32 already sets up AP mode
(Step 2). Build the GAP8 example **without** `SETUP_WIFI_AP`, exactly as
above.
:::

:::{admonition} Recommended one-line fix
:class: tip

In `sendBufferViaCPX()`, the last chunk of every frame is copied with
`sizeof(packet->data)` instead of the number of bytes actually left, so it
reads past the end of the image buffer. The grayscale fix in
[aideck_fixes](https://github.com/dmz44/aideck_fixes) changes that line to:

```c
memcpy(packet->data, &buffer[offset], size);
```

Make the same change in the color streamer.
:::

### Porting to newer firmware

If you build Bitcraze's current `aideck-gap8-examples` instead of the pinned
commit, port the fix yourself and re-test it on your deck:

- **Resolution and encoding.** The new example takes these as `make` variables,
  so append `CAMERA_RESOLUTION=qqvga STREAM_ENCODING=raw` to the
  `make-example` command instead of editing `#define`s.
- **Frame pacing.** The new example has no inter-frame delay. Add a
  `vTaskDelay(...)` at the end of each loop iteration of `camera_task()` in
  `wifi-img-streamer.c`.
- **Viewer.** Check the image header width and height. They follow the
  resolution you built, so viewers that hard-code a size must be updated.

Bitcraze also changes the CPX protocol and deck firmware from time to time.
If a newer Crazyflie release no longer works with the old GAP8 build, flash
the same release version on both the STM32 and the GAP8, or port the fix as
above.

## Step 4: Connect and view

1. Power-cycle the drone. After a few seconds the network `myssid` appears.
   Join it from your laptop with the password `mypassword`.
2. Your laptop gets an address `192.168.4.x`. The deck is **`192.168.4.1`**.
   That WiFi adapter now has no internet access; use Ethernet or a second
   adapter if you need both.
3. Open a viewer. All of these work on the host and inside the CrazySim
   container (it uses host networking, so `192.168.4.1` is reachable from
   there too):

**Bitcraze's viewer** (`opencv-viewer.py` in the same pinned checkout, default
address `192.168.4.1:5000`). For the color QQVGA stream, change the reshape in
the raw branch from `(244, 324)` to `(122, 162)`:

```console
$ cd aideck-gap8-examples/examples/other/wifi-img-streamer
$ sed -i 's/bayer_img.shape = (244, 324)/bayer_img.shape = (122, 162)/' opencv-viewer.py
$ python3 opencv-viewer.py -n 192.168.4.1 -p 5000
```

**The viewers from aideck_fixes** (already set to 162 × 122):

```console
$ python3 opencv_viewer_color_QQVGA.py -n 192.168.4.1 -p 5000   # raw + color windows
$ python3 opencv_viewer_QQVGA_Color.py -n 192.168.4.1 -p 5000   # color + YOLOv8n detection (pip install ultralytics)
```

Their built-in default address is `192.168.0.101` (a station-mode address),
so **always pass `-n 192.168.4.1`**.

**This guide's viewer** (cflib/CPX, the same code you use against the
simulator):

```console
(container) $ python3 ~/my_code/examples/aideck_opencv_viewer.py --uri tcp://192.168.4.1:5000 --debayer
```

**Colors look wrong?** Bitcraze's viewer and `opencv_viewer_color_QQVGA.py`
debayer with `BayerBG`, while the YOLO viewer uses `BayerRG`. If red and blue
look swapped, switch to the other pattern (`--bayer RG` in this guide's
viewer). The section below explains why the pattern can change.

## How the color fix changes the camera compared with the simulator

The simulated deck renders an ideal camera: 324 × 244 grayscale, 70° vertical
FOV, centred, 20 fps, no lens distortion. With the color fix the real camera
differs in several ways. This matters as soon as you reuse vision code,
detection thresholds, or anything that converts pixels to angles or
distances.

| | Simulator (default) | Real color deck, QQVGA fix | What it means |
|---|---|---|---|
| Resolution | 324 × 244 | **162 × 122** | 4× fewer pixels; small or distant objects become very small |
| Field of view | 70° vertical (≈ 86° horizontal) | **same as at QVGA** (see below) | angles are the same, each pixel just covers 2× more |
| Focal length in pixels | fy ≈ **174** px | fy ≈ **87** px (if the FOV is 70°) | pixel-based math (e.g. distance from object size) must be halved |
| Principal point | exact image centre | **may be off-centre** (see below) | calibrate instead of assuming the centre (80.5, 60.5) |
| Pixel data | grayscale | raw **Bayer** mosaic → debayered color | debayering adds color fringes on edges; convert to gray if your code is grayscale |
| Bayer pattern | — | `BG` or `RG` | depends on the sensor flip and the subsampling; check once per build |
| Frame rate / latency | 20 fps, no latency | about **2–3 fps**, ≥ 400 ms between frames, plus WiFi delay | control loops on vision must be much slower; frames can be dropped |
| Exposure | constant scene lighting | auto exposure/gain (AEG), noise, motion blur | thresholds tuned in sim may fail; normalise or adapt |
| Lens | ideal pinhole | real wide-angle lens, usually some distortion | undistort real frames before comparing with the sim |

**Why the FOV doesn't shrink at QQVGA.** In the GAP8 SDK's Himax driver,
`PI_CAMERA_QQVGA` sets the sensor's 2:1 readout/binning registers
(`HIMAX_BINNING_MODE`, `HIMAX_READOUT_X/Y`). The sensor reads every other
pixel pair in both directions instead of cropping the middle of the image. You
get the same scene at half the resolution: the field of view stays the same,
and the focal length *in pixels* halves. The output is still a Bayer mosaic,
which is why debayering works.

**Why the Bayer pattern can change.** The streamer writes `3` to the sensor's
orientation register (`IMG_ORIENTATION`, mirror + flip) so the image is
upright on the drone. Flipping both axes of a mosaic swaps which color the
first pixel has (an RGGB mosaic read backwards starts with B), and 2:1
subsampling can shift it again. That's why viewers disagree on `BG` vs `RG`.

**Why the principal point may be off-centre.** The sensor's full array is
324 × 324. A QVGA image (244 rows) is only centred if the sensor's QVGA window
is enabled, and the GAP SDK driver leaves that register off by default.
Bitcraze's newer streamer added a `CAMERA_QVGA_WINDOW_ENABLE` option for this.
With the old streamer, the rows you receive may be a band of the full readout
rather than a centred crop, both at QVGA and at QQVGA. The vertical FOV is
then smaller than the full sensor's, and the optical centre is not in the
middle of the image. Calibrate rather than assume.

### Make the simulator match your deck

**1. Same resolution and frame rate.** `examples/launch_camera_swarm.sh`
passes camera options through `CAM_ARGS`:

```console
(container) $ CAM_ARGS="--cam-width 162 --cam-height 122 --cam-fps 2.5" \
      bash ~/my_code/examples/launch_camera_swarm.sh -s ~/my_code/scenes/scene_lab_example.xml -- 0,0
```

The simulator keeps the vertical FOV fixed when you change the resolution, so
162 × 122 gives the same 70° view at half the pixels — the same relationship
as the real QQVGA mode. (With the stock `sitl_camera.sh`, add the same three
options to its `crazysim.py` line.)

**2. Measure the real camera.** Print a checkerboard (e.g. 9 × 6 inner
corners, 25 mm squares), save 20–40 frames of it from different angles, and
run the calibration tool:

```console
$ python3 examples/aideck_opencv_viewer.py --uri tcp://192.168.4.1:5000 --debayer --save calib_frames
$ python3 tools/aideck_calibrate.py calib_frames --cols 9 --rows 6 --square 0.025
fx = ... px   fy = ... px
cx = ... px   cy = ... px   (image centre: 80.5, 60.5)
FOV: horizontal ... deg, vertical ... deg

Simulator equivalent (MuJoCo <camera> on the drone body):
  simple : fovy="..."
  exact  : resolution="162 122" sensorsize="1 1" focalpixel="... ..." principalpixel="... ..."
```

The tool was checked by "calibrating" the simulator's own camera, and it
recovers the configured intrinsics (fy ≈ 87 px at 162 × 122, 70°), including
an off-centre principal point.

**3. Put the numbers into the simulator.** The AI-deck camera is defined on
the drone model as `fpv_cam`. For the simple version, change its `fovy` to
the measured vertical FOV (`64.0` below is only an example):

```console
(container) $ cd ~/CrazySim/crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco
(container) $ sed -i 's/<camera name="fpv_cam" pos="0.03 0 0" euler="0 -90 -90" fovy="70"/<camera name="fpv_cam" pos="0.03 0 0" euler="0 -90 -90" fovy="64.0"/' \
      drone-models/drone_models/data/cf2x_T350.xml
```

For the exact version (including an off-centre principal point), replace
`fovy="70" resolution="640 480"` with the "exact" line the tool prints. MuJoCo
does not allow `fovy` together with `sensorsize`, so `fovy` must go:

```console
(container) $ sed -i 's/euler="0 -90 -90" fovy="70" resolution="640 480"/euler="0 -90 -90" resolution="162 122" sensorsize="1 1" focalpixel="87.0 87.0" principalpixel="10.0 -8.0"/' \
      drone-models/drone_models/data/cf2x_T350.xml
```

(with your own numbers), and keep `--cam-width`/`--cam-height` equal to that
`resolution`. Edit the XML of the model you fly (`cf2x_T350.xml`,
`cf2x_L250.xml`, …). The change is inside the container, so
re-apply it after `docker compose down`, or add the `sed` line to the
`Dockerfile`.

**4. Undistort real frames.** MuJoCo renders an ideal pinhole camera. Load
`calib_frames/calibration.npz` and run `cv2.undistort(frame, K, dist)` on real
frames before they reach code that was tuned in simulation.

**5. Decide on color.** The simulator streams grayscale. If your pipeline needs
color (e.g. YOLO), test it on real frames. If it can run on grayscale, convert
the debayered real frames with `cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)`, so the
same code runs on both. Then only the URI differs: `tcp://127.0.0.1:5050` in
simulation, `tcp://192.168.4.1:5000` on the drone.

## Grayscale AI-deck

The grayscale deck doesn't need the color streamer. Use the JPEG/memcpy fix
from the
[aideck_fixes README](https://github.com/dmz44/aideck_fixes#contents-of-changes-to-gap8-code)
(grayscale images compress well as JPEG, which is what makes the stream
stable). In Bitcraze's `opencv-viewer.py`, comment out the
`cv2.cvtColor(..., COLOR_BayerBG2BGRA)` line and the "Color" window, since
there is no color to reconstruct. The grayscale deck runs at QVGA, so the
simulator's default 324 × 244 already matches its resolution.

## Troubleshooting

| Symptom | Check |
|---|---|
| `myssid` never appears | Password at least 8 characters? Was the STM32 reflashed (look for `AI-deck will become access point` in the console)? Did you update the ESP32 with a recent release first? |
| Laptop joins, but the viewer can't connect | Use `192.168.4.1` port `5000`. Only one client at a time: close cfclient's AI-deck tab and any other viewer. |
| A few frames, then the stream stops | Increase the `vTaskDelay(400)`, stay at QQVGA, move closer to the drone |
| `cannot reshape` / `Buffer mismatch` | The viewer expects another size: the color streamer sends 162 × 122, the stock one 324 × 244 |
| Gray image with a fine grid pattern | That's raw Bayer. Debayer it (`--debayer`, or the "Color" window) |
| Red and blue swapped | Try the other Bayer pattern (`BG` ↔ `RG`) |
| Build errors after `git pull` in aideck-gap8-examples | You left the pinned commit; `git checkout 725a350` again, or port the fix (see the version warning) |
