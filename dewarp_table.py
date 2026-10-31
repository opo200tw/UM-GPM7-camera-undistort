#!/usr/bin/env python3
"""Chessboard footage in, General Plus IPU dewarp table (dewarp_int.bin) out, no GUI.

calibrate: find the board in a video, a stream URL or an image directory, calibrate the
           lens, write camera_param.yml and the table, print the table's CRC32.
check:     report how far the board's rows and columns bend; with --table, after
           remapping each frame the way the firmware does (nearest neighbour).
"""
import argparse
import glob
import logging
import os
import sys
import zlib

import cv2
import numpy as np

log = logging.getLogger("dewarp_table")


def wxh(text):
    w, h = text.lower().split("x")
    return int(w), int(h)


def frames(src):
    if os.path.isdir(src):
        for path in sorted(glob.glob(os.path.join(src, "*"))):
            img = cv2.imread(path)
            if img is not None:
                yield img
        return
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {src}")
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                return
            yield img
    finally:
        cap.release()


def find_boards(src, board, size, step, limit=None, remap=None):
    """Corner sets from every step-th frame; stops at limit sets, end of input or Ctrl-C."""
    found = []
    try:
        for i, img in enumerate(frames(src)):
            if i % step:
                continue
            if (img.shape[1], img.shape[0]) != size:
                raise SystemExit(f"frame is {img.shape[1]}x{img.shape[0]}, expected "
                                 f"{size[0]}x{size[1]} (the firmware stream size, see --size)")
            if remap is not None:
                img = cv2.remap(img, remap[0], remap[1], cv2.INTER_NEAREST)
            ok, corners = cv2.findChessboardCornersSB(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), board)
            if ok:
                found.append(corners.reshape(-1, 2))
                log.info("frame %d: board found (%d)", i, len(found))
                if limit and len(found) >= limit:
                    break
    except KeyboardInterrupt:
        log.info("stopped by Ctrl-C")
    return found


def pack(mapx, mapy):
    """Source pixel per output pixel as the firmware reads it: row in bits 31..16, column in
    15..0, rounded to the nearest pixel and clamped into the frame, little endian."""
    h, w = mapx.shape
    x = np.clip(np.rint(mapx), 0, w - 1).astype(np.uint32)
    y = np.clip(np.rint(mapy), 0, h - 1).astype(np.uint32)
    return ((y << 16) | x).astype("<u4").ravel()


def unpack(table, size):
    w, h = size
    t = table.reshape(h, w)
    return (t & 0xFFFF).astype(np.float32), (t >> 16).astype(np.float32)


def make_table(K, D, size):
    # New camera matrix = K: same field of view as the earlier undistort_table output
    mapx, mapy = cv2.initUndistortRectifyMap(K, D, None, K, size, cv2.CV_32FC1)
    return pack(mapx, mapy)


def read_table(path, size):
    table = np.fromfile(path, dtype="<u4")
    if table.size != size[0] * size[1]:
        raise SystemExit(f"{path} holds {table.size} entries, expected {size[0] * size[1]}")
    return table


def bend(corners, board):
    """Largest distance of a corner from the straight line through its row or column."""
    grid = corners.reshape(board[1], board[0], 2)
    worst = 0.0
    for line in list(grid) + list(grid.transpose(1, 0, 2)):
        centred = line - line.mean(axis=0)
        normal = np.linalg.svd(centred)[2][1]
        worst = max(worst, float(np.abs(centred @ normal).max()))
    return worst


def calibrate(args):
    found = find_boards(args.src, args.board, args.size, args.step, args.max_views)
    if len(found) < args.min_views:
        raise SystemExit(f"board found in {len(found)} frames, need {args.min_views}")
    obj = np.zeros((args.board[0] * args.board[1], 3), np.float32)
    obj[:, :2] = np.mgrid[0:args.board[0], 0:args.board[1]].T.reshape(-1, 2)
    rms, K, D, _, _ = cv2.calibrateCamera([obj] * len(found), found, args.size, None, None)
    log.info("views %d, rms %.3f px\nK\n%s\nD %s", len(found), rms, K, D.ravel())
    if rms > args.max_rms:
        raise SystemExit(f"rms {rms:.3f} px is above --max-rms {args.max_rms}")

    table = make_table(K, D, args.size)
    w, h = args.size
    mapx, mapy = unpack(table, args.size)
    shift = np.hypot(mapx - np.arange(w), mapy - np.arange(h)[:, None]).max()
    if shift < 1:
        log.warning("table moves no pixel: was the footage already dewarped? "
                    "Record with no dewarp_int.bin on the card")

    fs = cv2.FileStorage(args.params, cv2.FILE_STORAGE_WRITE)
    fs.write("cameraMatrix", K)
    fs.write("dist_coeffs", D)
    fs.write("image_width", w)
    fs.write("image_height", h)
    fs.write("rms", rms)
    fs.write("views", len(found))
    fs.release()
    data = table.tobytes()
    with open(args.out, "wb") as f:
        f.write(data)
    if os.path.getsize(args.out) != w * h * 4:
        raise SystemExit(f"{args.out} is not {w * h * 4} bytes")
    print(f"{args.out}: {len(data)} bytes, crc32 {zlib.crc32(data):08x}, max shift {shift:.1f} px")


def check(args):
    remap = unpack(read_table(args.table, args.size), args.size) if args.table else None
    found = find_boards(args.src, args.board, args.size, args.step, args.max_views, remap)
    if not found:
        raise SystemExit("board not found in any frame")
    worst = sorted(bend(c, args.board) for c in found)
    print(f"views {len(worst)}, bend median {worst[len(worst) // 2]:.2f} px, max {worst[-1]:.2f} px")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--board", type=wxh, default=(6, 9), help="inner corners WxH (default 6x9)")
    p.add_argument("--size", type=wxh, default=(1280, 720), help="stream size WxH (default 1280x720)")
    p.add_argument("--step", type=int, default=10, help="use every Nth frame (default 10)")
    p.add_argument("--max-views", type=int, default=40, help="stop after this many boards (default 40)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate")
    c.add_argument("src", help="video file, rtsp:// URL or image directory")
    c.add_argument("-o", "--out", default="dewarp_int.bin")
    c.add_argument("--params", default="camera_param.yml")
    c.add_argument("--min-views", type=int, default=10)
    c.add_argument("--max-rms", type=float, default=1.0)
    k = sub.add_parser("check")
    k.add_argument("src", help="video file, rtsp:// URL or image directory")
    k.add_argument("--table", help="remap frames by this table first")
    args = p.parse_args()
    calibrate(args) if args.cmd == "calibrate" else check(args)


if __name__ == "__main__":
    main()
