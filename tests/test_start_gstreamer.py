"""python3 -m unittest tests.test_start_gstreamer  (from the repo root)"""
import os
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "start_gstreamer.sh")
PASSWORD = "FakePw-9Q7z"

# Stand-in for gst-launch-1.0: records its arguments one per line and prints the rtspsrc
# location to stdout and stderr, as the real one prints "Progress: (connect) Connecting to <URL>"
STUB = """#!/bin/bash
for a in "$@"; do
    printf '%s\\n' "$a" >> "$ARGS_LOG"
    case "$a" in location=rtsp*)
        echo "Progress: (connect) Connecting to ${a#location=}"
        echo "stub stderr: ${a#location=}" >&2;;
    esac
done
exit "${STUB_RC:-0}"
"""


class StartGstreamer(unittest.TestCase):
    def run_script(self, url, rc="0"):
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "gst-launch-1.0")
            with open(stub, "w") as f:
                f.write(STUB)
            os.chmod(stub, stat.S_IRWXU)
            log = os.path.join(tmp, "args")
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"],
                       ARGS_LOG=log, STUB_RC=rc)
            p = subprocess.run(["/bin/bash", SCRIPT, url, os.path.join(tmp, "out.mkv")],
                               env=env, capture_output=True, text=True, timeout=30)
            with open(log) as f:
                args = f.read().splitlines()
        return p, args

    def test_password_not_printed(self):
        for rc in ("0", "1"):  # 1: the fallback pipeline and its messages run too
            p, args = self.run_script(f"rtsp://admin:{PASSWORD}@192.168.0.31:8080", rc)
            self.assertNotIn(PASSWORD, p.stdout + p.stderr)
            self.assertIn("user-id=admin", args)
            self.assertIn(f"user-pw={PASSWORD}", args)
            self.assertIn("location=rtsp://192.168.0.31:8080", args)

    def test_no_scheme_no_port(self):
        # a password starting with digits must not pass for the port
        pw = "4242" + PASSWORD
        p, args = self.run_script(f"admin:{pw}@192.168.0.31")
        self.assertNotIn(PASSWORD, p.stdout + p.stderr)
        self.assertIn("location=rtsp://192.168.0.31:8080", args)
        self.assertIn(f"user-pw={pw}", args)

    def test_no_login(self):
        p, args = self.run_script("192.168.0.31")
        self.assertIn("location=rtsp://192.168.0.31:8080", args)
        self.assertFalse([a for a in args if a.startswith("user-")])


if __name__ == "__main__":
    unittest.main()
