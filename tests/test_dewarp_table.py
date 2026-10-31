"""python3 -m unittest discover tests  (from the repo root)"""
import os
import subprocess
import sys
import tempfile
import unittest
import zlib

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import dewarp_table as dt  # noqa: E402

SIZE = (1280, 720)
K = np.array([[900.0, 0, 640], [0, 900.0, 360], [0, 0, 1]])
D = np.array([-0.30, 0.10, 0.0, 0.0, 0.0])
BOARD = (6, 9)


def board_texture(sq=60, margin=60):
    cols, rows = BOARD[0] + 1, BOARD[1] + 1
    img = np.full((rows * sq + 2 * margin, cols * sq + 2 * margin), 255, np.uint8)
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                img[margin + r * sq:margin + (r + 1) * sq, margin + c * sq:margin + (c + 1) * sq] = 0
    return img, sq, margin


def distorted_views(n):
    """Board seen by a pinhole camera K, then pushed through the lens model D."""
    tex, sq, margin = board_texture()
    th, tw = tex.shape
    # Distorted pixel -> ideal pixel, so the ideal render can be resampled into the lens image
    w, h = SIZE
    pts = np.stack(np.meshgrid(np.arange(w), np.arange(h)), -1).reshape(-1, 1, 2).astype(np.float32)
    ideal = cv2.undistortPointsIter(pts, K, D, None, K, (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-6))
    mapx, mapy = [m.reshape(h, w).astype(np.float32) for m in (ideal[:, 0, 0], ideal[:, 0, 1])]
    rng = np.random.default_rng(1)
    views = []
    while len(views) < n:
        rvec = rng.uniform(-0.5, 0.5, 3)
        tvec = np.array([rng.uniform(-3.5, 1.0), rng.uniform(-2.5, 0.5), rng.uniform(9, 13)])
        # Texture pixel -> board units (one square = 1), board centred on its corner grid
        corners_tex = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]])
        corners_obj = np.float32([[(x - margin) / sq - 1, (y - margin) / sq - 1, 0] for x, y in corners_tex])
        img_pts, _ = cv2.projectPoints(corners_obj, rvec, tvec, K, None)
        H = cv2.getPerspectiveTransform(corners_tex, img_pts.reshape(4, 2).astype(np.float32))
        render = cv2.warpPerspective(tex, H, SIZE, borderValue=128)
        lens = cv2.remap(render, mapx, mapy, cv2.INTER_LINEAR, borderValue=128)
        if cv2.findChessboardCornersSB(lens, BOARD)[0]:
            views.append(cv2.cvtColor(lens, cv2.COLOR_GRAY2BGR))
    return views


class Pack(unittest.TestCase):
    def test_round_clamp_layout(self):
        mapx = np.array([[-3.2, 1.6, 0.5, 4.6]], np.float32).repeat(2, 0)
        mapy = np.array([[0.0, 0.5, 1.4, 9.0]], np.float32).repeat(2, 0)
        t = dt.pack(mapx, mapy)
        self.assertEqual(t.dtype.str, "<u4")
        t = t.reshape(2, 4)
        self.assertEqual(list(t[0] & 0xFFFF), [0, 2, 0, 3])  # x: clamp low, round, round half even, clamp high
        self.assertEqual(list(t[0] >> 16), [0, 0, 1, 1])     # y in the high half, clamped to h - 1

    def test_identity_maps_to_firmware_identity(self):
        w, h = 8, 4
        t = dt.make_table(np.array([[5.0, 0, 3.5], [0, 5.0, 1.5], [0, 0, 1]]), np.zeros(5), (w, h))
        expect = [(i << 16) | j for i in range(h) for j in range(w)]  # fill_identity_table()
        self.assertEqual(list(t), expect)


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = os.path.join(cls.tmp.name, "frames")
        os.mkdir(cls.src)
        for i, v in enumerate(distorted_views(14)):
            cv2.imwrite(os.path.join(cls.src, f"{i:03d}.png"), v)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "dewarp_table.py"), "--step", "1", *args],
                           capture_output=True, text=True, cwd=self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_calibrate_then_check(self):
        out = self.run_tool("calibrate", self.src)
        (version,) = os.listdir(os.path.join(self.tmp.name, "tables"))
        table = os.path.join("tables", version, "dewarp_int.bin")
        with open(os.path.join(self.tmp.name, table), "rb") as f:
            data = f.read()
        crc = f"{zlib.crc32(data):08x}"
        self.assertEqual(len(data), SIZE[0] * SIZE[1] * 4)
        self.assertIn(f"crc32 {crc}", out)
        self.assertTrue(version.endswith("-" + crc))
        fs = cv2.FileStorage(os.path.join(self.tmp.name, "tables", version, "camera_param.yml"),
                             cv2.FILE_STORAGE_READ)
        self.assertEqual(fs.getNode("crc32").string(), crc)
        fs.release()

        got = np.frombuffer(data, "<u4")
        want = dt.make_table(K, D, SIZE)
        dx = np.abs((got & 0xFFFF).astype(int) - (want & 0xFFFF).astype(int))
        dy = np.abs((got >> 16).astype(int) - (want >> 16).astype(int))
        err = np.hypot(dx, dy)
        self.assertLess(err.mean(), 1.0)
        self.assertLess(np.percentile(err, 95), 2.0)

        before = float(self.run_tool("check", self.src).split()[4])
        after = float(self.run_tool("check", self.src, "--table", table).split()[4])
        self.assertGreater(before, 2.0)
        self.assertLess(after, 1.0)

    def test_failures_write_nothing(self):
        for args, why in ((["--size", "640x480", "calibrate"], "expected 640x480"),
                          (["calibrate", "--min-views", "99"], "need 99"),
                          (["calibrate", "--max-rms", "0.001"], "above --max-rms")):
            with tempfile.TemporaryDirectory() as cwd:
                r = subprocess.run([sys.executable, os.path.join(ROOT, "dewarp_table.py"), "--step", "1",
                                    *args, self.src], capture_output=True, text=True, cwd=cwd)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(why, r.stderr)
                self.assertEqual(os.listdir(cwd), [])


if __name__ == "__main__":
    unittest.main()
