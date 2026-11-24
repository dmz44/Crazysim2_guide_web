#!/usr/bin/env python3
"""
aideck_calibrate.py — calibrate the AI-deck camera from saved frames and print
the matching CrazySim (MuJoCo) camera settings.

1. Print a checkerboard (e.g. 9 x 6 inner corners, 25 mm squares) and tape it
   flat to a board.
2. Save 20-40 frames of it from different angles and distances, filling
   different parts of the image:
       python3 examples/aideck_opencv_viewer.py --uri tcp://192.168.4.1:5000 \
           --debayer --save calib_frames
3. Run:
       python3 tools/aideck_calibrate.py calib_frames --cols 9 --rows 6 --square 0.025

Prints fx, fy, cx, cy, distortion, the equivalent vertical FOV, and a
<camera> line you can use for the simulator's fpv_cam.
"""

import argparse
import glob
import math
import os
import sys

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder', help='folder with PNG/JPG frames')
    ap.add_argument('--cols', type=int, default=9, help='inner corners per row')
    ap.add_argument('--rows', type=int, default=6, help='inner corners per column')
    ap.add_argument('--square', type=float, default=0.025, help='square size [m]')
    ap.add_argument('--show', action='store_true', help='show detected corners')
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.folder, '*.png')) +
                   glob.glob(os.path.join(args.folder, '*.jpg')))
    if not files:
        sys.exit(f'No images in {args.folder}')

    pattern = (args.cols, args.rows)
    objp = np.zeros((args.cols * args.rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:args.cols, 0:args.rows].T.reshape(-1, 2) * args.square

    # Use the most common image size; skip anything else (e.g. a stray PNG).
    images = {}
    for f in files:
        img = cv2.imread(f, cv2.IMREAD_UNCHANGED)
        if img is not None:
            images[f] = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sizes = [g.shape[::-1] for g in images.values()]
    size = max(set(sizes), key=sizes.count)

    obj_pts, img_pts = [], []
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    for f, gray in images.items():
        if gray.shape[::-1] != size:
            print(f'skip {os.path.basename(f)}: size {gray.shape[::-1]} != {size}')
            continue
        ok, corners = cv2.findChessboardCorners(gray, pattern, None)
        if not ok:
            continue
        corners = cv2.cornerSubPix(gray, corners, (3, 3), (-1, -1), crit)
        obj_pts.append(objp)
        img_pts.append(corners)
        if args.show:
            vis = cv2.drawChessboardCorners(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
                                            pattern, corners, ok)
            cv2.imshow('corners', cv2.resize(vis, None, fx=3, fy=3))
            cv2.waitKey(150)

    print(f'Checkerboard found in {len(img_pts)} of {len(files)} images ({size[0]}x{size[1]})')
    if len(img_pts) < 8:
        sys.exit('Need at least ~8 good views (aim for 20+).')

    rms, K, dist, _, _ = cv2.calibrateCamera(obj_pts, img_pts, size, None, None)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    w, h = size
    fovy = math.degrees(2 * math.atan(h / (2 * fy)))
    fovx = math.degrees(2 * math.atan(w / (2 * fx)))

    print(f'\nRMS reprojection error: {rms:.3f} px  (below ~0.5 px is good)')
    print(f'fx = {fx:.1f} px   fy = {fy:.1f} px')
    print(f'cx = {cx:.1f} px   cy = {cy:.1f} px   (image centre: {(w - 1) / 2:.1f}, {(h - 1) / 2:.1f})')
    print(f'distortion k1 k2 p1 p2 k3 = {np.round(dist.ravel(), 4).tolist()}')
    print(f'FOV: horizontal {fovx:.1f} deg, vertical {fovy:.1f} deg')

    print('\nSimulator equivalent (MuJoCo <camera> on the drone body):')
    print(f'  simple : fovy="{fovy:.1f}"   (keeps the principal point centred)')
    # MuJoCo's principalpixel is an offset from the image centre; checked
    # empirically: +x moves the principal point left, +y moves it up.
    # OpenCV puts pixel centres on integers, so the image centre is (w-1)/2.
    print(f'  exact  : resolution="{w} {h}" sensorsize="1 1" '
          f'focalpixel="{fx:.1f} {fy:.1f}" '
          f'principalpixel="{(w - 1) / 2 - cx:.1f} {(h - 1) / 2 - cy:.1f}"')
    print('MuJoCo renders an ideal pinhole camera: undistort real frames with '
          'cv2.undistort(img, K, dist) before comparing them with simulated ones.')

    np.savez(os.path.join(args.folder, 'calibration.npz'), K=K, dist=dist, size=size)
    print(f'\nSaved K and dist to {os.path.join(args.folder, "calibration.npz")}')


if __name__ == '__main__':
    main()
