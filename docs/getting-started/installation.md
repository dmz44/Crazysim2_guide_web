# Installing the host software

You need a PC that can run **Ubuntu 24.04** with a reasonably modern **NVIDIA
GPU**. Docker makes the simulator itself portable, but the host needs Docker,
the NVIDIA Container Toolkit, and an X server for the simulator window.

:::{tip}
**Windows 11** works through WSL2 + Docker Desktop (the compose file already
mounts `/mnt/wslg` and `/dev/dxg` for WSLg GPU rendering), but expect extra
configuration. **macOS** is not supported for GPU rendering.
:::

## 1. Base packages

```console
$ sudo apt update && sudo apt upgrade
$ sudo apt -y install vim net-tools openssh-server curl git
```

## 2. Docker Engine

Follow the official guide (<https://docs.docker.com/engine/install/ubuntu/>);
the short version is:

```console
$ sudo apt-get remove docker docker-engine docker.io containerd runc   # old versions, if any
$ sudo apt-get install ca-certificates curl gnupg
$ sudo install -m 0755 -d /etc/apt/keyrings
$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
$ sudo chmod a+r /etc/apt/keyrings/docker.gpg
$ echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
$ sudo apt-get update
$ sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Let your user run Docker without `sudo`, then log out and back in (or reboot):

```console
$ sudo usermod -aG docker $USER
$ newgrp docker
$ docker run hello-world
```

## 3. NVIDIA Container Toolkit

This lets the container use your GPU for MuJoCo/Gazebo rendering.

```console
$ curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
$ curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
$ sudo apt-get update
$ sudo apt-get install -y nvidia-container-toolkit
$ sudo nvidia-ctk runtime configure --runtime=docker
$ sudo systemctl restart docker
```

Check that the driver is visible: `nvidia-smi` should list your GPU.

## 4. (For real drones) Crazyradio USB access

Only needed when you move to hardware ({doc}`../guides/sim2real`). Add the
Bitcraze udev rules on the **host** so the Crazyradio can be used without root:

```console
$ sudo groupadd plugdev; sudo usermod -a -G plugdev $USER
$ cat <<'EOF' | sudo tee /etc/udev/rules.d/99-bitcraze.rules
# Crazyradio (normal operation)
SUBSYSTEM=="usb", ATTRS{idVendor}=="1915", ATTRS{idProduct}=="7777", MODE="0664", GROUP="plugdev"
# Bootloader
SUBSYSTEM=="usb", ATTRS{idVendor}=="1915", ATTRS{idProduct}=="0101", MODE="0664", GROUP="plugdev"
# Crazyflie (over USB)
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", MODE="0664", GROUP="plugdev"
EOF
$ sudo udevadm control --reload-rules && sudo udevadm trigger
```

The container runs `privileged` with host networking, so once the host can see
the radio, cflib inside the container can too.

Next: {doc}`container`.
