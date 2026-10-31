#!/usr/bin/env python3
"""synth_board.py OUTDIR: chessboard views through a known lens, the stand-in for holding a real board.

Renders a 7x10-square board (6x9 inner corners) in poses that cover the frame corners, edges and
middle, with a pinhole camera K, pushes them through the lens model D, and writes 1280x720
OUTDIR/view_NN.png plus OUTDIR/truth.txt. dewarp_table.py should recover K and D from them.
"""
import logging
import os
import sys

import cv2
import numpy as np

log = logging.getLogger("synth_board")
W, H = 1280, 720
K = np.array([[900.0, 0, 640.0], [0, 900.0, 360.0], [0, 0, 1]])
D = np.array([-0.30, 0.10, 0.0, 0.0, 0.0])
SQ = 60  # texture pixels per square
COLS, ROWS = 7, 10  # squares


def board_texture():
    tex = np.full(((ROWS + 2) * SQ, (COLS + 2) * SQ), 255, np.uint8)  # one square of white margin
    for r in range(ROWS):
        for c in range(COLS):
            if (r + c) % 2 == 0:
                tex[(r + 1) * SQ:(r + 2) * SQ, (c + 1) * SQ:(c + 2) * SQ] = 0
    return tex


def lens_map():
    """For each pixel of the lens image, where it lies in the ideal pinhole image."""
    pts = np.stack(np.meshgrid(np.arange(W), np.arange(H)), -1).reshape(-1, 1, 2).astype(np.float32)
    ideal = cv2.undistortPointsIter(pts, K, D, None, K, (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-6))
    ideal = ideal.reshape(H, W, 2)
    return ideal[..., 0].copy(), ideal[..., 1].copy()


def views():
    tex = board_texture()
    th, tw = tex.shape
    mx, my = lens_map()
    rng = np.random.default_rng(1884)
    # Board centre targets in pixels: a 3x3 grid, then the four corners and four edge midpoints
    targets = [(x, y) for y in (150, 360, 570) for x in (220, 640, 1060)] + \
              [(160, 110), (1120, 110), (160, 610), (1120, 610), (640, 120), (640, 600), (140, 360), (1140, 360)]
    square = 0.06  # metres
    corners_m = np.array([[-tw / 2, -th / 2, 0], [tw / 2, -th / 2, 0], [tw / 2, th / 2, 0], [-tw / 2, th / 2, 0]]) / SQ * square
    for tx, ty in targets:
        # Pull the board toward the centre until all of it lands inside the lens image:
        # findChessboardCornersSB needs every inner corner
        for k in range(40):
            f = 1.0 - 0.025 * k
            z = rng.uniform(1.6, 2.2)
            rvec = np.array([rng.uniform(-0.45, 0.45), rng.uniform(-0.45, 0.45), rng.uniform(-0.3, 0.3)])
            centre = np.linalg.inv(K) @ np.array([640 + (tx - 640) * f, 360 + (ty - 360) * f, 1.0]) * z
            cam = (cv2.Rodrigues(rvec)[0] @ corners_m.T).T + centre
            img = (K @ cam.T).T
            img = (img[:, :2] / img[:, 2:]).astype(np.float32)
            lens = cv2.projectPoints(cam.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K, D)[0].reshape(-1, 2)
            if np.all((lens[:, 0] > 8) & (lens[:, 0] < W - 8) & (lens[:, 1] > 8) & (lens[:, 1] < H - 8)):
                break
        h = cv2.getPerspectiveTransform(np.float32([[0, 0], [tw, 0], [tw, th], [0, th]]), img)
        ideal = cv2.warpPerspective(tex, h, (W, H), borderValue=170)
        view = cv2.GaussianBlur(cv2.remap(ideal, mx, my, cv2.INTER_LINEAR, borderValue=170), (3, 3), 0)
        yield cv2.cvtColor(view, cv2.COLOR_GRAY2BGR)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    n = 0
    for n, view in enumerate(views(), 1):
        cv2.imwrite(os.path.join(out, f"view_{n:02d}.png"), view)
    with open(os.path.join(out, "truth.txt"), "w") as f:
        f.write(f"K {K.ravel().tolist()}\nD {D.tolist()}\nviews {n}\n")
    log.info("%d views in %s", n, out)


if __name__ == "__main__":
    main()
