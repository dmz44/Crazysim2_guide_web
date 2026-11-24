# Pre-flight checklist for real drones

Use this list **before every flight** with real Crazyflies. Most crashes in the
lab come from a handful of small things: a prop on the wrong motor, an
off-centre battery, a drone that moved during its self-test, a stale state
estimate. Each check takes seconds.

Print it, or keep this page open next to cfclient.

## Before the session (once)

- [ ] **Code passed in simulation**: same script, same flight area, with
      `--sensor-noise --ground-effect` (and `--downwash` for swarms), and the
      measured mass (`-M`). See {doc}`sim2real`.
- [ ] **Firmware**: all drones on the same, recent Crazyflie release, flashed
      with their decks mounted.
- [ ] **Lighthouse**: base stations powered and not moved since the last
      calibration; every drone has the shared geometry imported
      ({doc}`lighthouse`).
- [ ] **Arena**: floor clear; no people, bags or cables in the flight volume;
      no mirrors or direct sunlight on the base stations.
- [ ] **Batteries**: charged. Keep spares charging.
- [ ] **Emergency stop**: one person on cfclient (or a gamepad) who can cut
      the motors at any time, and who is *not* also the person typing commands.
- [ ] **Radio addresses**: every drone you will connect to has a unique
      address and is labelled.

## Before every flight

### Hardware

- [ ] **Propellers.** CW and CCW props on the correct motors, **convex side
      and centre ring facing up**, pushed fully onto the shafts. No chips or
      cracks.
- [ ] **Props spin freely.** Turn each one by hand. No hair or debris around
      the shaft. A motor that feels **gritty or resistant** gets replaced.
- [ ] **Frame.** Friction-fit parts (motor mounts, arms, decks, pin headers)
      are firmly seated.
- [ ] **Battery centred** in its holder, so the drone doesn't drift on take-off.
      Battery **lead tucked away** from the props.
- [ ] **Decks** firmly seated on their pins; the Lighthouse deck is not
      covered by cables or tape.

### Power-on

- [ ] Place the drone on a **flat, level surface** (at its start position in
      the arena) **before** switching it on.
- [ ] Switch on and **don't touch it** while the self-test runs (the
      **front-right LED blinks red** during start-up). Moving it now corrupts
      the gyro calibration.
- [ ] After a **crash** or after sitting on the ground for a long time,
      **power-cycle** the drone so the state estimate (Kalman filter) starts
      fresh.

### Positioning (cfclient)

- [ ] Connect. In the **Lighthouse tab**, *Receiving*, *Calibration*,
      *Geometry* and *Estimator* are **all green**, and the status reads
      **LH ready**. The deck LED is green.
- [ ] In **Flight Control**, the state estimate **matches where the drone is**
      (e.g. its spawn point) and **does not jump or drift** while the drone
      sits still.
- [ ] `z` reads about **0** on the floor.
- [ ] Battery voltage at rest is **≥ 3.8 V** (fresh LiPo ≈ 4.2 V).

### Test hover

- [ ] Do a short **hover from cfclient** first (*Flight Control → Take off*,
      then *Land*). The drone should rise straight up and hold position.
- [ ] Only then run your **Python script**: start with one drone, low
      (≤ 0.5 m), slow.

### Your script

- [ ] **URI** points to the real drone (`radio://0/80/2M/E7E7E7E7E7` or the
      drone's own address), not `udp://127.0.0.1:...`.
- [ ] **Arming request** is sent (`cf.platform.send_arming_request(True)`).
- [ ] **Safety envelope**: maximum height and arena bounds enforced in code.
- [ ] **Lands on error**: `try/finally` (or the commander's context manager)
      lands on exceptions and `Ctrl+C`.
- [ ] **Estimator reset** before take-off (`kalman.resetEstimation`) and
      high-level commander enabled (`commander.enHighLevel = 1`).

## After the flight

- [ ] Land and **power off** before picking up the drone.
- [ ] Check props and motors again after any hard landing or crash.
- [ ] Unplug and **store batteries** safely; don't leave LiPos charging
      unattended.
- [ ] Note anything odd (drift, a noisy motor) so the next person knows.

## Quick troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| **Drifts hard on take-off** | battery off-centre; failing motor | re-centre the battery; clear debris from motor shafts; replace the motor |
| **Flips immediately** | props on the wrong motors or upside down | check CW/CCW placement and that props are convex side up |
| Wobbles or climbs unevenly | chipped prop, loose motor mount | replace the prop; reseat the mount |
| **Not receiving**, Lighthouse LED **orange** | occlusion or IR interference | restore line of sight; block sunlight; cover mirrors |
| **No geo/calib**, Lighthouse LED **red** | geometry missing on this drone | import the shared configuration, or re-run the geometry setup ({doc}`lighthouse`) |
| Estimate jumps while sitting still | reflections; stale estimator | fix the room; power-cycle the drone |
| Won't take off from a script, but cfclient works | not armed; high-level commander off; wrong URI | arming request; `commander.enHighLevel = 1`; check the URI |
| Behaves differently from the simulation | mass, positioning mode or frame mismatch | see {doc}`sim2real` |
