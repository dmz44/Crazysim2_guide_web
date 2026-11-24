#!/usr/bin/env python3
"""
make_spawn_file.py — generate a CrazySim spawn-coordinates file.

CrazySim's ``sitl_multiagent_text.sh -f <file>`` reads one "x,y" line per
drone from ``crazyflie-firmware/tools/crazyflie-simulation/drone_spawn_list/``.
Drone i (0-based, line order) gets cflib URI udp://127.0.0.1:<19850+i>.

    python3 make_spawn_file.py grid   --rows 2 --cols 4 --spacing 0.6  -o grid_8.txt
    python3 make_spawn_file.py circle -n 6 --radius 1.0                -o circle_6.txt
    python3 make_spawn_file.py line   -n 5 --spacing 0.5 --x0 -1       -o line_5.txt

Use ``--install`` to also copy it into drone_spawn_list/ (run inside the
container). Because the container is reset by ``docker compose down``, keep the
original in ~/my_code and re-install it when needed.
"""

import argparse
import math
import os
import shutil

DEFAULT_SPAWN_DIR = os.path.expanduser(
    '~/CrazySim/crazyflie-firmware/tools/crazyflie-simulation/drone_spawn_list')


def grid(rows, cols, spacing, x0, y0):
    return [(x0 + c * spacing, y0 + r * spacing) for r in range(rows) for c in range(cols)]


def circle(n, radius, x0, y0):
    return [(x0 + radius * math.cos(2 * math.pi * i / n),
             y0 + radius * math.sin(2 * math.pi * i / n)) for i in range(n)]


def line(n, spacing, x0, y0):
    return [(x0 + i * spacing, y0) for i in range(n)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shape', choices=['grid', 'circle', 'line'])
    ap.add_argument('-n', type=int, default=4, help='drones (circle/line)')
    ap.add_argument('--rows', type=int, default=2)
    ap.add_argument('--cols', type=int, default=2)
    ap.add_argument('--spacing', type=float, default=0.5, help='[m]')
    ap.add_argument('--radius', type=float, default=1.0, help='[m]')
    ap.add_argument('--x0', type=float, default=0.0)
    ap.add_argument('--y0', type=float, default=0.0)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--install', action='store_true',
                    help=f'also copy into {DEFAULT_SPAWN_DIR}')
    ap.add_argument('--spawn-dir', default=DEFAULT_SPAWN_DIR)
    args = ap.parse_args()

    if args.shape == 'grid':
        pts = grid(args.rows, args.cols, args.spacing, args.x0, args.y0)
    elif args.shape == 'circle':
        pts = circle(args.n, args.radius, args.x0, args.y0)
    else:
        pts = line(args.n, args.spacing, args.x0, args.y0)

    min_gap = min((math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1:]),
                  default=float('inf'))
    if min_gap < 0.3:
        print(f'WARNING: closest drones are {min_gap:.2f} m apart; '
              'keep >= 0.3 m (more with --downwash).')

    with open(args.output, 'w') as f:
        for x, y in pts:
            f.write(f'{x:.3f},{y:.3f}\n')
    print(f'Wrote {len(pts)} positions to {args.output}')
    for i, (x, y) in enumerate(pts):
        print(f'  cf{i}: ({x:+.2f}, {y:+.2f})  udp://127.0.0.1:{19850 + i}')

    if args.install:
        os.makedirs(args.spawn_dir, exist_ok=True)
        dst = os.path.join(args.spawn_dir, os.path.basename(args.output))
        shutil.copy(args.output, dst)
        print(f'Installed -> {dst}')
        print(f'Launch: bash tools/crazyflie-simulation/simulator_files/mujoco/launch/'
              f'sitl_multiagent_text.sh -f {os.path.basename(args.output)}')


if __name__ == '__main__':
    main()
