# Calibrating the Lighthouse positioning system

The Lighthouse system gives a real Crazyflie the same thing the simulator
gives it for free: an **absolute position in a world frame**. The two base
stations sweep the room with infrared lasers, and the Lighthouse deck on the
drone times the sweeps to work out its pose. For your simulated code to work
on hardware, the Lighthouse frame must match the simulator's world frame:
same origin, same +X direction, Z up, metres.

This page follows Bitcraze's
[Getting started with the Lighthouse system](https://www.bitcraze.io/documentation/tutorials/getting-started-with-lighthouse/)
tutorial and the
[cfclient Lighthouse tab guide](https://www.bitcraze.io/documentation/repository/crazyflie-clients-python/2026.8/userguides/userguide_client/lighthouse_tab/),
plus the lab's notes on placement and troubleshooting.

:::{note}
Bitcraze rewrote the geometry wizard in the **2026.08** cfclient release
(sample collection with *Origin / X-axis / XY-plane / XYZ-space /
Verification* steps and automatic upload). This page describes that version.
In older clients the last step was a separate **Write to Crazyflie** button.
If you have one, press it, or the geometry won't survive a reboot.
:::

## What you need

| Item | Notes |
|---|---|
| Crazyflie 2.1 (or 2.1+, Brushless) | with the **Lighthouse positioning deck** mounted firmly and parallel to the PCB |
| 2 base stations (V2 recommended; 2–4 supported) | V1 stations also work, but only two of them |
| Crazyradio 2.0 / PA | udev rules from {doc}`../getting-started/installation` |
| Latest cfclient | `pip install cfclient` (host or container) |
| Tape measure and floor tape | to mark the origin and the 1 m X-axis point |

On Linux, add yourself to the `dialout` group once, so cfclient can talk to a
base station over USB when you set its channel:

```console
$ sudo usermod -aG dialout $USER     # then log out and back in
```

## 1. Place the base stations

- Mount them **high** (wall or tripod), **at least 50 cm above** the highest
  point you will fly, and tilt them down toward the flight area. In the lab,
  two stations about **90° apart** (seen from above), each tilted about
  **45° down**, give good coverage.
- Two stations cover roughly **4 × 4 × 2 m**. The drone must stay within
  **6 m** of at least one station, with a clear line of sight.
- Remove or cover **mirrors and shiny surfaces**, and block **direct
  sunlight**. Both create false sweeps.
- Stations only need power. USB is used once, to set the channel.
- **Don't move them afterwards.** Any bump means re-estimating the geometry
  (step 5).

## 2. Update the firmware

Flash the latest Crazyflie release from cfclient (*Connect → Bootloader*)
**with the Lighthouse deck mounted**. The deck's firmware is updated in the
same step. Use the same release on every drone.

## 3. Give each base station its own channel (V2)

Each V2 base station needs a **unique channel**. In cfclient, open
*View → Tabs → Lighthouse Positioning*, then for **one station at a time**:

1. Connect the station to the PC with micro-USB.
2. Click **Set BS channel** → **Scan**. **Current channel** shows its channel
   (often `0` if it was never set).
3. Enter a new value (`1`–`4`) in **Change Channel**, click **Set Channel**,
   and wait for "success!".

Label each station with its channel. (V1 stations instead use the button on
the back: modes `b`/`c` without a sync cable, `a`/`b` with one.)

## 4. Tell the drone which system it is using

Connect to the Crazyflie in cfclient, open the Lighthouse tab, click
**Switch BS version** and choose V1 or V2. The setting is stored on the drone.

Place the drone where it can see all base stations and wait about
**20 seconds**. The *Calibration* column of the base station grid turns
green (blue at first means stored data that hasn't been confirmed yet).

## 5. Estimate the geometry (set the origin)

This step defines the coordinate system. **Use the same origin and +X
direction as the simulator**, so that a spawn file position like `(1.0, 0.0)`
means the same spot in the room as in the simulation:

1. On the floor, tape a cross at the **origin** and a mark **exactly 1.0 m
   along +X**. Pick +X to match your simulated scene, e.g. "towards the
   workbench".
2. In the Lighthouse tab click **Start set up**. In *Sample Collection*, step
   through with `<` / `>` and press the big button to measure each sample.
   Hold the drone still during each measurement.

| Sample | Where to put the drone | How many |
|---|---|---|
| **Origin** | on the origin cross, flat on the floor | 1 |
| **X-axis** | on the mark **1.0 m along +X** (this also sets the scale) | 1 |
| **XY-plane** | flat on the floor, **not** on the X-axis, spread over the arena | **4 or more** |
| **XYZ-space** | carried through the flight volume at different heights; rotate it left–right around its Z-axis and hold still until confirmed (or press **Sample Position**) | as many as practical, especially where you will fly |
| **Verification** (optional) | anywhere; not used for the estimate, only to check it | a few |

3. The geometry is estimated and uploaded to the drone automatically. The
   status reads **Uploaded** in green.

:::{important}
Keep the deck parallel to the floor for the origin, X-axis and XY-plane
samples. These define the floor plane. A drone tilted on a cable or an uneven
spot puts a tilt into the whole coordinate system, and your "flat" flight at
0.5 m will not be flat.
:::

## 6. Check the result

- **Sample details.** Click **Show** under *Sample Details*. In the
  *Samples* table, errors (*Err (mm)*) should stay **below about 10 mm**.
  Larger errors mean the base stations disagree about that sample. Delete
  bad *estimation* samples. For bad *verification* samples, add XYZ-space
  samples in that area and let it re-estimate.
- **Base stations table.** Every station must be *linked* to at least one
  other station (a red *Links* cell means it isn't). More links make a more
  robust solution.
- **3D view and deck LED.** The 3D view shows the base stations with their
  channels and the drone as a blue dot. The deck LED should be **green**,
  and the status should read **LH ready**.
- **Walk the arena.** Carry the drone slowly around the whole flight volume
  while watching the position in the Lighthouse tab or in *Flight Control*.
  The estimate must not jump. Wherever it does, there is occlusion or a
  reflection; fix the room, or add XYZ-space samples there.
- **Check known points.** Put the drone on the origin and on the 1 m mark;
  the position should read about `(0, 0, 0)` and `(1, 0, 0)`. Then check one
  of your simulated spawn points.

## 7. Use the same geometry on every drone

The geometry is stored in the drone's persistent memory. For a swarm, don't
re-estimate on each drone. Copy the one you just made:

1. On the calibrated drone: **Export configuration** → save e.g.
   `lab_lighthouse.yaml` (keep it in `~/my_code` or in the repository).
2. On every other drone: connect, then **Import configuration** with that
   file. The type, calibration and geometry are written to its persistent
   memory.

All drones now share one coordinate system: the same one your spawn file
uses in the simulator.

## When to recalibrate

- A base station was moved, bumped, or re-mounted.
- The *Calibration* column turns **orange**: the received calibration doesn't
  match the stored data.
- The known-point check is off by more than a couple of centimetres, or
  drones disagree about the same spot.

Re-estimating is quick: **Clear all samples**, repeat step 5, then export and
import again.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| **Not receiving**, deck LED **orange** | occlusion or IR interference | restore line of sight; block direct sunlight; cover mirrors |
| **No geo/calib**, deck LED **red** | geometry or calibration data missing on this drone | redo step 5, or **Import configuration** |
| Position jumps in parts of the room | reflections, or only one station visible there | remove reflective items; add XYZ-space samples there; adjust station placement |
| Floor not at z = 0, or the whole frame tilted | origin/XY-plane samples taken with the drone not flat | clear samples and redo step 5 on a flat floor |
| A swarm member's positions are offset | it has an old or different geometry | import the shared configuration file again |
| Simulated path ends up in the wrong place in the room | Lighthouse origin/+X differ from the simulator's | re-mark the origin and +X to match the scene, then redo step 5 |

Next: {doc}`preflight-checklist`.
