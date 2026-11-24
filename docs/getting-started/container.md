# Building and using the container

## Build it (once)

```console
$ mkdir -p ~/crazyflie_docker/my_code
$ cd ~/crazyflie_docker
$ git clone https://github.com/dmz44/Crazyflie_Simulator_Container.git
$ cp Crazyflie_Simulator_Container/Dockerfile Dockerfile
$ cp Crazyflie_Simulator_Container/docker-compose.yml docker-compose.yml
$ HOST_UID=$(id -u) USER_HOME=$HOME docker compose up -d --build
```

The first build downloads ROS 2 Humble and Gazebo Garden and compiles the SITL
firmware, so it takes a while. The image contains:

- ROS 2 Humble desktop, Gazebo Garden, MuJoCo (pip)
- [CrazySim](https://github.com/gtfactslab/CrazySim) with the SITL firmware already built
- cflib (built from source, with the UDP driver) and cfclient

The example scripts, scenes and tools used in this guide are in the guide's
own repository. Copy them into your shared folder so you can use them inside
the container:

```console
$ cd ~/crazyflie_docker
$ git clone https://github.com/dmz44/Crazysim2_guide_web.git
$ cp -r Crazysim2_guide_web/{examples,scenes,tools} ~/crazyflie_docker/my_code/
```

:::{admonition} Recommended Dockerfile additions
:class: tip

The cflib repository moved most of its examples (`fpv.py`,
`circling_square_demo.py`, `multiranger_pointcloud.py`, swarm demos) to
[bitcraze/crazyflie-demos](https://github.com/bitcraze/crazyflie-demos) in
April 2026, so a fresh build no longer has them under
`crazyflie-lib-python/examples/`. Add these lines near the end of the
`Dockerfile` (before `WORKDIR /root/CrazySim/crazyflie-firmware`) to get the
demos plus the packages used by the AI-deck and 3D-scan sections, then rebuild:

```dockerfile
# Demos that used to live in crazyflie-lib-python/examples
RUN git clone --depth 1 https://github.com/bitcraze/crazyflie-demos.git /root/crazyflie-demos
# AI-deck viewer + 3D-scan conversion tools used in this guide
RUN pip3 install --no-cache-dir opencv-python trimesh fast_simplification coacd
```
:::

## Every boot

Allow the container to open windows on your display, start it, and enter it:

```console
$ xhost +local:root
$ cd ~/crazyflie_docker
$ HOST_UID=$(id -u) USER_HOME=$HOME docker compose up -d
$ docker exec -it remote_pc_humble bash
```

You land in `~/CrazySim/crazyflie-firmware`, which is where every launch
command in this guide is run from. Open as many terminals as you need with the
same `docker exec` command — typically one for the simulator and one for your
script.

When you are done:

```console
$ docker compose down     # stop and remove the container (resets it)
$ docker compose stop     # or: pause it, keeping its temporary state
```

## The shared folder

| Host | Container |
|---|---|
| `~/crazyflie_docker/my_code` | `~/my_code` (`/root/my_code`) |

Edit files on the host with any editor (VS Code, etc.) and run them in the
container — changes appear instantly. **Only this folder survives**
`docker compose down`. A `sudo apt install` or a file you create elsewhere in
the container vanishes when the container is removed. That is fine for quick
experiments; to make a change permanent, put it in the `Dockerfile` and
rebuild:

```console
$ docker compose up -d --build
```

:::{tip}
If the simulator starts behaving strangely (drones not connecting, stale
firmware processes), a `docker compose down` followed by `up -d` gives you a
clean slate.
:::
