#!/usr/bin/env python3
"""
fly_square.py — one script, two targets: CrazySim (SITL) or a real Crazyflie.

Takes off, flies a square with the high-level commander, and lands, while
logging the state estimate to a CSV so you can compare sim and real runs.

    # simulator (default)
    python3 fly_square.py
    # real drone over Crazyradio
    python3 fly_square.py --target real                 # radio://0/80/2M/E7E7E7E7E7 (Bitcraze default)
    # bigger square, higher, slower
    python3 fly_square.py --size 1.0 --height 0.8 --speed 0.3

The only things that change between sim and real are the URI and the
pre-flight checks. Keep it that way: if you need an "if sim:" branch in your
flight logic, the simulator is not matching your hardware yet.
"""

import argparse
import csv
import math
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger

SIM_URI = 'udp://127.0.0.1:19850'
REAL_URI = 'radio://0/80/2M/E7E7E7E7E7'

# Safety envelope (metres). Anything outside is refused before take-off.
MAX_HEIGHT = 1.5
MAX_XY = 2.0
MIN_VBAT_REAL = 3.8   # volts; a fresh 1S LiPo is ~4.2 V


def read_once(scf, variables):
    """Read a handful of log variables once."""
    lg = LogConfig(name='once', period_in_ms=50)
    for name, typ in variables:
        lg.add_variable(name, typ)
    with SyncLogger(scf, lg) as logger:
        for _, data, _ in logger:
            return data


def reset_estimator(scf):
    cf = scf.cf
    cf.param.set_value('kalman.resetEstimation', '1')
    time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0')
    # Wait until the position variance has settled.
    lg = LogConfig(name='Kalman Variance', period_in_ms=100)
    for v in ('kalman.varPX', 'kalman.varPY', 'kalman.varPZ'):
        lg.add_variable(v, 'float')
    history = {v: [1000.0] * 10 for v in ('kalman.varPX', 'kalman.varPY', 'kalman.varPZ')}
    with SyncLogger(scf, lg) as logger:
        for _, data, _ in logger:
            for k in history:
                history[k].append(data[k])
                history[k].pop(0)
            if all(max(h) - min(h) < 0.001 for h in history.values()):
                return


def preflight(scf, target):
    est = read_once(scf, [('stateEstimate.x', 'float'), ('stateEstimate.y', 'float'),
                          ('stateEstimate.z', 'float'), ('pm.vbat', 'float')])
    x, y, z, vbat = (est['stateEstimate.x'], est['stateEstimate.y'],
                     est['stateEstimate.z'], est['pm.vbat'])
    print(f'Start pose  x={x:+.2f} y={y:+.2f} z={z:+.2f}   battery {vbat:.2f} V')
    if target == 'real':
        if vbat < MIN_VBAT_REAL:
            sys.exit(f'Battery too low ({vbat:.2f} V). Charge it first.')
        if abs(z) > 0.15:
            sys.exit(f'Estimated z = {z:.2f} m while sitting on the floor - '
                     'check your positioning system (Lighthouse / mocap / Flow deck).')
    return x, y


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target', choices=['sim', 'real'], default='sim')
    ap.add_argument('--uri', default=None, help='override the URI')
    ap.add_argument('--size', type=float, default=0.5, help='square side [m]')
    ap.add_argument('--height', type=float, default=0.5, help='flight height [m]')
    ap.add_argument('--speed', type=float, default=0.25, help='cruise speed [m/s]')
    ap.add_argument('--log', default=None, help='CSV path (default: square_<target>.csv)')
    args = ap.parse_args()

    uri = args.uri or (SIM_URI if args.target == 'sim' else REAL_URI)
    log_path = args.log or f'square_{args.target}.csv'

    if args.height > MAX_HEIGHT or args.size > MAX_XY:
        sys.exit('Requested square is outside the safety envelope.')

    cflib.crtp.init_drivers()
    print(f'Connecting to {uri} ({args.target})')

    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf
        cf.param.set_value('commander.enHighLevel', '1')
        reset_estimator(scf)
        x0, y0 = preflight(scf, args.target)

        # Log the trajectory in the background.
        rows = []
        lg = LogConfig(name='traj', period_in_ms=20)
        for v in ('stateEstimate.x', 'stateEstimate.y', 'stateEstimate.z',
                  'stabilizer.roll', 'stabilizer.pitch', 'stabilizer.yaw'):
            lg.add_variable(v, 'float')
        lg.data_received_cb.add_callback(
            lambda ts, d, _: rows.append([ts] + [d[k] for k in sorted(d)]))
        cf.log.add_config(lg)
        lg.start()

        hl = cf.high_level_commander
        # SITL auto-arms; recent real firmware (and the Crazyflie 2.1 Brushless)
        # needs an explicit arming request. Harmless if already armed.
        cf.platform.send_arming_request(True)
        time.sleep(1.0)

        try:
            hl.takeoff(args.height, 2.0)
            time.sleep(2.5)

            s = args.size
            corners = [(x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s), (x0, y0)]
            prev = (x0, y0)
            for cx, cy in corners:
                dist = math.hypot(cx - prev[0], cy - prev[1])
                dur = max(dist / args.speed, 1.0)
                print(f'  -> ({cx:+.2f}, {cy:+.2f}, {args.height:.2f})  {dur:.1f}s')
                hl.go_to(cx, cy, args.height, 0.0, dur)
                time.sleep(dur + 0.3)
                prev = (cx, cy)

            hl.land(0.0, 2.0)
            time.sleep(2.5)
        except KeyboardInterrupt:
            print('Interrupted - landing')
            hl.land(0.0, 2.0)
            time.sleep(2.5)
        finally:
            hl.stop()
            lg.stop()

    with open(log_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['timestamp_ms'] + sorted(['stateEstimate.x', 'stateEstimate.y',
                                              'stateEstimate.z', 'stabilizer.roll',
                                              'stabilizer.pitch', 'stabilizer.yaw']))
        w.writerows(rows)
    print(f'Wrote {len(rows)} samples to {log_path}')


if __name__ == '__main__':
    main()
