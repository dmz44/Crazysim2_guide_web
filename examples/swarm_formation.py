#!/usr/bin/env python3
"""
swarm_formation.py — fly N Crazyflies in CrazySim (or real) with cflib's Swarm.

Every drone takes off from wherever it was spawned, flies to a slot on a
circle, rotates the circle once, returns to its spawn point and lands.

    # 4 simulated drones (ports 19850..19853)
    python3 swarm_formation.py -n 4
    # real drones: list the radio URIs explicitly
    python3 swarm_formation.py --uris radio://0/80/2M/E7E7E7E701 radio://0/80/2M/E7E7E7E702

Start the simulator first, e.g.
    bash tools/crazyflie-simulation/simulator_files/mujoco/launch/sitl_multiagent_square.sh -n 4
"""

import argparse
import math
import time

import cflib.crtp
from cflib.crazyflie.swarm import CachedCfFactory
from cflib.crazyflie.swarm import Swarm

SIM_BASE_PORT = 19850


def sim_uris(n):
    return [f'udp://127.0.0.1:{SIM_BASE_PORT + i}' for i in range(n)]


def arm_and_enable(scf):
    scf.cf.param.set_value('commander.enHighLevel', '1')
    scf.cf.platform.send_arming_request(True)  # no-op in SITL, needed on newer HW
    time.sleep(0.5)


def take_off(scf, height):
    scf.cf.high_level_commander.takeoff(height, 2.0)
    time.sleep(2.5)


def go_to(scf, x, y, z, duration):
    scf.cf.high_level_commander.go_to(x, y, z, 0.0, duration)
    time.sleep(duration + 0.2)


def land(scf):
    hl = scf.cf.high_level_commander
    hl.land(0.0, 2.0)
    time.sleep(2.5)
    hl.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-n', type=int, default=4, help='number of simulated drones')
    ap.add_argument('--uris', nargs='+', default=None, help='explicit URIs (overrides -n)')
    ap.add_argument('--radius', type=float, default=0.8)
    ap.add_argument('--height', type=float, default=0.6)
    ap.add_argument('--steps', type=int, default=8, help='steps per revolution')
    args = ap.parse_args()

    uris = args.uris or sim_uris(args.n)
    n = len(uris)
    cflib.crtp.init_drivers()
    factory = CachedCfFactory(rw_cache='./cache')

    with Swarm(uris, factory=factory) as swarm:
        print(f'Connected to {n} drones')
        swarm.reset_estimators()          # waits for Kalman to converge on each
        start = swarm.get_estimated_positions()
        for uri, p in start.items():
            print(f'  {uri}: start ({p.x:+.2f}, {p.y:+.2f}, {p.z:+.2f})')

        # Use the centroid of the spawn positions as the circle centre.
        cx = sum(p.x for p in start.values()) / n
        cy = sum(p.y for p in start.values()) / n
        # Give each drone the circle slot nearest its own bearing so paths don't cross.
        uris = sorted(uris, key=lambda u: math.atan2(start[u].y - cy, start[u].x - cx))

        swarm.parallel_safe(arm_and_enable)
        swarm.parallel_safe(take_off, args_dict={u: [args.height] for u in uris})

        try:
            for step in range(args.steps + 1):
                phase = 2 * math.pi * step / args.steps
                targets = {}
                for i, uri in enumerate(uris):
                    a = phase + 2 * math.pi * i / n
                    targets[uri] = [cx + args.radius * math.cos(a),
                                    cy + args.radius * math.sin(a),
                                    args.height,
                                    3.0 if step == 0 else 1.5]
                swarm.parallel_safe(go_to, args_dict=targets)

            home = {u: [p.x, p.y, args.height, 3.0] for u, p in start.items()}
            swarm.parallel_safe(go_to, args_dict=home)
        finally:
            swarm.parallel_safe(land)


if __name__ == '__main__':
    main()
