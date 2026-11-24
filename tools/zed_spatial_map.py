#!/usr/bin/env python3
"""
zed_spatial_map.py — scan a room or object with a ZED 2 / ZED 2i / ZED X and
save a textured mesh that scan_to_sim.py can turn into simulator assets.

Requires the ZED SDK and its Python API (pyzed) on a machine with an NVIDIA
GPU. Written against the ZED SDK 4.x / 5.x Python API.

    # live camera, stop with Ctrl+C
    python3 zed_spatial_map.py -o lab.obj
    # replay a recording made with ZED Explorer (repeatable, recommended)
    python3 zed_spatial_map.py --svo lab.svo2 -o lab.obj
    # small object on a table: finer resolution, short range
    python3 zed_spatial_map.py -o part.obj --resolution 0.01 --range 2

The mesh is written Z-up, X-forward, in metres, with the origin where the
camera was when tracking started. Start the scan with the camera at the spot
you want as the world origin (e.g. your Lighthouse/mocap origin) facing +X,
and the scan will already line up with the simulator and your real arena.
"""

import argparse
import signal
import sys
import time

try:
    import pyzed.sl as sl
except ImportError:
    sys.exit('pyzed not found - install the ZED SDK and run its get_python_api.py')

_stop = False


def _sigint(*_):
    global _stop
    _stop = True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-o', '--output', default='scan.obj', help='.obj or .ply')
    ap.add_argument('--svo', default=None, help='replay an SVO/SVO2 file instead of live')
    ap.add_argument('--resolution', type=float, default=0.03,
                    help='mapping resolution [m] (0.01 fine ... 0.08 coarse)')
    ap.add_argument('--range', type=float, default=4.0,
                    help='max depth used for mapping [m]')
    ap.add_argument('--duration', type=float, default=0,
                    help='stop after N seconds (0 = until Ctrl+C / end of SVO)')
    ap.add_argument('--no-texture', action='store_true', help='skip texture (faster)')
    ap.add_argument('--filter', choices=['low', 'medium', 'high'], default='medium')
    args = ap.parse_args()

    init = sl.InitParameters()
    init.camera_resolution = sl.RESOLUTION.HD720
    init.depth_mode = sl.DEPTH_MODE.NEURAL
    init.coordinate_units = sl.UNIT.METER
    # Same convention as MuJoCo / Gazebo / Crazyflie: Z up, X forward.
    init.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Z_UP_X_FWD
    init.depth_maximum_distance = args.range
    if args.svo:
        init.set_from_svo_file(args.svo)
        init.svo_real_time_mode = False

    zed = sl.Camera()
    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        sys.exit(f'Could not open the ZED: {err}')

    tracking = sl.PositionalTrackingParameters()
    tracking.set_floor_as_origin = False  # keep the camera start pose as origin
    err = zed.enable_positional_tracking(tracking)
    if err != sl.ERROR_CODE.SUCCESS:
        sys.exit(f'Positional tracking failed: {err}')

    mapping = sl.SpatialMappingParameters()
    mapping.map_type = sl.SPATIAL_MAP_TYPE.MESH
    mapping.resolution_meter = args.resolution
    mapping.range_meter = args.range
    mapping.save_texture = not args.no_texture
    err = zed.enable_spatial_mapping(mapping)
    if err != sl.ERROR_CODE.SUCCESS:
        sys.exit(f'Spatial mapping failed: {err}')

    print('Scanning. Move slowly, overlap your passes, and cover the floor.')
    print('Press Ctrl+C to stop and save.' if not args.svo else 'Replaying SVO...')
    signal.signal(signal.SIGINT, _sigint)

    runtime = sl.RuntimeParameters()
    pose = sl.Pose()
    t0 = time.time()
    frames = 0
    while not _stop:
        err = zed.grab(runtime)
        if err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
            break
        if err != sl.ERROR_CODE.SUCCESS:
            continue
        frames += 1
        if frames % 30 == 0:
            state = zed.get_position(pose, sl.REFERENCE_FRAME.WORLD)
            t = pose.get_translation(sl.Translation()).get()
            print(f'  {frames:5d} frames  tracking={state}  '
                  f'cam=({t[0]:+.2f}, {t[1]:+.2f}, {t[2]:+.2f})  '
                  f'mapping={zed.get_spatial_mapping_state()}')
        if args.duration and time.time() - t0 > args.duration:
            break

    print('Extracting mesh...')
    mesh = sl.Mesh()
    zed.extract_whole_spatial_map(mesh)

    fp = sl.MeshFilterParameters()
    fp.set({'low': sl.MESH_FILTER.LOW, 'medium': sl.MESH_FILTER.MEDIUM,
            'high': sl.MESH_FILTER.HIGH}[args.filter])
    mesh.filter(fp)
    if not args.no_texture:
        print('Applying texture...')
        mesh.apply_texture(sl.MESH_TEXTURE_FORMAT.RGB)

    fmt = sl.MESH_FILE_FORMAT.PLY if args.output.lower().endswith('.ply') else sl.MESH_FILE_FORMAT.OBJ
    ok = mesh.save(args.output, fmt)
    print(('Saved ' if ok else 'FAILED to save ') + args.output)

    zed.disable_spatial_mapping()
    zed.disable_positional_tracking()
    zed.close()


if __name__ == '__main__':
    main()
