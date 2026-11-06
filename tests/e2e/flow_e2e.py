"""End-to-end: the Climb tab in a headless Chromium, with a fake camera that plays synthetic wall footage,
against the real `serve` server (plain HTTP on localhost, which browsers treat as secure for the camera).

Needs Node with Playwright and its Chromium (npm i playwright && npx playwright install chromium). It is
not part of tests/rehearsal.py because of that. Run from anywhere:  python tests/e2e/flow_e2e.py
Phase 1: open the link, New wall, Capture, the laptop finds wall and holds, Looks good -> wall saved.
Phase 2: existing wall, route by skill, Another one, Use this route, Start, a sticker climbs the route in
the footage -> good x4, top -> Done says 'sent'. Screenshots land next to this file."""
import json, os, subprocess, sys, tempfile, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests")); sys.path.insert(0, ROOT)
import cv2, numpy as np
import ascent, rehearsal

HERE = os.path.dirname(os.path.abspath(__file__))
work = tempfile.mkdtemp(prefix="flow_e2e_")
os.chdir(work)
photo, holds, corners = rehearsal.make_wall_photo()
Hs = rehearsal.camera_path(40)


def mjpeg(path, frames):
    with open(path, "wb") as f:
        for fr in frames:
            f.write(cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes())


def wall_frames(n=30):
    return [cv2.warpPerspective(photo, Hs[i % 40], (1280, 720), borderValue=(30, 30, 30)) for i in range(n)]


mjpeg("wall.mjpeg", wall_frames())

httpd = ascent.make_server("127.0.0.1", 8787, "e2ecode")
threading.Thread(target=httpd.serve_forever, daemon=True).start()
url = "http://127.0.0.1:8787/?code=e2ecode"


def run_node(script, *args):
    r = subprocess.run(["node", os.path.join(HERE, script), *args], capture_output=True, text=True, timeout=240)
    print(r.stdout)
    if r.returncode:
        print(r.stderr[-3000:])
    return r.returncode == 0


ok1 = run_node("phase1.js", url, os.path.abspath("wall.mjpeg"), os.path.join(HERE, "phase1.png"))
wall = json.load(open("walls/wall/wall.json"))
print("saved wall:", wall["version"], len(wall["holds"]), "holds", wall["size_cm"], wall["mode"])

# the route the phone will get (seeded by the test), and footage of a sticker climbing it
prev = ascent.phone_make_route({"wall": "wall", "skill": "reach", "seed": 3})
px = {h["id"]: h["px"] for h in wall["holds"]}
ref = cv2.imread("walls/wall/ref.jpg")                  # the hold positions belong to the saved photo
mild = [np.array([[1 - 0.04 * np.sin(i / 6), 0.01 * np.cos(i / 9), 10 * np.sin(i / 5)],
                  [-0.01 * np.cos(i / 7), 1 - 0.04 * np.sin(i / 6), 8 * np.cos(i / 4)], [0, 0, 1.0]]) for i in range(40)]
frames = []
for k, hid in enumerate(prev["holds"]):
    for i in range(40):                                  # ~1.3 s per hold at 30 fps
        H = mild[(k * 7 + i // 5) % 40]
        fr = cv2.warpPerspective(ref, H, (ref.shape[1], ref.shape[0]), borderValue=(30, 30, 30))
        x, y = ascent.transform(H, [px[hid]])[0]
        cv2.circle(fr, (int(x) + 3, int(y) - 4), 8, (60, 230, 60), -1, cv2.LINE_AA)
        frames.append(fr)
frames += [cv2.warpPerspective(ref, mild[i % 40], (ref.shape[1], ref.shape[0]), borderValue=(30, 30, 30)) for i in range(60)]
mjpeg("climb.mjpeg", frames)
ok2 = run_node("phase2.js", url, os.path.abspath("climb.mjpeg"), os.path.join(HERE, "phase2.png"), str(len(prev["holds"])))
print("routes on the wall:", ascent.route_names("wall"))
httpd.shutdown()
print("E2E", "OK" if ok1 and ok2 else "FAILED")
sys.exit(0 if ok1 and ok2 else 1)
