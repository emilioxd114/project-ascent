"""
Project Ascent - laptop prototype for ArtRock (Tirol Hackathon 2026)

One file. Needs:  pip install opencv-contrib-python numpy

Commands
  python ascent.py selftest                         check the install, no camera needed
  python ascent.py scan --wall panel                photograph a wall, tap corners, tap holds
  python ascent.py scan --wall panel --image p.jpg  same, from a photo file
  python ascent.py scan --wall panel --markers      use the printed markers instead of tapping corners
  python ascent.py generate --wall panel --train reach --moves 6 --height 172 --preview
  python ascent.py build --wall panel               tap holds in order to make your own route
  python ascent.py live --wall panel --route r1     route drawn on the live camera
  python ascent.py preview --wall panel --route r1  route drawn on the saved photo (demo backup)
  python ascent.py list                             show saved walls and routes

Keys in the windows
  scan corners : click 4 corners (top-left, top-right, bottom-right, bottom-left), u = undo, Enter = done
  scan holds   : click each hold, then j/c/s/p/k to tag it jug/crimp/sloper/pinch/pocket, u = undo, Enter = done
  build        : click holds in climbing order, u = undo, Enter = done
  live         : q = quit, s = screenshot, v = start/stop recording a video
"""

import argparse
import json
import math
import os
import random
import shutil
import sys
import time

import cv2
import numpy as np

DATA_DIR = "walls"
HOLD_TYPES = {"j": "jug", "c": "crimp", "s": "sloper", "p": "pinch", "k": "pocket"}

# BGR colours: start green, middle blue, finish red, warning amber
GREEN = (128, 222, 74)
BLUE = (244, 169, 106)
RED = (111, 115, 243)
AMBER = (61, 177, 245)
WHITE = (240, 243, 244)
DARK = (16, 14, 12)
GREY = (166, 160, 154)

REACH_FACTOR = 0.55          # comfortable reach between consecutive hand holds = 0.55 x height
LEVEL_TARGET = {"easy": 0.30, "medium": 0.40, "hard": 0.50}
GRADES = ["4", "5a", "5b", "5c", "6a", "6b", "6c", "7a"]


# ---------------------------------------------------------------- display helpers

def fit(img, max_w=1280, max_h=760):
    h, w = img.shape[:2]
    s = min(max_w / w, max_h / h, 1.0)
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img, s


def put_text(img, text, org, scale=0.7, color=WHITE, thick=2):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, DARK, thick + 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def banner(img, lines, color=WHITE):
    y = 34
    for line in lines:
        put_text(img, line, (16, y), 0.65, color, 2)
        y += 30


def draw_ring(img, center, radius, color, label):
    x, y = int(round(center[0])), int(round(center[1]))
    r = int(max(12, radius))
    cv2.circle(img, (x, y), r + 3, DARK, 7, cv2.LINE_AA)      # dark outer edge
    cv2.circle(img, (x, y), r, WHITE, 6, cv2.LINE_AA)         # white halo: visible on any hold colour
    cv2.circle(img, (x, y), r, color, 3, cv2.LINE_AA)         # route colour
    size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    put_text(img, label, (x - size[0] // 2, y + size[1] // 2), 0.7, WHITE, 2)


def draw_route(img, pts, radius):
    if len(pts) > 1:
        overlay = img.copy()
        for a, b in zip(pts[:-1], pts[1:]):
            cv2.line(overlay, tuple(int(v) for v in a), tuple(int(v) for v in b), WHITE, 2, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.35, img, 0.65, 0, img)
    for i, p in enumerate(pts):
        color = GREEN if i == 0 else RED if i == len(pts) - 1 else BLUE
        draw_ring(img, p, radius, color, str(i + 1))


# ---------------------------------------------------------------- storage

def wall_path(name, *parts):
    return os.path.join(DATA_DIR, name, *parts)


def load_wall(name):
    p = wall_path(name, "wall.json")
    if not os.path.exists(p):
        sys.exit(f"No wall called '{name}'. Run: python ascent.py scan --wall {name}")
    with open(p, encoding="utf-8") as f:
        wall = json.load(f)
    ref = cv2.imread(wall_path(name, "ref.jpg"))
    if ref is None:
        sys.exit(f"Reference photo missing for '{name}'. Scan it again.")
    return wall, ref


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_route(wall_name, route_name):
    p = wall_path(wall_name, "routes", f"{route_name}.json")
    if not os.path.exists(p):
        sys.exit(f"No route '{route_name}' on wall '{wall_name}'. Run: python ascent.py list")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def archive_existing(name):
    """Re-scanning a wall makes a new version. The old photo, map and routes are archived, never deleted."""
    d = wall_path(name)
    if not os.path.exists(os.path.join(d, "wall.json")):
        return 1
    with open(os.path.join(d, "wall.json"), encoding="utf-8") as f:
        old = json.load(f)
    v = old.get("version", 1)
    arch = os.path.join(d, f"archive_v{v}")
    os.makedirs(arch, exist_ok=True)
    for item in ("wall.json", "ref.jpg", "routes"):
        src = os.path.join(d, item)
        if os.path.exists(src):
            shutil.move(src, os.path.join(arch, item))
    print(f"Version {v} archived in {arch}. This scan becomes version {v + 1}.")
    return v + 1


# ---------------------------------------------------------------- geometry

def order_corners(pts):
    """Return points as top-left, top-right, bottom-right, bottom-left."""
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def rectify_matrix(corners_px, w_cm, h_cm):
    """Photo pixels -> wall centimetres. x to the right, y upwards, origin at bottom-left corner."""
    dst = np.array([[0, h_cm], [w_cm, h_cm], [w_cm, 0], [0, 0]], dtype=np.float32)
    return cv2.getPerspectiveTransform(np.array(corners_px, dtype=np.float32), dst)


def transform(H, pts):
    pts = np.array(pts, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, H).reshape(-1, 2)


def quad_area(q):
    return abs(cv2.contourArea(np.array(q, dtype=np.float32)))


# ---------------------------------------------------------------- markers

def aruco_detect(gray):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "ArucoDetector"):
        corners, ids, _ = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters()).detectMarkers(gray)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(gray, dictionary)
    found = {}
    if ids is not None:
        for c, i in zip(corners, ids.ravel()):
            found[int(i)] = c.reshape(4, 2).astype(np.float32)
    return found


# ---------------------------------------------------------------- tracking

class Tracker:
    """Finds where the saved wall photo sits in a live camera frame.

    features mode: compares hundreds of small image patches (mostly holds and wall texture)
                   between the saved photo and the frame. Nothing is stuck on the wall.
    markers mode:  finds the printed markers. Very reliable, needs the markers on the wall.
    """

    def __init__(self, wall, ref, method="sift"):
        self.mode = wall.get("mode", "features")
        self.corners = np.array(wall["corners_px"], dtype=np.float32)
        if self.mode == "markers":
            self.ref_markers = {int(k): np.array(v, dtype=np.float32) for k, v in wall["markers_px"].items()}
            return
        gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
        s = min(1.0, 1000.0 / gray.shape[1])
        self.S = np.diag([s, s, 1.0])
        small = cv2.resize(gray, (0, 0), fx=s, fy=s, interpolation=cv2.INTER_AREA)
        if method == "sift" and hasattr(cv2, "SIFT_create"):
            self.det = cv2.SIFT_create(nfeatures=4000)
            self.matcher = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 5}, {"checks": 50})
        else:
            self.det = cv2.ORB_create(nfeatures=4000)
            self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.kp_r, self.des_r = self.det.detectAndCompute(small, None)
        if self.des_r is None or len(self.kp_r) < 30:
            print("Warning: the saved photo has very little texture. Consider --markers.")

    def locate(self, frame):
        """Returns (H, state). H maps saved-photo pixels to frame pixels, or None.
        state: locked | far | close | lost"""
        fh, fw = frame.shape[:2]
        if self.mode == "markers":
            found = aruco_detect(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            src, dst = [], []
            for i, c in found.items():
                if i in self.ref_markers:
                    src.append(self.ref_markers[i])
                    dst.append(c)
            if len(src) == 0:
                return None, "lost"
            if len(src) == 1:
                return None, "close"
            H, _ = cv2.findHomography(np.vstack(src), np.vstack(dst), cv2.RANSAC, 4.0)
            return self._judge(H, fw, fh, True)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        f = min(1.0, 960.0 / fw)
        F = np.diag([f, f, 1.0])
        small = cv2.resize(gray, (0, 0), fx=f, fy=f, interpolation=cv2.INTER_AREA)
        kp_f, des_f = self.det.detectAndCompute(small, None)
        if des_f is None or self.des_r is None or len(kp_f) < 10:
            return None, "lost"
        pairs = self.matcher.knnMatch(self.des_r, des_f, k=2)
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
        if len(good) < 12:
            return None, "lost"
        src = np.float32([self.kp_r[m.queryIdx].pt for m in good])
        dst = np.float32([kp_f[m.trainIdx].pt for m in good])
        Hs, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if Hs is None:
            return None, "lost"
        inliers = int(mask.sum())
        H = np.linalg.inv(F) @ Hs @ self.S
        return self._judge(H, fw, fh, inliers >= 20)

    def _judge(self, H, fw, fh, enough):
        if H is None:
            return None, "lost"
        quad = transform(H, self.corners)
        if not np.all(np.isfinite(quad)) or not cv2.isContourConvex(quad.reshape(-1, 1, 2).astype(np.float32)):
            return None, "lost"
        frame_area = float(fw * fh)
        area = quad_area(quad)
        if area < 0.01 * frame_area or area > 25 * frame_area:
            return None, "lost"
        frame_rect = np.array([[0, 0], [fw, 0], [fw, fh], [0, fh]], dtype=np.float32)
        inter, _ = cv2.intersectConvexConvex(quad.astype(np.float32), frame_rect)
        inside = inter / area if area > 0 else 0
        if not enough:
            if area < 0.10 * frame_area:
                return None, "far"
            if inside < 0.6:
                return None, "close"
            return None, "lost"
        return H, "locked"


# ---------------------------------------------------------------- route generation (rules, no AI)

def hold_cm(wall):
    return {h["id"]: np.array(h["cm"], dtype=float) for h in wall["holds"]}


def generate_route(wall, moves=6, height=172.0, train=(), level="medium", seed=None, attempts=600):
    holds = wall["holds"]
    pos = hold_cm(wall)
    W, Hh = wall["size_cm"]["w"], wall["size_cm"]["h"]
    reach = REACH_FACTOR * height
    target = LEVEL_TARGET[level] * height
    traverse = "traverse" in train
    types = [t for t in train if t in HOLD_TYPES.values()]
    rng = random.Random(seed)

    if traverse:
        left = [h for h in holds if pos[h["id"]][0] <= 0.3 * W]
        right = [h for h in holds if pos[h["id"]][0] >= 0.7 * W]
        starts = left + right
    else:
        starts = [h for h in holds if pos[h["id"]][1] <= 0.35 * Hh]
    if not starts:
        return None

    best, best_score = None, -1.0
    for attempt in range(attempts):
        start = rng.choice(starts)
        direction = 1 if pos[start["id"]][0] < W / 2 else -1
        path, score = [start["id"]], 0.0
        for _ in range(moves - 1):
            cur = pos[path[-1]]
            cands = []
            for h in holds:
                if h["id"] in path:
                    continue
                p = pos[h["id"]]
                d = float(np.linalg.norm(p - cur))
                if d < 15 or d > reach:
                    continue
                dx, dy = p - cur
                if traverse:
                    if dx * direction < 5 or abs(dy) > 0.35 * height:
                        continue
                elif dy < 5:
                    continue
                w = math.exp(-((d - target) / (0.15 * height)) ** 2)
                if "reach" in train:
                    w *= 1 + 2 * d / reach
                if types and h.get("type") in types:
                    w *= 3
                cands.append((h["id"], w))
            if not cands:
                break
            total = sum(w for _, w in cands)
            r, acc = rng.random() * total, 0.0
            for hid, w in cands:
                acc += w
                if acc >= r:
                    path.append(hid)
                    score += w
                    break
        if len(path) < moves:
            continue
        end = pos[path[-1]]
        finished = (abs(end[0] - pos[path[0]][0]) >= 0.4 * W) if traverse else (end[1] >= 0.70 * Hh)
        if not finished and attempt < attempts * 0.7:
            continue
        score += 3 if finished else 0
        if score > best_score:
            best, best_score = path, score
    return best


def route_warnings(wall, ids, height):
    pos = hold_cm(wall)
    reach = REACH_FACTOR * height
    out = []
    if wall["size_cm"].get("assumed"):
        out.append("Wall size was not measured, so reach checks are approximate.")
    for i, (a, b) in enumerate(zip(ids[:-1], ids[1:]), start=1):
        d = float(np.linalg.norm(pos[b] - pos[a]))
        if d > reach:
            out.append(f"Move {i} -> {i + 1} is {d - reach:.0f} cm past your reach")
    return out


def estimate_grade(wall, ids, height):
    pos = hold_cm(wall)
    types = {h["id"]: h.get("type") for h in wall["holds"]}
    if len(ids) < 2:
        return "?"
    ratio = np.mean([np.linalg.norm(pos[b] - pos[a]) for a, b in zip(ids[:-1], ids[1:])]) / height
    for hid in ids:
        if types.get(hid) in ("sloper", "crimp", "pocket"):
            ratio += 0.02
        elif types.get(hid) == "jug":
            ratio -= 0.02
    i = int(np.clip((ratio - 0.22) / 0.05, 0, len(GRADES) - 1))
    return "~" + GRADES[i]


# ---------------------------------------------------------------- commands

def cmd_selftest(args):
    """Builds a fake wall, photographs it from a different angle, and checks the overlay lands on the holds."""
    rng = np.random.default_rng(7)
    ref = np.full((900, 1200, 3), 70, np.uint8)
    noise = rng.integers(0, 40, (900, 1200, 1), dtype=np.uint8)
    ref = cv2.add(ref, np.repeat(noise, 3, axis=2))
    ref = cv2.GaussianBlur(ref, (3, 3), 0)
    palette = [(20, 20, 20), (40, 210, 240), (200, 120, 40), (60, 60, 220), (30, 140, 250)]
    holds = []
    for i in range(45):
        x, y = int(rng.integers(120, 1080)), int(rng.integers(100, 800))
        c = palette[i % len(palette)]
        axes = (int(rng.integers(14, 30)), int(rng.integers(10, 22)))
        cv2.ellipse(ref, (x, y), axes, float(rng.integers(0, 180)), 0, 360, c, -1, cv2.LINE_AA)
        cv2.ellipse(ref, (x, y), axes, 0, 0, 360, (10, 10, 10), 2, cv2.LINE_AA)
        cv2.circle(ref, (x + 3, y - 2), 3, (230, 230, 230), -1)
        holds.append((x, y))
    true_H = np.array([[0.82, 0.10, 90], [-0.06, 0.88, 40], [0.00012, 0.00005, 1.0]])
    live = cv2.warpPerspective(ref, true_H, (1280, 720))
    live = cv2.convertScaleAbs(live, alpha=1.15, beta=-12)
    live = cv2.add(live, rng.integers(0, 12, live.shape, dtype=np.uint8))

    wall = {"mode": "features", "corners_px": [[100, 80], [1100, 80], [1100, 820], [100, 820]]}
    tracker = Tracker(wall, ref)
    tracker.locate(live)
    t0 = time.time()
    H, state = tracker.locate(live)
    ms = (time.time() - t0) * 1000
    if H is None:
        print(f"FAIL: could not lock (state={state}).")
        return 1
    err = np.linalg.norm(transform(H, holds) - transform(true_H, holds), axis=1)
    print(f"Features: {state}, mean error {err.mean():.1f} px, worst {err.max():.1f} px, {ms:.0f} ms per frame")

    marker_ref = ref.copy()
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    spots = [(30, 30), (1050, 30), (1050, 750), (30, 750)]
    for i, (x, y) in enumerate(spots):
        m = cv2.aruco.generateImageMarker(d, i, 120)
        tile = np.full((160, 160), 255, np.uint8)
        tile[20:140, 20:140] = m
        marker_ref[y - 10:y + 150, x - 10:x + 150] = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
    found = aruco_detect(cv2.cvtColor(marker_ref, cv2.COLOR_BGR2GRAY))
    mwall = {"mode": "markers", "corners_px": wall["corners_px"],
             "markers_px": {str(k): v.tolist() for k, v in found.items()}}
    mlive = cv2.warpPerspective(marker_ref, true_H, (1280, 720))
    H2, state2 = Tracker(mwall, marker_ref).locate(mlive)
    if H2 is None:
        print(f"Markers: could not lock (state={state2}), found {len(found)} markers in the photo.")
    else:
        err2 = np.linalg.norm(transform(H2, holds) - transform(true_H, holds), axis=1)
        print(f"Markers:  {state2}, mean error {err2.mean():.1f} px, worst {err2.max():.1f} px")

    ok = err.mean() < 5
    print("OK - the install works." if ok else "Overlay error is high - check the OpenCV install.")
    return 0 if ok else 1


def capture_photo(cam_index):
    cap = open_camera(cam_index)
    print("Point the camera at the whole wall. SPACE = take photo, ESC = cancel.")
    photo = None
    while True:
        ok, frame = cap.read()
        if not ok:
            sys.exit("Could not read from the camera. Try --camera 1, or use --image photo.jpg")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bright = gray.mean()
        sharp = cv2.Laplacian(gray, cv2.CV_64F).var()
        view = frame.copy()
        lines = [("Fit the whole wall in the frame", WHITE)]
        lines.append(("Holding steady", GREEN) if sharp > 60 else ("Hold steady - image is blurry", AMBER))
        lines.append(("Light is fine", GREEN) if bright > 70 else ("A little dark - more light helps", AMBER))
        y = 34
        for text, col in lines:
            put_text(view, text, (16, y), 0.65, col)
            y += 30
        put_text(view, "SPACE = take photo", (16, view.shape[0] - 20), 0.65, WHITE)
        cv2.imshow("Ascent - frame the wall", view)
        k = cv2.waitKey(1) & 0xFF
        if k == 27:
            break
        if k == 32:
            photo = frame.copy()
            break
    cap.release()
    cv2.destroyAllWindows()
    if photo is None:
        sys.exit("Cancelled.")
    return photo


def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        sys.exit(f"Camera {index} not found. Try --camera 1")
    return cap


def click_corners(photo):
    view0, s = fit(photo)
    pts = []
    win = "Ascent - tap the 4 corners"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
            pts.append((x / s, y / s))

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    names = ["top-left", "top-right", "bottom-right", "bottom-left"]
    while True:
        view = view0.copy()
        for i, (x, y) in enumerate(pts):
            cv2.circle(view, (int(x * s), int(y * s)), 12, AMBER, -1, cv2.LINE_AA)
            put_text(view, str(i + 1), (int(x * s) - 6, int(y * s) + 6), 0.55, DARK, 1)
        if len(pts) >= 2:
            poly = np.array([(int(x * s), int(y * s)) for x, y in pts], np.int32)
            cv2.polylines(view, [poly], len(pts) == 4, AMBER, 2, cv2.LINE_AA)
        msg = f"Click the {names[len(pts)]} corner" if len(pts) < 4 else "Enter = done, u = undo"
        banner(view, ["Corners of the climbing area - fixed points, never a hold", msg])
        cv2.imshow(win, view)
        k = cv2.waitKey(20) & 0xFF
        if k == ord("u") and pts:
            pts.pop()
        elif k in (13, 10) and len(pts) == 4:
            break
        elif k == 27:
            sys.exit("Cancelled.")
    cv2.destroyWindow(win)
    return order_corners(pts)


def click_holds(photo, corners):
    view0, s = fit(photo)
    holds = []
    win = "Ascent - tap every hold"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            holds.append({"px": [x / s, y / s], "type": None})

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    while True:
        view = view0.copy()
        cv2.polylines(view, [np.int32(corners * s)], True, AMBER, 1, cv2.LINE_AA)
        for i, h in enumerate(holds):
            c = (int(h["px"][0] * s), int(h["px"][1] * s))
            cv2.circle(view, c, 10, WHITE if h["type"] else GREY, 2, cv2.LINE_AA)
            if h["type"]:
                put_text(view, h["type"][0].upper(), (c[0] + 12, c[1] + 6), 0.5, WHITE, 1)
        banner(view, [f"{len(holds)} holds. Click each hold.",
                      "Tag the last one: j jug  c crimp  s sloper  p pinch  k pocket",
                      "u = undo, Enter = done"])
        cv2.imshow(win, view)
        k = cv2.waitKey(20) & 0xFF
        if k == ord("u") and holds:
            holds.pop()
        elif chr(k) in HOLD_TYPES and holds:
            holds[-1]["type"] = HOLD_TYPES[chr(k)]
        elif k in (13, 10) and holds:
            break
        elif k == 27:
            sys.exit("Cancelled.")
    cv2.destroyWindow(win)
    return holds


def ask_number(prompt, default=None):
    while True:
        raw = input(prompt).strip()
        if not raw and default is not None:
            return default
        try:
            v = float(raw.replace(",", "."))
            if v > 0:
                return v
        except ValueError:
            pass
        print("Please type a number in centimetres.")


def cmd_scan(args):
    photo = cv2.imread(args.image) if args.image else capture_photo(args.camera)
    if photo is None:
        sys.exit(f"Could not open {args.image}")

    markers_px = None
    if args.markers:
        found = aruco_detect(cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY))
        if len(found) < 4:
            sys.exit(f"Found {len(found)} of 4 markers in the photo. Make sure all four are visible and flat.")
        corners = order_corners([c.mean(axis=0) for c in found.values()])
        markers_px = {str(k): v.tolist() for k, v in found.items()}
        print("Markers found. Their centres are used as the corners.")
    else:
        corners = click_corners(photo)

    print("\nScale lets the app check whether a move is within reach.")
    top = np.linalg.norm(corners[1] - corners[0])
    side = np.linalg.norm(corners[3] - corners[0])
    w_cm = ask_number("Distance between the two top corners, in cm (Enter to skip): ", default=-1)
    assumed = w_cm < 0
    if assumed:
        w_cm = 300.0
        print("Skipped. Assuming 300 cm wide - reach checks will be approximate.")
    h_default = round(w_cm * side / top)
    h_cm = ask_number(f"Distance between the two left corners, in cm (Enter for about {h_default}): ", default=h_default)

    holds = click_holds(photo, corners)
    R = rectify_matrix(corners, w_cm, h_cm)
    cms = transform(R, [h["px"] for h in holds])
    for i, (h, c) in enumerate(zip(holds, cms), start=1):
        h["id"] = i
        h["cm"] = [round(float(c[0]), 1), round(float(c[1]), 1)]

    version = archive_existing(args.wall)
    os.makedirs(wall_path(args.wall), exist_ok=True)
    cv2.imwrite(wall_path(args.wall, "ref.jpg"), photo)
    wall = {
        "name": args.wall,
        "version": version,
        "scanned": time.strftime("%Y-%m-%d %H:%M"),
        "mode": "markers" if args.markers else "features",
        "corners_px": corners.tolist(),
        "size_cm": {"w": w_cm, "h": h_cm, "assumed": assumed},
        "holds": holds,
    }
    if markers_px:
        wall["markers_px"] = markers_px
    save_json(wall_path(args.wall, "wall.json"), wall)
    typed = sum(1 for h in holds if h["type"])
    print(f"\nSaved wall '{args.wall}' version {version}: {len(holds)} holds, {typed} tagged with a type.")
    print(f"Next: python ascent.py generate --wall {args.wall} --preview")


def save_route(wall, ids, name, how, height, train=()):
    warnings = route_warnings(wall, ids, height)
    route = {
        "name": name, "wall": wall["name"], "wall_version": wall["version"], "holds": ids,
        "estimated_grade": estimate_grade(wall, ids, height), "train": list(train), "made_by": how,
        "height_cm": height, "created": time.strftime("%Y-%m-%d %H:%M"), "warnings": warnings,
    }
    save_json(wall_path(wall["name"], "routes", f"{name}.json"), route)
    return route


def next_route_name(wall_name):
    d = wall_path(wall_name, "routes")
    n = len([f for f in os.listdir(d) if f.endswith(".json")]) + 1 if os.path.isdir(d) else 1
    return f"r{n}"


def cmd_generate(args):
    wall, ref = load_wall(args.wall)
    train = [t.strip().lower() for t in args.train.split(",") if t.strip()] if args.train else []
    typed = {h.get("type") for h in wall["holds"]}
    for t in train:
        if t in HOLD_TYPES.values() and t not in typed:
            print(f"Note: no hold is tagged '{t}', so that filter cannot work. Tag holds during the scan.")
    ids = None
    for moves in range(args.moves, 2, -1):
        ids = generate_route(wall, moves, args.height, train, args.level, args.seed)
        if ids:
            if moves < args.moves:
                print(f"Could not fit {args.moves} holds on this wall within reach - made a {moves}-hold route.")
            break
    if not ids:
        sys.exit("No route fits these settings. Try fewer moves, an easier level, or tap more holds.")
    name = args.name or next_route_name(args.wall)
    route = save_route(wall, ids, name, "generated", args.height, train)
    print(f"Route '{name}': holds {ids}, grade {route['estimated_grade']} (estimated)")
    for w in route["warnings"]:
        print("  ! " + w)
    print(f"Climb it: python ascent.py live --wall {args.wall} --route {name}")
    if args.preview:
        show_preview(wall, ref, route)


def cmd_build(args):
    wall, ref = load_wall(args.wall)
    view0, s = fit(ref)
    px = {h["id"]: np.array(h["px"]) for h in wall["holds"]}
    chosen = []
    win = "Ascent - build a route"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            p = np.array([x / s, y / s])
            hid, d = min(((i, np.linalg.norm(q - p)) for i, q in px.items()), key=lambda t: t[1])
            if d * s < 40 and hid not in chosen:
                chosen.append(hid)

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    while True:
        view = view0.copy()
        for hid, p in px.items():
            cv2.circle(view, (int(p[0] * s), int(p[1] * s)), 8, GREY, 1, cv2.LINE_AA)
        draw_route(view, [px[i] * s for i in chosen], 16)
        warns = route_warnings(wall, chosen, args.height) if len(chosen) > 1 else []
        lines = [f"{len(chosen)} holds. Click holds in climbing order.", "u = undo, Enter = save"]
        banner(view, lines)
        y = view.shape[0] - 20
        for w in reversed(warns[-3:]):
            put_text(view, w, (16, y), 0.6, AMBER)
            y -= 28
        cv2.imshow(win, view)
        k = cv2.waitKey(20) & 0xFF
        if k == ord("u") and chosen:
            chosen.pop()
        elif k in (13, 10) and len(chosen) >= 2:
            break
        elif k == 27:
            sys.exit("Cancelled.")
    cv2.destroyAllWindows()
    name = args.name or next_route_name(args.wall)
    route = save_route(wall, chosen, name, "built", args.height)
    print(f"Saved route '{name}': {chosen}, grade {route['estimated_grade']} (estimated)")
    print(f"Climb it: python ascent.py live --wall {args.wall} --route {name}")


def show_preview(wall, ref, route):
    view, s = fit(ref)
    px = {h["id"]: np.array(h["px"]) for h in wall["holds"]}
    draw_route(view, [px[i] * s for i in route["holds"]], 0.022 * ref.shape[1] * s)
    banner(view, [f"{route['name']}  {route['estimated_grade']} (estimated)", "any key = close"], WHITE)
    cv2.imshow("Ascent - route preview", view)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def cmd_preview(args):
    wall, ref = load_wall(args.wall)
    show_preview(wall, ref, load_route(args.wall, args.route))


def cmd_live(args):
    wall, ref = load_wall(args.wall)
    route = load_route(args.wall, args.route)
    if route.get("wall_version") != wall["version"]:
        print("Warning: this route was made on an older version of the wall.")
    px = {h["id"]: h["px"] for h in wall["holds"]}
    ref_pts = np.array([px[i] for i in route["holds"]], dtype=np.float32)
    ring_ref = 0.022 * ref.shape[1]
    tracker = Tracker(wall, ref, args.features)
    cap = open_camera(args.camera)

    smooth, last_lock, started = None, 0.0, time.time()
    writer, shots = None, 0
    messages = {
        "far": ("Move closer", AMBER),
        "close": ("Step back - show more of the wall", AMBER),
        "lost": (f"Point the camera at '{wall['name']}'", GREY),
    }
    print("q = quit, s = screenshot, v = record video")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        H, state = tracker.locate(frame)
        now = time.time()
        view = frame.copy()
        if H is not None:
            pts = transform(H, ref_pts)
            if smooth is not None and np.mean(np.linalg.norm(pts - smooth, axis=1)) < 40:
                pts = 0.5 * smooth + 0.5 * pts
            smooth, last_lock = pts, now
            edge = transform(H, [[0, 0], [ring_ref, 0]])
            radius = float(np.linalg.norm(edge[1] - edge[0]))
            draw_route(view, pts, radius)
            put_text(view, f"Locked  {route['name']}  {route['estimated_grade']}", (16, 34), 0.75, GREEN)
        elif smooth is not None and now - last_lock < 0.25:
            draw_route(view, smooth, 18)
        else:
            smooth = None
            since = now - max(last_lock, started)
            if since > 9:
                put_text(view, "Can't match this wall. Has it been reset?", (16, 34), 0.75, AMBER)
                put_text(view, f"If the holds changed: python ascent.py scan --wall {wall['name']}",
                         (16, 66), 0.6, WHITE)
            else:
                text, col = messages[state]
                put_text(view, text, (16, 34), 0.75, col)
        if writer is not None:
            writer.write(view)
            cv2.circle(view, (view.shape[1] - 24, 24), 9, (60, 60, 230), -1)
        cv2.imshow("Ascent - live", view)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q") or k == 27:
            break
        if k == ord("s"):
            shots += 1
            name = f"ascent_shot_{shots}.png"
            cv2.imwrite(name, view)
            print("Saved " + name)
        if k == ord("v"):
            if writer is None:
                name = time.strftime("ascent_demo_%H%M%S.mp4")
                writer = cv2.VideoWriter(name, cv2.VideoWriter_fourcc(*"mp4v"), 15, (view.shape[1], view.shape[0]))
                print("Recording to " + name)
            else:
                writer.release()
                writer = None
                print("Recording saved.")
    if writer is not None:
        writer.release()
    cap.release()
    cv2.destroyAllWindows()


def cmd_list(args):
    if not os.path.isdir(DATA_DIR):
        print("No walls yet. Run: python ascent.py scan --wall panel")
        return
    for name in sorted(os.listdir(DATA_DIR)):
        p = wall_path(name, "wall.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            w = json.load(f)
        print(f"{name}  version {w['version']}  {len(w['holds'])} holds  ({w['mode']})")
        d = wall_path(name, "routes")
        if os.path.isdir(d):
            for rf in sorted(os.listdir(d)):
                with open(os.path.join(d, rf), encoding="utf-8") as f:
                    r = json.load(f)
                print(f"   {r['name']}  {r['estimated_grade']}  {len(r['holds'])} holds  {r['made_by']}")


def main():
    ap = argparse.ArgumentParser(description="Project Ascent prototype")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selftest")
    sub.add_parser("list")

    p = sub.add_parser("scan")
    p.add_argument("--wall", required=True)
    p.add_argument("--image")
    p.add_argument("--markers", action="store_true")
    p.add_argument("--camera", type=int, default=0)

    p = sub.add_parser("generate")
    p.add_argument("--wall", required=True)
    p.add_argument("--name")
    p.add_argument("--moves", type=int, default=6)
    p.add_argument("--height", type=float, default=172)
    p.add_argument("--train", default="", help="comma list: reach, traverse, jug, crimp, sloper, pinch, pocket")
    p.add_argument("--level", choices=list(LEVEL_TARGET), default="medium")
    p.add_argument("--seed", type=int)
    p.add_argument("--preview", action="store_true")

    p = sub.add_parser("build")
    p.add_argument("--wall", required=True)
    p.add_argument("--name")
    p.add_argument("--height", type=float, default=172)

    p = sub.add_parser("live")
    p.add_argument("--wall", required=True)
    p.add_argument("--route", required=True)
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--features", choices=["sift", "orb"], default="sift")

    p = sub.add_parser("preview")
    p.add_argument("--wall", required=True)
    p.add_argument("--route", required=True)

    args = ap.parse_args()
    handler = {"selftest": cmd_selftest, "scan": cmd_scan, "generate": cmd_generate, "build": cmd_build,
               "live": cmd_live, "preview": cmd_preview, "list": cmd_list}[args.cmd]
    sys.exit(handler(args) or 0)


if __name__ == "__main__":
    main()
