"""
Project Ascent - laptop prototype for ArtRock (Tirol Hackathon 2026)

One file. Needs:  pip install opencv-contrib-python numpy

Commands
  python ascent.py selftest                         check the install, no camera needed
  python ascent.py scan --wall panel                photograph a wall, tap corners, tap holds
  python ascent.py scan --wall panel --image p.jpg  same, from a photo file
  python ascent.py scan --wall panel --markers      use the printed markers instead of tapping corners
  python ascent.py scan --wall panel --width 300 --height 220   wall size in cm, so nothing is typed
  python ascent.py generate --wall panel --train reach --moves 6 --height 172 --preview
  python ascent.py build --wall panel               tap holds in order to make your own route
  python ascent.py live --wall panel --route r1     route drawn on the live camera
  python ascent.py preview --wall panel --route r1  route drawn on the saved photo (demo backup)
  python ascent.py list                             show saved walls and routes
  python ascent.py track --wall panel --route r1    record my try: hand tracking with sounds (needs mediapipe)
  python ascent.py log --climber lena --wall panel --route r1 --result sent    log a climb (sent/tried/fail)
  python ascent.py log --climber lena               show Lena's logbook
  python ascent.py progress --climber lena          stats, skills / level / rehab sessions, milestones
  python ascent.py recommend --climber lena --wall panel --make 3    what to train next, by rules

Keys in the windows
  scan corners : click 4 corners (top-left, top-right, bottom-right, bottom-left), u = undo, Enter = done
  scan holds   : click each hold, then j/c/s/p/k to tag it jug/crimp/sloper/pinch/pocket, u = undo, Enter = done
  build        : click holds in climbing order, u = undo, Enter = done
  live         : q = quit, s = screenshot, v = start/stop recording a video
  track        : q = stop, m = sound on/off
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
        # Two looks at every image: as it is, and with local contrast evened out.
        # The plain look copes with dim light; the corrected one copes with spotlights.
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.refs = {
            "plain": self.det.detectAndCompute(small, None),
            "contrast": self.det.detectAndCompute(self.clahe.apply(small), None),
        }
        self.order = ["plain", "contrast"]
        kp, des = self.refs["plain"]
        if des is None or len(kp) < 30:
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
        first_state = None
        for look in list(self.order):
            img = small if look == "plain" else self.clahe.apply(small)
            H, state = self._match(look, img, F, fw, fh)
            if H is not None:
                if self.order[0] != look:
                    self.order = [look] + [o for o in self.order if o != look]
                return H, state
            first_state = first_state or state
        return None, first_state

    def _match(self, look, img, F, fw, fh):
        kp_r, des_r = self.refs[look]
        kp_f, des_f = self.det.detectAndCompute(img, None)
        if des_f is None or des_r is None or len(kp_f) < 10:
            return None, "lost"
        pairs = self.matcher.knnMatch(des_r, des_f, k=2)
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
        if len(good) < 12:
            return None, "lost"
        src = np.float32([kp_r[m.queryIdx].pt for m in good])
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
            last = i == len(holds) - 1
            cv2.circle(view, c, 15, DARK, 6, cv2.LINE_AA)
            cv2.circle(view, c, 15, AMBER if last else WHITE, 3, cv2.LINE_AA)
            if h["type"]:
                put_text(view, h["type"], (c[0] + 19, c[1] + 6), 0.5, WHITE, 1)
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


def positive_cm(raw):
    try:
        v = float(str(raw).replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{raw}' is not a number in centimetres")
    if v <= 0:
        raise argparse.ArgumentTypeError("must be more than 0 cm")
    return v


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
    w_arg, h_arg = getattr(args, "width", None), getattr(args, "height", None)
    if w_arg is not None:
        w_cm = float(w_arg)
        print(f"Width from --width: {w_cm:g} cm.")
    else:
        w_cm = ask_number("Distance between the two top corners, in cm (Enter to skip): ", default=-1)
    assumed = w_cm < 0
    if assumed:
        w_cm = 300.0
        print("Skipped. Assuming 300 cm wide - reach checks will be approximate.")
    h_default = round(w_cm * side / top)
    if h_arg is not None:
        h_cm = float(h_arg)
        print(f"Height from --height: {h_cm:g} cm.")
    else:
        h_cm = ask_number(f"Distance between the two left corners, in cm (Enter for about {h_default}): ",
                          default=h_default)

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


def save_route(wall, ids, name, how, height, train=(), by=None):
    warnings = route_warnings(wall, ids, height)
    route = {
        "name": name, "wall": wall["name"], "wall_version": wall["version"], "holds": ids,
        "estimated_grade": estimate_grade(wall, ids, height), "train": list(train), "made_by": how,
        "height_cm": height, "created": time.strftime("%Y-%m-%d %H:%M"), "warnings": warnings,
    }
    if by:
        route["by"] = climber_id(by)           # who set it - optional, older routes have no "by"
    save_json(wall_path(wall["name"], "routes", f"{name}.json"), route)
    return route


def route_names(wall_name):
    d = wall_path(wall_name, "routes")
    if not os.path.isdir(d):
        return []
    names = [f[:-5] for f in os.listdir(d) if f.endswith(".json")]
    return sorted(names, key=lambda n: (0, int(n[1:])) if n[:1] == "r" and n[1:].isdigit() else (1, n))


def next_route_name(wall_name):
    taken = set(route_names(wall_name))
    n = 1
    while f"r{n}" in taken:
        n += 1
    return f"r{n}"


def parse_train(text):
    return [t.strip().lower() for t in text.split(",") if t.strip()] if text else []


def make_generated_route(wall, moves, height, train, level, seed=None, name=None, by=None):
    """Generate, save and return a route, or None if nothing fits. Shared by 'generate' and the live 'g' key."""
    typed = {h.get("type") for h in wall["holds"]}
    for t in train:
        if t in HOLD_TYPES.values() and t not in typed:
            print(f"Note: no hold is tagged '{t}', so that filter cannot work. Tag holds during the scan.")
    ids = None
    for n in range(moves, 2, -1):
        ids = generate_route(wall, n, height, train, level, seed)
        if ids:
            if n < moves:
                print(f"Could not fit {moves} holds on this wall within reach - made a {n}-hold route.")
            break
    if not ids:
        return None
    name = name or next_route_name(wall["name"])
    route = save_route(wall, ids, name, "generated", height, train, by)
    print(f"Route '{name}': holds {ids}, grade {route['estimated_grade']} (estimated)")
    for w in route["warnings"]:
        print("  ! " + w)
    return route


def cmd_generate(args):
    wall, ref = load_wall(args.wall)
    route = make_generated_route(wall, args.moves, args.height, parse_train(args.train), args.level,
                                 args.seed, args.name, getattr(args, "by", None))
    if route is None:
        sys.exit("No route fits these settings. Try fewer moves, an easier level, or tap more holds.")
    print(f"Climb it: python ascent.py live --wall {args.wall} --route {route['name']}")
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
    route = save_route(wall, chosen, name, "built", args.height, by=getattr(args, "by", None))
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
    train = parse_train(args.train)
    names = route_names(args.wall)
    if args.route:
        route = load_route(args.wall, args.route)
    elif names:
        route = load_route(args.wall, names[-1])
    else:
        route = make_generated_route(wall, args.moves, args.height, train, args.level)
        if route is None:
            sys.exit("This wall has no routes and none could be generated. Tap more holds in the scan.")
    px = {h["id"]: h["px"] for h in wall["holds"]}

    def use(r):
        if r.get("wall_version") != wall["version"]:
            print(f"Warning: route {r['name']} was made on an older version of the wall.")
        return r, np.array([px[i] for i in r["holds"]], dtype=np.float32)

    route, ref_pts = use(route)
    ring_ref = 0.022 * ref.shape[1]
    tracker = Tracker(wall, ref, args.features)
    if args.video:
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            sys.exit(f"Could not open video {args.video}")
    else:
        cap = open_camera(args.camera)

    win = "Ascent - live"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    full = False
    smooth, last_lock, started = None, 0.0, time.time()
    writer, shots = None, 0
    messages = {
        "far": ("Move closer", AMBER),
        "close": ("Step back - show more of the wall", AMBER),
        "lost": (f"Point the camera at '{wall['name']}'", GREY),
    }
    print("q = quit, g = generate a new route, n = next route, f = full screen, s = screenshot, v = record video")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        H, state = tracker.locate(frame)
        now = time.time()
        view = frame.copy()
        if H is not None:
            pts = transform(H, ref_pts)
            if smooth is not None and len(smooth) == len(pts) and np.mean(np.linalg.norm(pts - smooth, axis=1)) < 40:
                pts = 0.5 * smooth + 0.5 * pts
            smooth, last_lock = pts, now
            edge = transform(H, [[0, 0], [ring_ref, 0]])
            radius = float(np.linalg.norm(edge[1] - edge[0]))
            draw_route(view, pts, radius)
            put_text(view, f"Locked  {route['name']}  {route['estimated_grade']}", (16, 34), 0.75, GREEN)
            detail = ", ".join(route.get("train") or []) or route.get("made_by", "")
            put_text(view, f"{len(route['holds'])} holds  {detail}", (16, 64), 0.6, WHITE)
            if route.get("warnings"):
                put_text(view, "! " + route["warnings"][0], (16, 92), 0.6, AMBER)
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
        put_text(view, "g new route   n next   f full screen   v record   q quit", (16, view.shape[0] - 18), 0.5, GREY, 1)
        if writer is not None:
            writer.write(view)
            cv2.circle(view, (view.shape[1] - 24, 24), 9, (60, 60, 230), -1)
        cv2.imshow(win, view)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q") or k == 27:
            break
        if k == ord("f"):
            full = not full
            cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if full else cv2.WINDOW_NORMAL)
        if k == ord("g"):
            new = make_generated_route(wall, args.moves, args.height, train, args.level)
            if new is None:
                print("No route fits these settings.")
            else:
                route, ref_pts = use(new)
                smooth = None
        if k == ord("n"):
            names = route_names(args.wall)
            if names:
                i = names.index(route["name"]) if route["name"] in names else -1
                route, ref_pts = use(load_route(args.wall, names[(i + 1) % len(names)]))
                smooth = None
                print(f"Showing route {route['name']}")
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


# ---------------------------------------------------------------- logbook

LOG_DIR = "logbook"
RESULTS = ("sent", "tried", "fail")


def climber_id(name):
    """A climber's name as a safe file name: letters, digits, - and _ only, lower case."""
    import unicodedata
    text = name.strip().lower().replace(" ", "_")
    for a, b in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"), ("\u00df", "ss")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text)
    cid = "".join(c for c in text if c.isascii() and (c.isalnum() or c in "-_"))
    if not cid:
        sys.exit(f"'{name}' can't be used as a name. Use letters and digits, for example: lena")
    return cid


def log_path(climber):
    return os.path.join(LOG_DIR, f"{climber_id(climber)}.json")


def load_log(climber):
    p = log_path(climber)
    if not os.path.exists(p):
        return {"climber": climber_id(climber), "entries": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def all_logs():
    if not os.path.isdir(LOG_DIR):
        return []
    out = []
    for f in sorted(os.listdir(LOG_DIR)):
        if f.endswith(".json"):
            with open(os.path.join(LOG_DIR, f), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out


def climbed_by(wall_name, wall_version, route_name):
    """Names of the climbers who sent this route on this version of the wall ("N people climbed this")."""
    return sorted({lg["climber"] for lg in all_logs() for e in lg["entries"]
                   if e["wall"] == wall_name and e["wall_version"] == wall_version
                   and e["route"] == route_name and e["result"] == "sent"})


def add_log_entry(climber, wall, route, result, by="self", date=None, note=None, attempt=None):
    types = {h["id"]: h.get("type") for h in wall["holds"]}
    entry = {
        "date": date or time.strftime("%Y-%m-%d %H:%M"),
        "wall": wall["name"], "wall_version": wall["version"], "route": route["name"],
        "result": result, "by": by,
        # a copy of what the route was, so the history still means something after a re-scan
        "estimated_grade": route.get("estimated_grade"), "train": route.get("train", []),
        "hold_types": sorted({types.get(i) for i in route["holds"] if types.get(i)}),
        "moves": len(route["holds"]) - 1,
    }
    if note:
        entry["note"] = note
    if attempt:
        entry["attempt"] = attempt
    log = load_log(climber)
    log["entries"].append(entry)
    save_json(log_path(climber), log)
    return entry


def valid_date(raw):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.strptime(raw, fmt))
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("use YYYY-MM-DD, for example 2026-11-06")


def cmd_log(args):
    cid = climber_id(args.climber)
    if args.undo:
        log = load_log(cid)
        if not log["entries"]:
            sys.exit(f"{cid}'s logbook is empty.")
        e = log["entries"].pop()
        save_json(log_path(cid), log)
        print(f"Removed the last entry: {e['date']}  {e['wall']} {e['route']}  {e['result']}")
        return
    if args.route or args.result or args.wall:
        if not (args.wall and args.route and args.result):
            sys.exit("To log a climb give all three: --wall, --route and --result sent|tried|fail")
        wall, _ = load_wall(args.wall)
        route = load_route(args.wall, args.route)
        e = add_log_entry(cid, wall, route, args.result, "self", args.date, args.note)
        print(f"Logged for {cid}: {e['wall']} {e['route']} {e['estimated_grade']} (estimated) - {e['result']}")
        n = len(climbed_by(wall["name"], wall["version"], route["name"]))
        print(f"{n} {'person has' if n == 1 else 'people have'} sent this route on this wall.")
        return
    log = load_log(cid)
    if not log["entries"]:
        print(f"{cid}'s logbook is empty. Log a climb: python ascent.py log --climber {cid} "
              "--wall panel --route r1 --result sent")
        return
    print(f"Logbook of {cid} ({len(log['entries'])} climbs)")
    for e in log["entries"]:
        skills = ", ".join(e.get("train") or e.get("hold_types") or [])
        extra = "  (camera)" if e.get("by") == "camera" else ""
        note = f"  - {e['note']}" if e.get("note") else ""
        print(f"  {e['date']}  {e['wall']} v{e['wall_version']} {e['route']:<6} {e.get('estimated_grade') or '?':<4} "
              f"{e['result']:<5} {skills}{extra}{note}")


# ---------------------------------------------------------------- progress and recommendations (rules, no AI)

PROFILE_DIR = "profiles"
GOALS = ("train", "play", "rehab")        # Lena, Max, Laura
SKILLS = list(HOLD_TYPES.values()) + ["reach", "traverse"]
LEVELS = list(LEVEL_TARGET)


def load_profile(climber):
    p = os.path.join(PROFILE_DIR, f"{climber_id(climber)}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def climber_settings(args):
    """Height, level, goal and age group: from the options if given, else the profile, else defaults."""
    prof = load_profile(args.climber) or {}
    rehab = prof.get("rehab") or {}
    s = {
        "height": getattr(args, "height", None) or prof.get("height_cm") or 172.0,
        "level": getattr(args, "level", None) or rehab.get("level") or prof.get("level") or "medium",
        "goal": getattr(args, "goal", None) or prof.get("goal") or "train",
        "minor": bool(prof.get("minor")),
        "rehab": rehab, "profile": bool(prof),
    }
    if s["goal"] == "rehab" and rehab.get("level"):
        s["level"] = rehab["level"]           # only the therapist changes a rehab level
    return s


def entry_skills(e):
    return set(e.get("hold_types") or []) | set(e.get("train") or [])


def week_of(date):
    return time.strftime("%G-W%V", time.strptime(date[:10], "%Y-%m-%d"))


def routes_set_by(climber):
    """Routes this climber made (generate/build --by), with who else sent them."""
    cid = climber_id(climber)
    out = []
    if not os.path.isdir(DATA_DIR):
        return out
    for wname in sorted(os.listdir(DATA_DIR)):
        p = wall_path(wname, "wall.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            version = json.load(f)["version"]
        for rname in route_names(wname):
            r = load_route(wname, rname)
            if r.get("by") == cid:
                others = [c for c in climbed_by(wname, version, rname) if c != cid]
                out.append((wname, rname, others))
    return out


def badges(climber, entries):
    """Milestones reward consistency, variety, routes set and climbing together - never the hardest grade,
    never a streak that punishes a rest day."""
    routes = {(e["wall"], e["wall_version"], e["route"]) for e in entries}
    types = set().union(*[set(e.get("hold_types") or []) for e in entries]) if entries else set()
    weeks = {week_of(e["date"]) for e in entries}
    out = []
    if entries:
        out.append("First climb logged")
    if any(e["result"] == "sent" for e in entries):
        out.append("First send")
    if len(routes) >= 5:
        out.append("Explorer: 5 different routes")
    if types >= set(HOLD_TYPES.values()):
        out.append("All-rounder: every hold type")
    if len(weeks) >= 4:
        out.append("Regular: climbed in 4 different weeks (rest weeks are fine)")
    if any(others for _, _, others in routes_set_by(climber)):
        out.append("Route setter: someone else sent your route")
    if any(e.get("challenge") for e in entries):
        out.append("Team player: finished a challenge")
    return out


def play_points(climber, entries):
    """Max's level. Points for showing up, trying new routes, new hold types and setting routes others
    climb. No points for grade, so a harder route is never worth more."""
    days = {e["date"][:10] for e in entries}
    routes = {(e["wall"], e["wall_version"], e["route"]) for e in entries}
    types = set().union(*[set(e.get("hold_types") or []) for e in entries]) if entries else set()
    repeats = sum(len(others) for _, _, others in routes_set_by(climber))
    pts = len(days) + 2 * len(routes) + len(types) + 3 * repeats + 2 * sum(1 for e in entries if e.get("challenge"))
    return pts, 1 + pts // 10, 10 - pts % 10


def bar(n, total, width=20):
    k = int(round(width * n / total)) if total else 0
    return "#" * k + "." * (width - k)


def cmd_progress(args):
    cid = climber_id(args.climber)
    st = climber_settings(args)
    entries = load_log(cid)["entries"]
    if not entries:
        print(f"Nothing logged for {cid} yet. Log a climb: python ascent.py log --climber {cid} "
              "--wall panel --route r1 --result sent")
        return
    res = {r: sum(1 for e in entries if e["result"] == r) for r in RESULTS}
    days = sorted({e["date"][:10] for e in entries})
    routes = {(e["wall"], e["wall_version"], e["route"]) for e in entries}
    secs = sum((e.get("attempt") or {}).get("seconds") or 0 for e in entries)
    print(f"Progress of {cid}  (goal: {st['goal']})")
    print(f"  {len(entries)} climbs on {len(days)} days, {len(routes)} different routes")
    print(f"  sent {res['sent']}, tried {res['tried']}, fail {res['fail']}"
          + (f", {secs / 60:.1f} min on the wall (camera)" if secs else ""))

    if st["goal"] == "rehab":
        weeks = {}
        for e in entries:
            weeks.setdefault(week_of(e["date"]), set()).add(e["date"][:10])
        target = st["rehab"].get("sessions_per_week")
        print("\n  Sessions per week" + (f" (therapist's goal: {target})" if target else ""))
        for w in sorted(weeks)[-6:]:
            n = len(weeks[w])
            mark = "  goal met" if target and n >= target else ""
            print(f"    {w}  {'#' * n:<8} {n}{mark}")
        lvl = st["rehab"].get("level")
        if lvl:
            print(f"  Level set by the therapist: {lvl}")
        print("\n  This is a record for you and your therapist. It does not judge whether a movement is safe.")
        return

    if st["goal"] == "play":
        pts, level, to_next = play_points(cid, entries)
        print(f"\n  Level {level}  ({pts} points, {to_next} to the next level)")
        print("  Points come from climbing days, new routes, new hold types and routes you set that others")
        print("  climb - never from grade. Rest days cost nothing.")
    else:
        print("\n  Skills (climbs with each kind of hold or move)")
        counts = {k: sum(1 for e in entries if k in entry_skills(e)) for k in SKILLS}
        sends = {k: sum(1 for e in entries if k in entry_skills(e) and e["result"] == "sent") for k in SKILLS}
        for k in SKILLS:
            print(f"    {k:<9} {bar(counts[k], len(entries))} {counts[k]:>3} climbs, {sends[k]} sent")
    got = badges(cid, entries)
    if got:
        print("\n  Milestones")
        for b in got:
            print("    * " + b)
    print(f"\n  What next? python ascent.py recommend --climber {cid} --wall {entries[-1]['wall']}")


def recommendations(climber, wall, st):
    """Rules, no AI. Returns (reasons, train, level, existing) - every line says why."""
    entries = [e for e in load_log(climber)["entries"]]
    typed = {h.get("type") for h in wall["holds"] if h.get("type")}
    available = [k for k in SKILLS if k in typed or k in ("reach", "traverse")]
    reasons = []
    level = st["level"]
    if not entries:
        reasons.append("Nothing logged yet, so start with an easy route to warm up.")
        return reasons, [], "easy" if st["goal"] != "rehab" else level, []

    counts = {k: sum(1 for e in entries if k in entry_skills(e)) for k in available}
    low = min(counts.values())
    rare = [k for k in available if counts[k] == low]
    pick = rare[0]
    reasons.append(f"You rarely climb {pick}{'s' if pick in HOLD_TYPES.values() else ''} "
                   f"({counts[pick]} of your {len(entries)} climbs).")
    if pick in HOLD_TYPES.values() and pick not in typed:
        reasons.append(f"No hold on this wall is tagged {pick}.")

    recent = entries[-5:]
    fails = sum(1 for e in recent if e["result"] == "fail")
    sends = sum(1 for e in recent if e["result"] == "sent")
    i = LEVELS.index(level)
    if st["goal"] == "rehab":
        reasons.append(f"Level {level}, as set by your therapist. Only the therapist changes it.")
    elif fails >= 3 and i > 0:
        level = LEVELS[i - 1]
        reasons.append(f"{fails} of your last {len(recent)} climbs did not get going, so one level easier: {level}.")
    elif sends == len(recent) == 5 and i < len(LEVELS) - 1 and st["goal"] == "train" and not st["minor"]:
        reasons.append(f"You sent your last 5 climbs. If you feel like it, try {LEVELS[i + 1]} "
                       "(--level " + LEVELS[i + 1] + "). Variety helps as much as difficulty.")
    else:
        reasons.append(f"Level {level}" + (" - new skills before harder grades." if st["goal"] == "play" else "."))

    sent_by_me = {(e["wall"], e["wall_version"], e["route"]) for e in entries if e["result"] == "sent"}
    existing = []
    for rname in route_names(wall["name"]):
        r = load_route(wall["name"], rname)
        if (wall["name"], wall["version"], rname) in sent_by_me or r.get("wall_version") != wall["version"]:
            continue
        types = {h["id"]: h.get("type") for h in wall["holds"]}
        skills = set(r.get("train") or []) | {types.get(i) for i in r["holds"]}
        if pick in skills:
            existing.append((rname, r.get("estimated_grade"), len(climbed_by(wall["name"], wall["version"], rname))))
    return reasons, [pick], level, existing[:3]


def cmd_recommend(args):
    cid = climber_id(args.climber)
    st = climber_settings(args)
    wall, _ = load_wall(args.wall)
    reasons, train, level, existing = recommendations(cid, wall, st)
    print(f"Recommendation for {cid} on {wall['name']}  (rules, not AI - each line says why)")
    for r in reasons:
        print("  - " + r)
    t = f" --train {','.join(train)}" if train else ""
    cmd = f"python ascent.py generate --wall {wall['name']}{t} --level {level} --height {st['height']:g} --by {cid}"
    print(f"\n  Make a route: {cmd}")
    for name, grade, n in existing:
        print(f"  Or climb {name} ({grade}, estimated) - {n} {'person' if n == 1 else 'people'} sent it")
    if args.make:
        print()
        for _ in range(args.make):
            if make_generated_route(wall, args.moves, st["height"], train, level, by=cid) is None:
                print("No more routes fit these settings.")
                break
        print(f"Climb them: python ascent.py live --wall {wall['name']} --route <name>")


# ---------------------------------------------------------------- motion tracking with audio

POSE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                  "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")
POSE_MODEL_PATH = os.path.join("models", "pose_landmarker_lite.task")
HAND_JOINTS = {"left": (15, 17, 19), "right": (16, 18, 20)}   # MediaPipe Pose: wrist, pinky, index
TOUCH_CM = 12.0      # a hand closer than this to a hold's centre is on that hold
DWELL_S = 0.4        # ... and must stay that long, so a hand passing by doesn't count
SOUND_FILES = {}


class PoseDetector:
    """MediaPipe Pose, run on this laptop. hands(frame, t) -> {"left": (x, y), "right": (x, y)} in frame
    pixels, only for hands it can see. MediaPipe is imported here, so every other command works without it."""

    def __init__(self, model_path=None):
        try:
            import mediapipe as mp
        except ImportError:
            sys.exit("track needs MediaPipe: pip install mediapipe   (every other command works without it)")
        self.mp, self.legacy, self.last_ms = mp, None, -1
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
            self.legacy = mp.solutions.pose.Pose(model_complexity=0)
            return
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        path = model_path or POSE_MODEL_PATH
        if not os.path.exists(path):
            print(f"Downloading the pose model once (5.5 MB) to {path} ...")
            try:
                import urllib.request
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                urllib.request.urlretrieve(POSE_MODEL_URL, path + ".part")
                os.replace(path + ".part", path)
            except Exception as e:
                sys.exit(f"Could not download the pose model ({e}).\nDownload it by hand from\n  {POSE_MODEL_URL}\n"
                         f"save it as {path}, or pass --pose-model FILE.")
        opts = vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=path),
                                            running_mode=vision.RunningMode.VIDEO, num_poses=1)
        self.tasks = vision.PoseLandmarker.create_from_options(opts)

    def hands(self, frame, t):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        if self.legacy is not None:
            res = self.legacy.process(rgb)
            lms = res.pose_landmarks.landmark if res.pose_landmarks else None
        else:
            ms = max(int(t * 1000), self.last_ms + 1)          # timestamps must always increase
            self.last_ms = ms
            res = self.tasks.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), ms)
            lms = res.pose_landmarks[0] if res.pose_landmarks else None
        out = {}
        if lms:
            for side, joints in HAND_JOINTS.items():
                pts = [lms[j] for j in joints]
                if min(getattr(p, "visibility", 1.0) or 0.0 for p in pts) > 0.5:
                    out[side] = (float(np.mean([p.x for p in pts])) * w, float(np.mean([p.y for p in pts])) * h)
        return out

    def close(self):
        (self.legacy or self.tasks).close()


class AttemptWatcher:
    """Decides, from hand positions in wall centimetres, which holds were touched and whether in order.
    Rules only: a hand is on a hold when it stays within TOUCH_CM of the hold's centre for DWELL_S.
    Feet are free, so only hands count. Never judges whether a movement is safe."""

    def __init__(self, wall, route_ids, touch_cm=TOUCH_CM, dwell=DWELL_S):
        self.pos = hold_cm(wall)
        self.route = list(route_ids)
        self.touch_cm, self.dwell = touch_cm, dwell
        self.next = 0                  # index in the route of the next hold to reach
        self.skipped, self.off_route, self.touches = [], [], []
        self.cand, self.on, self.last_off = {}, {}, {}
        self.started_at, self.finished_at = None, None

    def nearest(self, p):
        hid, d = min(((i, float(np.linalg.norm(q - p))) for i, q in self.pos.items()), key=lambda x: x[1])
        return hid if d <= self.touch_cm else None

    def update(self, hands_cm, t):
        """hands_cm: {"left": (x, y), "right": (x, y)} in cm. Returns a list of (sound, message)."""
        events = []
        for side in ("left", "right"):
            hid = self.nearest(np.array(hands_cm[side], dtype=float)) if side in hands_cm else None
            if hid is None:
                self.cand.pop(side, None)
                self.on[side] = None
                continue
            if self.cand.get(side, (None,))[0] != hid:
                self.cand[side] = (hid, t)
            if t - self.cand[side][1] >= self.dwell and self.on.get(side) != hid:
                self.on[side] = hid
                ev = self._arrive(hid, t, side)
                if ev:
                    events.append(ev)
        return events

    def _arrive(self, hid, t, side):
        self.touches.append({"hold": hid, "hand": side, "t": round(t, 2)})
        n = len(self.route)
        if hid in self.route:
            idx = self.route.index(hid)
            if idx < self.next:
                return None                                  # back on a hold already reached: fine, silent
            if self.next == 0:
                self.started_at = t
            if idx > self.next:
                self.skipped += self.route[self.next:idx]
                msg = f"Hold {idx + 1} before hold {self.next + 1} - out of order"
                self.next = idx + 1
                kind = "order"
            else:
                self.next += 1
                kind, msg = "good", f"Hold {idx + 1} of {n}"
            if self.next == n:
                self.finished_at = t
                return "top", "Top! " + ("Clean, in order." if self.clean() else "Finish reached.")
            return kind, msg
        if self.next == 0 or self.finished_at is not None:
            return None                                      # before the start or after the top: not counted
        if t - self.last_off.get(hid, -99) < 2.0:
            return None
        self.last_off[hid] = t
        self.off_route.append(hid)
        return "off", "That hold is not on the route"

    def clean(self):
        return not self.skipped and not self.off_route

    def result(self):
        """sent = reached the finish, in order, no off-route holds; tried = got past the start; fail = did not."""
        if self.next == len(self.route) and self.clean():
            return "sent"
        return "tried" if self.next >= 2 else "fail"

    def summary(self):
        return {"result": self.result(), "reached": self.next, "of": len(self.route),
                "skipped": self.skipped, "off_route": self.off_route, "touches": self.touches,
                "seconds": round(self.finished_at - self.started_at, 1)
                if self.started_at is not None and self.finished_at is not None else None}


def make_sound_files():
    """Short tones, made once with the standard library: no sound files in git, no extra install."""
    import tempfile
    import wave
    tones = {"good": [(880, 0.09), (1320, 0.12)], "order": [(520, 0.12), (520, 0.12)],
             "off": [(220, 0.35)], "top": [(660, 0.1), (880, 0.1), (1320, 0.25)]}
    d = tempfile.mkdtemp(prefix="ascent_sounds_")
    rate = 22050
    for kind, notes in tones.items():
        samples = []
        for f, dur in notes:
            k = int(rate * dur)
            env = np.minimum(1, np.minimum(np.arange(k), np.arange(k)[::-1]) / (0.01 * rate))
            samples.append(0.5 * env * np.sin(2 * np.pi * f * np.arange(k) / rate))
            samples.append(np.zeros(int(rate * 0.03)))
        data = (np.concatenate(samples) * 32767).astype("<i2").tobytes()
        path = os.path.join(d, f"{kind}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(data)
        SOUND_FILES[kind] = path


def play_sound(kind):
    """Plays without waiting: Windows winsound, macOS afplay, Linux paplay/aplay, else the terminal bell."""
    try:
        if not SOUND_FILES:
            make_sound_files()
        path = SOUND_FILES[kind]
        if os.name == "nt":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        import subprocess
        for player in (["afplay"], ["paplay"], ["aplay", "-q"]):
            if shutil.which(player[0]):
                subprocess.Popen(player + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    except Exception:
        pass
    print("\a", end="", flush=True)


def make_pose_detector(model_path=None):
    return PoseDetector(model_path)


def run_track(args):
    """Runs one tracked attempt and returns its summary."""
    wall, ref = load_wall(args.wall)
    route = load_route(args.wall, args.route)
    if route.get("wall_version") != wall["version"]:
        print(f"Warning: route {route['name']} was made on an older version of the wall.")
    px = {h["id"]: h["px"] for h in wall["holds"]}
    ref_pts = np.array([px[i] for i in route["holds"]], dtype=np.float32)
    R = rectify_matrix(wall["corners_px"], wall["size_cm"]["w"], wall["size_cm"]["h"])
    print("Record my try: put the camera 3-4 m back, whole wall in frame, never on the landing zone.")
    print("Body tracking uses an AI model (MediaPipe Pose) on this laptop. No video is saved and nothing")
    print("leaves the device. It only checks which holds your hands touch - it does not judge whether a")
    print("movement is safe. Only film people who agreed to it.")
    detector = make_pose_detector(args.pose_model)
    tracker = Tracker(wall, ref, args.features)
    if args.video:
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            sys.exit(f"Could not open video {args.video}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    else:
        cap, fps = open_camera(args.camera), None
    watcher = AttemptWatcher(wall, route["holds"], args.touch_cm)
    sound = (lambda kind: None) if args.mute else play_sound
    win = "Ascent - record my try"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    ring_ref = 0.022 * ref.shape[1]
    flash, frame_i, started = None, 0, time.time()
    print("q = stop, m = sound on/off")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_i / fps if fps else time.time() - started
        frame_i += 1
        H, state = tracker.locate(frame)
        view = frame.copy()
        if H is not None:
            # Never guess: hands only count, and rings are only drawn, while the wall is locked.
            pts = transform(H, ref_pts)
            edge = transform(H, [[0, 0], [ring_ref, 0]])
            draw_route(view, pts, float(np.linalg.norm(edge[1] - edge[0])))
            for i in range(watcher.next):
                cv2.circle(view, tuple(int(v) for v in pts[i]), 7, GREEN, -1, cv2.LINE_AA)
            hands = detector.hands(frame, t)
            if hands:
                to_cm = R @ np.linalg.inv(H)
                sides = list(hands)
                cms = transform(to_cm, [hands[s] for s in sides])
                for s in sides:
                    cv2.circle(view, tuple(int(v) for v in hands[s]), 9, WHITE, 2, cv2.LINE_AA)
                for kind, msg in watcher.update(dict(zip(sides, cms)), t):
                    sound(kind)
                    print(f"{t:6.1f} s  {msg}")
                    flash = (msg, GREEN if kind in ("good", "top") else AMBER, t)
            nxt = (f"Next: hold {watcher.next + 1} of {len(route['holds'])}" if watcher.next < len(route["holds"])
                   else "Top reached")
            put_text(view, f"Locked  {route['name']}  {nxt}", (16, 34), 0.75, GREEN)
        else:
            put_text(view, {"far": "Move closer", "close": "Step back - show the whole wall"}.get(
                state, f"Point the camera at '{wall['name']}'"), (16, 34), 0.75, AMBER)
        if flash and t - flash[2] < 1.5:
            put_text(view, flash[0], (16, 70), 0.8, flash[1])
        put_text(view, "AI body tracking on this laptop - no video saved.  m sound  q stop",
                 (16, view.shape[0] - 18), 0.5, GREY, 1)
        cv2.imshow(win, view)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q") or k == 27:
            break
        if k == ord("m"):
            sound = play_sound if sound is not play_sound else (lambda kind: None)
            print("Sound " + ("on" if sound is play_sound else "off"))
    cap.release()
    detector.close()
    cv2.destroyAllWindows()
    s = watcher.summary()
    print(f"\nReached {s['reached']} of {s['of']} holds in order.", end="")
    if s["skipped"]:
        print(f"  Skipped: {s['skipped']}.", end="")
    if s["off_route"]:
        print(f"  Off-route holds touched: {s['off_route']}.", end="")
    print(f"\nThe camera's guess: {s['result']}. You know better - it is only a suggestion.")
    if getattr(args, "climber", None):
        if s["reached"] == 0:
            print("No hold of the route was reached, so nothing was logged.")
        else:
            attempt = {k: s[k] for k in ("reached", "of", "skipped", "off_route", "seconds")}
            add_log_entry(args.climber, wall, route, s["result"], "camera", attempt=attempt)
            print(f"Logged for {climber_id(args.climber)} as '{s['result']}'. Wrong? Fix it with:\n"
                  f"  python ascent.py log --climber {climber_id(args.climber)} --undo   and log it again by hand.")
    return s


def cmd_track(args):
    run_track(args)


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
    p.add_argument("--width", type=positive_cm, help="wall width in cm (top-left to top-right corner); skips the question")
    p.add_argument("--height", type=positive_cm, help="wall height in cm (top-left to bottom-left corner); skips the question")

    p = sub.add_parser("generate")
    p.add_argument("--wall", required=True)
    p.add_argument("--name")
    p.add_argument("--moves", type=int, default=6)
    p.add_argument("--height", type=float, default=172)
    p.add_argument("--train", default="", help="comma list: reach, traverse, jug, crimp, sloper, pinch, pocket")
    p.add_argument("--level", choices=list(LEVEL_TARGET), default="medium")
    p.add_argument("--seed", type=int)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--by", help="who set the route (optional, counts for their progress)")

    p = sub.add_parser("build")
    p.add_argument("--wall", required=True)
    p.add_argument("--name")
    p.add_argument("--height", type=float, default=172)
    p.add_argument("--by", help="who set the route (optional, counts for their progress)")

    p = sub.add_parser("live")
    p.add_argument("--wall", required=True)
    p.add_argument("--route", help="route to show first; default: the newest one")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--video", help="use a video file instead of the webcam")
    p.add_argument("--features", choices=["sift", "orb"], default="sift")
    p.add_argument("--train", default="", help="settings for the g key: comma list like generate")
    p.add_argument("--moves", type=int, default=6)
    p.add_argument("--height", type=float, default=172)
    p.add_argument("--level", choices=list(LEVEL_TARGET), default="medium")

    p = sub.add_parser("track", help="record my try: hand tracking with sounds (needs mediapipe)")
    p.add_argument("--wall", required=True)
    p.add_argument("--route", required=True)
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--video", help="use a video file instead of the webcam")
    p.add_argument("--features", choices=["sift", "orb"], default="sift")
    p.add_argument("--touch-cm", type=positive_cm, default=TOUCH_CM, help="how close a hand must be to a hold")
    p.add_argument("--pose-model", help="MediaPipe pose model file (downloaded once if missing)")
    p.add_argument("--mute", action="store_true", help="no sounds, messages only")
    p.add_argument("--climber", help="save the attempt in this climber's logbook")

    p = sub.add_parser("progress", help="stats, skills, level or rehab sessions, milestones")
    p.add_argument("--climber", required=True)
    p.add_argument("--goal", choices=GOALS, help="train (skills), play (levels), rehab (sessions); default: profile")

    p = sub.add_parser("recommend", help="what to climb next, by rules")
    p.add_argument("--climber", required=True)
    p.add_argument("--wall", required=True)
    p.add_argument("--goal", choices=GOALS)
    p.add_argument("--height", type=positive_cm, help="climber height in cm; default: profile, else 172")
    p.add_argument("--level", choices=LEVELS, help="default: profile, else medium")
    p.add_argument("--make", type=int, default=0, help="also generate this many routes")
    p.add_argument("--moves", type=int, default=6)

    p = sub.add_parser("log", help="logbook: log a climb, or show a climber's history")
    p.add_argument("--climber", required=True)
    p.add_argument("--wall")
    p.add_argument("--route")
    p.add_argument("--result", choices=RESULTS)
    p.add_argument("--date", type=valid_date, help="YYYY-MM-DD, default now")
    p.add_argument("--note")
    p.add_argument("--undo", action="store_true", help="remove the last entry")

    p = sub.add_parser("preview")
    p.add_argument("--wall", required=True)
    p.add_argument("--route", required=True)

    args = ap.parse_args()
    handler = {"selftest": cmd_selftest, "scan": cmd_scan, "generate": cmd_generate, "build": cmd_build,
               "live": cmd_live, "preview": cmd_preview, "list": cmd_list, "track": cmd_track,
               "log": cmd_log, "progress": cmd_progress, "recommend": cmd_recommend}[args.cmd]
    sys.exit(handler(args) or 0)


if __name__ == "__main__":
    main()
