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
import synth_board as sb  # noqa: E402

SIZE = (sb.W, sb.H)


def run_tool(cwd, *args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "dewarp_table.py"), *args],
                          capture_output=True, text=True, cwd=cwd)


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


class SyntheticBoard(unittest.TestCase):
    """The whole host-side flow on synth_board.py views: the stand-in for a person holding a board."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = os.path.join(cls.tmp.name, "frames")
        os.mkdir(cls.src)
        for i, v in enumerate(sb.views()):
            cv2.imwrite(os.path.join(cls.src, f"view_{i:02d}.png"), v)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_ok(self, *args):
        r = run_tool(self.tmp.name, *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_calibrate_then_check(self):
        # No --step: an image directory must default to every image
        r = self.run_ok("calibrate", self.src)
        self.assertNotIn("frame corner", r.stderr)
        self.assertNotIn("under 5 px", r.stderr)
        (version,) = os.listdir(os.path.join(self.tmp.name, "tables"))
        table = os.path.join("tables", version, "dewarp_int.bin")
        with open(os.path.join(self.tmp.name, table), "rb") as f:
            data = f.read()
        crc = f"{zlib.crc32(data):08x}"
        self.assertEqual(len(data), SIZE[0] * SIZE[1] * 4)
        self.assertIn(f"crc32 {crc}", r.stdout)
        self.assertTrue(version.endswith("-" + crc))

        fs = cv2.FileStorage(os.path.join(self.tmp.name, "tables", version, "camera_param.yml"),
                             cv2.FILE_STORAGE_READ)
        self.assertEqual(fs.getNode("crc32").string(), crc)
        self.assertEqual(int(fs.getNode("views").real()), len(os.listdir(self.src)))
        self.assertLess(fs.getNode("rms").real(), 0.3)
        self.assertAlmostEqual(fs.getNode("dist_coeffs").mat().ravel()[0], sb.D[0], delta=0.02)
        fs.release()

        got = np.frombuffer(data, "<u4")
        want = dt.make_table(sb.K, sb.D, SIZE)
        err = np.hypot((got & 0xFFFF).astype(int) - (want & 0xFFFF).astype(int),
                       (got >> 16).astype(int) - (want >> 16).astype(int))
        self.assertLess(err.mean(), 1.0)
        self.assertLess(np.percentile(err, 95), 2.0)

        # "views N, bend median M px, max X px": compare the largest bend
        before = float(self.run_ok("check", self.src).stdout.split()[7])
        predicted = float(self.run_ok("check", self.src, "--table", table).stdout.split()[7])
        self.assertGreater(before, 1.0)
        self.assertLess(predicted, 0.6)

    def test_max_views_caps_a_file(self):
        with tempfile.TemporaryDirectory() as cwd:
            r = run_tool(cwd, "calibrate", "--max-views", "12", self.src)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("views 12,", r.stderr)

    def test_failures_write_nothing(self):
        for args, why in ((["calibrate", "--size", "640x480"], "expected 640x480"),
                          (["calibrate", "--min-views", "99"], "need 99"),
                          (["calibrate", "--max-rms", "0.001"], "above --max-rms")):
            with tempfile.TemporaryDirectory() as cwd:
                r = run_tool(cwd, *args, self.src)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(why, r.stderr)
                self.assertEqual(os.listdir(cwd), [])


if __name__ == "__main__":
    unittest.main()
