# CrazySim2 Simulation Guide

**Software-in-the-loop simulation for the Bitcraze Crazyflie, packaged in Docker.**

CrazySim runs the *real* Crazyflie firmware on your PC and connects it to a
physics simulator (MuJoCo or Gazebo). Your cflib scripts, cfclient and
Crazyswarm2 talk to the simulated drone exactly as they would to hardware — you
only change the URI. This guide walks through the containerised setup used for
the Texas State Makerspace Crazyflie digital twin, from a single hovering drone
to swarms, the AI-deck camera, custom and 3D-scanned environments, and
moving your code onto real drones.

```{image} _static/img/lab_example.png
:alt: Three simulated Crazyflies in the example lab scene
:align: center
```

## Where to start

| I want to... | Go to |
|---|---|
| Install Docker + GPU support and build the container | {doc}`getting-started/installation`, {doc}`getting-started/container` |
| Understand ports, backends and drone models | {doc}`getting-started/overview` |
| Fly one simulated Crazyflie from Python | {doc}`guides/single-crazyflie` |
| Fly a swarm (cflib or Crazyswarm2) | {doc}`guides/multiple-crazyflies` |
| Stream the simulated AI-deck camera | {doc}`guides/ai-deck` |
| Put walls, furniture or obstacles in the world | {doc}`guides/adding-objects` |
| Scan a real room/object with a ZED 2 and import it | {doc}`guides/3d-scanned-objects` |
| Move my code from the simulator to real drones | {doc}`guides/sim2real` |

## The two repositories

The simulator and this guide live in separate repositories:

```text
Crazyflie_Simulator_Container/     # the simulator container
├── Dockerfile                     # ROS 2 Humble + Gazebo Garden + MuJoCo + CrazySim + cflib
└── docker-compose.yml             # GPU, X11 display, shared folder ~/crazyflie_docker/my_code

Crazysim2_guide_web/               # this website + the scripts it uses
├── docs/                          # the pages (Sphinx + Read the Docs theme)
├── examples/                      # flight, swarm and AI-deck scripts (copy into my_code/)
├── scenes/                        # example MuJoCo scenes
└── tools/                         # spawn-file generator, ZED scanning, scan → sim converter
```

- Container: <https://github.com/dmz44/Crazyflie_Simulator_Container>
- Guide and scripts: <https://github.com/dmz44/Crazysim2_guide_web>

```{toctree}
:maxdepth: 2
:caption: Getting started

getting-started/overview
getting-started/installation
getting-started/container
```

```{toctree}
:maxdepth: 2
:caption: Simulation guides

guides/single-crazyflie
guides/multiple-crazyflies
guides/ai-deck
guides/adding-objects
guides/3d-scanned-objects
guides/sim2real
```

```{toctree}
:maxdepth: 2
:caption: Reference

reference/launch-options
reference/troubleshooting
reference/publishing-docs
reference/credits
```
