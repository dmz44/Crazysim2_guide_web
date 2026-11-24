#!/bin/bash
# launch_camera_swarm.sh — N simulated Crazyflies, each with an AI-deck camera.
#
# The stock sitl_camera.sh only starts one drone. This script starts N firmware
# instances, one CPX bridge per drone, and one MuJoCo process with --camera.
#
#   Drone i:  cflib  udp://127.0.0.1:<19850+i>
#             CPX    tcp://127.0.0.1:<5050+i>      (AI-deck stream)
#
# Usage (inside the container):
#   bash ~/my_code/examples/launch_camera_swarm.sh [-s scene.xml] [-m model] X0,Y0 X1,Y1 ...
#   bash ~/my_code/examples/launch_camera_swarm.sh -s ~/my_code/scenes/scene_lab_example.xml -- -2,-1 -2,0
#
# Rendering N cameras is GPU-heavy; drop --cam-fps or the resolution if the
# real-time factor falls below 1.

FW_DIR="${FW_DIR:-$HOME/CrazySim/crazyflie-firmware}"
SIM_DIR="$FW_DIR/tools/crazyflie-simulation/simulator_files/mujoco"
BUILD="$FW_DIR/sitl_make/build"

MODEL="cf2x_T350"
SCENE_ARG=""
while getopts m:s: opt; do
	case "$opt" in
		m) MODEL="$OPTARG";;
		s) SCENE_ARG="--scene $OPTARG";;
		*) exit 1;;
	esac
done
shift $((OPTIND - 1))
[ "$1" == "--" ] && shift
SPAWNS=("$@")
[ ${#SPAWNS[@]} -eq 0 ] && SPAWNS=("0,0" "1,0")
N=${#SPAWNS[@]}

cleanup() {
	pkill -x cf2
	pkill -f crazysim_cpx.py
}
trap cleanup SIGINT SIGTERM EXIT

pkill -x cf2; pkill -f crazysim_cpx.py; pkill -f crazysim.py
sleep 1

for ((i = 0; i < N; i++)); do
	mkdir -p "$BUILD/$i"
	(cd "$BUILD/$i" && stdbuf -oL "$BUILD/cf2" $((19950 + i)) > out.log 2> error.log &)
	python3 "$SIM_DIR/crazysim_cpx.py" --cpx-port $((5050 + i)) \
		--cflib-port $((19850 + i)) --frame-port $((5200 + i)) > /tmp/cpx_$i.log 2>&1 &
	echo "drone $i at (${SPAWNS[$i]}): udp://127.0.0.1:$((19850 + i))  tcp://127.0.0.1:$((5050 + i))"
done
sleep 1

python3 "$SIM_DIR/crazysim.py" --model-type "$MODEL" --port 19950 --vis --camera \
	$SCENE_ARG -- "${SPAWNS[@]}"
