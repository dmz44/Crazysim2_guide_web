#!/usr/bin/env python3
"""
aideck_opencv_viewer.py — receive AI-deck camera frames over CPX with OpenCV.

Works unchanged against
  * CrazySim's emulated AI-deck  (tcp://127.0.0.1:5050, from sitl_camera.sh)
  * a real AI-deck in AP mode    (tcp://192.168.4.1:5000)
  * a real AI-deck in station mode (tcp://<deck-ip>:5000)

    python3 aideck_opencv_viewer.py                       # sim, show window
    python3 aideck_opencv_viewer.py --save frames/        # also save PNGs
    python3 aideck_opencv_viewer.py --edges               # run Canny on each frame
    python3 aideck_opencv_viewer.py --uri tcp://192.168.4.1:5000

Frames from the simulator are 324x244 8-bit grayscale (Himax HM01B0 size).
Real decks may stream raw Bayer, grayscale or JPEG depending on the GAP8
streamer build; the 'format' byte in the image header tells you which.
"""

import argparse
import os
import struct
import threading
import time

import cv2
import numpy as np

import cflib.crtp
from cflib.cpx import CPXFunction
from cflib.crazyflie import Crazyflie

IMG_MAGIC = 0xBC
FMT_RAW, FMT_JPEG = 0, 1


class FrameGrabber(threading.Thread):
    """Reassemble CPX APP packets into images; keep only the latest frame."""

    def __init__(self, cpx):
        super().__init__(daemon=True)
        self._cpx = cpx
        self.lock = threading.Lock()
        self.frame = None
        self.count = 0

    def run(self):
        while True:
            p = self._cpx.receivePacket(CPXFunction.APP)
            if len(p.data) < 11:
                continue
            magic, width, height, depth, fmt, size = struct.unpack('<BHHBBI', p.data[:11])
            if magic != IMG_MAGIC:
                continue
            buf = bytearray()
            while len(buf) < size:
                buf.extend(self._cpx.receivePacket(CPXFunction.APP).data)

            if fmt == FMT_JPEG:
                img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_UNCHANGED)
            else:
                # Don't trust the 'depth' byte (CrazySim sends 8 = bits per
                # pixel, real GAP8 examples send 1 = bytes per pixel).
                # Infer channels from the payload size instead.
                ch = max(1, len(buf) // (width * height))
                img = np.frombuffer(bytes(buf[:width * height * ch]), np.uint8)
                img = img.reshape(height, width) if ch == 1 else img.reshape(height, width, ch)
            if img is None:
                continue
            with self.lock:
                self.frame = img
                self.count += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--uri', default='tcp://127.0.0.1:5050')
    ap.add_argument('--save', default=None, help='directory to save PNG frames')
    ap.add_argument('--edges', action='store_true', help='show Canny edges too')
    ap.add_argument('--debayer', action='store_true',
                    help='treat frames as Bayer (real colour AI-deck, raw mode)')
    ap.add_argument('--headless', action='store_true', help='no window (e.g. over SSH)')
    args = ap.parse_args()

    cflib.crtp.init_drivers()
    cf = Crazyflie(rw_cache='./cache')
    cf.open_link(args.uri)
    if not cf.link or not hasattr(cf.link, 'cpx'):
        raise SystemExit(f'{args.uri} is not a CPX/WiFi link. '
                         'Is sitl_camera.sh (or the AI-deck) running?')

    grabber = FrameGrabber(cf.link.cpx)
    grabber.start()
    if args.save:
        os.makedirs(args.save, exist_ok=True)

    print('Streaming - press q in the window (or Ctrl+C) to quit')
    last_count, t0, saved = 0, time.time(), 0
    try:
        while True:
            with grabber.lock:
                img, count = grabber.frame, grabber.count
            if img is None or count == last_count:
                time.sleep(0.005)
                continue
            last_count = count

            if args.debayer and img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_BayerBG2BGR)

            if args.save:
                cv2.imwrite(os.path.join(args.save, f'img_{saved:06d}.png'), img)
                saved += 1

            if time.time() - t0 >= 2.0:
                print(f'  {count / (time.time() - t0):5.1f} fps  shape={img.shape}')
                with grabber.lock:
                    grabber.count = 0
                last_count, t0 = 0, time.time()

            if not args.headless:
                cv2.imshow('AI-deck', cv2.resize(img, None, fx=2, fy=2,
                                                 interpolation=cv2.INTER_NEAREST))
                if args.edges:
                    cv2.imshow('edges', cv2.Canny(img, 60, 160))
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cf.close_link()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
