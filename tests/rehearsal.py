"""
Full rehearsal of the prototype without a screen or a camera.

Clicks, keypresses and typed answers are scripted, and the webcam is replaced by a
synthetic video of a wall seen from a moving camera. Run from the repo root:

    python tests/rehearsal.py
"""

import builtins
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import ascent  # noqa: E402


class FakeGUI:
    """Stands in for OpenCV windows: replays scripted clicks and keys."""

    def __init__(self):
        self.actions, self.callback, self.strict, self.frames = [], None, True, 0

    def setMouseCallback(self, win, cb, *a):
        self.callback = cb

    def waitKey(self, delay=0):
        self.frames += 1
        if not self.actions:
            if self.strict:
                raise RuntimeError("A window was waiting for input the script did not provide.")
            return -1
        kind, *val = self.actions.pop(0)
        if kind == "click":
            self.callback(cv2.EVENT_LBUTTONDOWN, int(val[0]), int(val[1]), 0, None)
            return -1
        return val[0] if isinstance(val[0], int) else ord(val[0])

    def install(self):
        cv2.imshow = lambda *a, **k: None
        cv2.namedWindow = lambda *a, **k: None
        cv2.destroyWindow = lambda *a, **k: None
        cv2.destroyAllWindows = lambda *a, **k: None
        cv2.setMouseCallback = self.setMouseCallback
        cv2.setWindowProperty = lambda *a, **k: None
        cv2.waitKey = self.waitKey


def make_wall_photo(seed=5, markers=False):
    rng = np.random.default_rng(seed)
    img = np.full((720, 1280, 3), 45, np.uint8)
    img = cv2.add(img, np.repeat(rng.integers(0, 20, (720, 1280, 1), dtype=np.uint8), 3, axis=2))
    corners = np.array([[230, 70], [1050, 70], [1050, 660], [230, 660]], np.float32)
    cv2.fillPoly(img, [corners.astype(np.int32)], (88, 92, 96))
    wood = rng.integers(0, 35, (720, 1280, 1), dtype=np.uint8)
    mask = np.zeros((720, 1280), np.uint8)
    cv2.fillPoly(mask, [corners.astype(np.int32)], 255)
    img[mask > 0] = cv2.add(img, np.repeat(wood, 3, axis=2))[mask > 0]
    colours = [(25, 25, 25), (40, 210, 240), (200, 120, 40), (60, 60, 220), (30, 140, 250)]
    holds = []
    while len(holds) < 26:
        x, y = int(rng.integers(280, 1000)), int(rng.integers(110, 620))
        if all((x - a) ** 2 + (y - b) ** 2 > 55 ** 2 for a, b in holds):
            holds.append((x, y))
    for i, (x, y) in enumerate(holds):
        axes = (int(rng.integers(13, 24)), int(rng.integers(10, 18)))
        cv2.ellipse(img, (x, y), axes, float(rng.integers(0, 180)), 0, 360, colours[i % 5], -1, cv2.LINE_AA)
        cv2.ellipse(img, (x, y), axes, 0, 0, 360, (12, 12, 12), 2, cv2.LINE_AA)
        cv2.circle(img, (x - 4, y - 3), 3, (235, 235, 235), -1)
    if markers:
        d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for i, (x, y) in enumerate(corners.astype(int)):
            tile = np.full((96, 96), 255, np.uint8)
            tile[12:84, 12:84] = cv2.aruco.generateImageMarker(d, i, 72)
            img[y - 48:y + 48, x - 48:x + 48] = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
    return img, holds, corners


def camera_path(n):
    """A camera drifting and turning in front of the wall."""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        a = np.deg2rad(-6 + 12 * t)
        s = 0.88 + 0.12 * np.sin(np.pi * t)
        H = np.array([[s * np.cos(a), -s * np.sin(a), 40 + 60 * t],
                      [s * np.sin(a), s * np.cos(a), 30 - 20 * t],
                      [0.00008 * np.sin(3 * t), 0.00006, 1.0]])
        out.append(H)
    return out


def write_video(path, photo, Hs, blank_tail=0):
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 15, (1280, 720))
    for H in Hs:
        f = cv2.warpPerspective(photo, H, (1280, 720), borderValue=(30, 30, 30))
        f = cv2.convertScaleAbs(f, alpha=1.08, beta=-6)
        w.write(f)
    for _ in range(blank_tail):
        w.write(np.full((720, 1280, 3), 30, np.uint8))
    w.release()


def rehearse_track(gui, photo, holds, corners):
    """Motion tracking: a scripted hand moves over the holds of a moving-camera video."""
    _, s = ascent.fit(photo)
    disp = lambda p: ("click", p[0] * s, p[1] * s)
    gui.strict = True
    gui.actions = [disp(c) for c in corners] + [("key", 13)] + [disp(h) for h in holds] + [("key", 13)]
    ascent.cmd_scan(SimpleNamespace(wall="tw", image="panel.jpg", markers=False, camera=0, width=300.0, height=216.0))
    wall = json.load(open("walls/tw/wall.json"))
    px = {h["id"]: h["px"] for h in wall["holds"]}
    by_height = sorted(px, key=lambda i: -px[i][1])            # bottom of the photo first
    route = by_height[0:25:5]                                  # 5 holds, bottom to top
    off = by_height[2]
    ascent.save_route(wall, route, "t1", "built", 172)

    def run(script, climber=None):
        frames = 10 * len(script) + 6
        Hs = camera_path(frames)
        write_video("track.avi", photo, Hs)

        class FakePose:
            def hands(self, frame, t):
                i = int(round(t * 15))
                k = i // 10
                if k >= len(script) or script[k] is None:
                    return {}
                x, y = ascent.transform(Hs[i], [px[script[k]]])[0]
                return {"right": (x + 3, y - 2)}

            def close(self):
                pass

        sounds = []
        ascent.make_pose_detector = lambda path=None: FakePose()
        real_play = ascent.play_sound
        ascent.play_sound = sounds.append
        gui.strict = False
        gui.actions = []
        try:
            summary = ascent.run_track(SimpleNamespace(wall="tw", route="t1", camera=0, video="track.avi",
                                                       features="sift", touch_cm=ascent.TOUCH_CM,
                                                       pose_model=None, mute=False, climber=climber))
        finally:
            ascent.play_sound = real_play
        return summary, sounds

    clean, sounds = run([off, route[0], route[1], route[2], route[3], route[4]])
    check("track: clean climb is a send", clean["result"] == "sent" and clean["reached"] == 5, str(clean["result"]))
    check("track: a sound for every hold in order, top at the end",
          sounds == ["good"] * 4 + ["top"], str(sounds))
    check("track: an off-route hold before the start is ignored", clean["off_route"] == [])
    messy, sounds = run([route[0], route[1], off, route[2], route[4]])
    check("track: off-route and out-of-order holds give an alert",
          sounds == ["good", "good", "off", "good", "top"] and messy["off_route"] == [off]
          and messy["skipped"] == [route[3]], f"{sounds} off={messy['off_route']} skipped={messy['skipped']}")
    check("track: not clean, so only 'tried'", messy["result"] == "tried", messy["result"])
    run([route[0], route[1], route[2], route[3], route[4]], climber="Lena")
    cam = ascent.load_log("lena")["entries"][-1]
    check("track --climber logs the camera's guess, without raw touches",
          cam["by"] == "camera" and cam["result"] == "sent" and "touches" not in cam["attempt"], str(cam))

    # nothing counts while the wall is not locked
    real_locate = ascent.Tracker.locate
    ascent.Tracker.locate = lambda self, frame: (None, "lost")
    try:
        lost, sounds = run(route)
    finally:
        ascent.Tracker.locate = real_locate
    check("track: no lock, no touches counted", lost["reached"] == 0 and sounds == [])

    model = os.path.join(ROOT, ascent.POSE_MODEL_PATH)
    try:
        import mediapipe  # noqa: F401
        have_mp = True
    except ImportError:
        have_mp = False
    if have_mp and os.path.exists(model):
        det = ascent.PoseDetector(model)
        seen = det.hands(np.zeros((480, 640, 3), np.uint8), 0.0)
        det.close()
        check("track: real MediaPipe runs and sees no hands on an empty frame", seen == {})
    else:
        print("[SKIP] real MediaPipe check (mediapipe or models/pose_landmarker_lite.task not installed)")


def rehearse_log():
    """Logbook: log, show, undo, N people climbed this."""
    log = lambda **kw: ascent.cmd_log(SimpleNamespace(**{"wall": None, "route": None, "result": None, "date": None,
                                                         "note": None, "undo": False, **kw}))
    log(climber="Max", wall="tw", route="t1", result="sent", date=ascent.valid_date("2026-11-01"))
    log(climber="Lena", wall="tw", route="t1", result="tried", note="slipped off 4")
    log(climber="Jonas", wall="tw", route="t1", result="fail")
    log(climber="Lena")
    check("log: entries saved with a copy of the route", ascent.load_log("max")["entries"][0]["estimated_grade"]
          .startswith("~") and ascent.load_log("max")["entries"][0]["date"] == "2026-11-01 00:00")
    check("log: N people climbed this counts sends only, each person once",
          ascent.climbed_by("tw", 1, "t1") == ["lena", "max"], str(ascent.climbed_by("tw", 1, "t1")))
    log(climber="Jonas", undo=True)
    check("log: undo removes the last entry", ascent.load_log("jonas")["entries"] == [])
    try:
        log(climber="Lena", wall="tw", result="sent")
        refused = False
    except SystemExit:
        refused = True
    check("log: half a command is refused", refused)
    check("log: names become safe file names", ascent.climber_id("Lena M\u00fcller") == "lena_mueller")


def quiet(fn, *a, **kw):
    """Runs fn and returns what it printed."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **kw)
    return buf.getvalue()


def rehearse_progress():
    """Progress, milestones, levels without grade points, rule-based recommendations."""
    wall = json.load(open("walls/tw/wall.json"))
    kinds = ["jug", "jug", "crimp", "sloper", "jug", "pinch", "crimp", "pocket", "jug", "sloper"]
    for i, h in enumerate(wall["holds"]):
        h["type"] = kinds[i % len(kinds)]
    ascent.save_json("walls/tw/wall.json", wall)
    log = lambda c, r, res, d: ascent.cmd_log(SimpleNamespace(climber=c, wall="tw", route=r, result=res,
                                                              date=ascent.valid_date(d), note=None, undo=False))
    quiet(ascent.cmd_generate, SimpleNamespace(wall="tw", name="j1", moves=5, height=172, train="jug",
                                               level="easy", seed=3, preview=False, by="max"))
    check("generate --by records who set the route", ascent.load_route("tw", "j1").get("by") == "max")
    for d in ("2026-10-05", "2026-10-13", "2026-10-21", "2026-11-02"):
        quiet(log, "nora", "j1", "sent", d)
    out = quiet(ascent.cmd_progress, SimpleNamespace(climber="nora", goal=None))
    check("progress shows skills and milestones", "Skills" in out and "Regular: climbed in 4 different weeks" in out
          and "Route setter" not in out, out.splitlines()[0])
    check("route setter milestone when someone else sends your route",
          "Route setter: someone else sent your route" in ascent.badges("max", ascent.load_log("max")["entries"]))

    e = ascent.load_log("nora")["entries"]
    harder = [dict(x, estimated_grade="~7a") for x in e]
    check("play level: a harder grade earns no extra points",
          ascent.play_points("nora", e)[0] == ascent.play_points("nora", harder)[0])
    out = quiet(ascent.cmd_progress, SimpleNamespace(climber="nora", goal="play"))
    check("progress --goal play shows a level", "Level " in out and "never from grade" in out)

    rec = lambda c, **kw: ascent.recommendations(c, wall, ascent.climber_settings(
        SimpleNamespace(climber=c, height=None, level=None, goal=None, **kw)))
    reasons, train, level, existing = rec("nora")
    check("recommend: the skill she rarely climbs", train and train[0] not in ("jug",), f"{train} {reasons[0]}")
    for d in ("2026-11-03", "2026-11-04", "2026-11-05"):
        quiet(log, "nora", "j1", "fail", d)
    reasons, train, level, _ = rec("nora")
    check("recommend: easier after 3 fails", level == "easy" or "easier" in " ".join(reasons), level)

    os.makedirs("profiles", exist_ok=True)
    ascent.save_json("profiles/kid.json", {"name": "kid", "goal": "train", "level": "easy", "minor": True})
    ascent.save_json("profiles/pat.json", {"name": "pat", "goal": "rehab", "level": "medium",
                                           "rehab": {"level": "easy", "sessions_per_week": 2}})
    for d in ("2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"):
        quiet(log, "kid", "j1", "sent", d)
        quiet(log, "pat", "j1", "fail", d)
    _, _, level, _ = rec("kid")
    check("recommend: never suggests harder to a minor", level == "easy" and "try" not in " ".join(rec("kid")[0]))
    reasons, _, level, _ = rec("pat")
    check("recommend: rehab level stays the therapist's", level == "easy" and "therapist" in " ".join(reasons))
    out = quiet(ascent.cmd_progress, SimpleNamespace(climber="pat", goal=None))
    check("progress for rehab: sessions against the therapist's goal, no safety judgement",
          "therapist's goal: 2" in out and "does not judge" in out)
    before = set(ascent.route_names("tw"))
    quiet(ascent.cmd_recommend, SimpleNamespace(climber="nora", wall="tw", goal=None, height=165.0, level=None,
                                                make=2, moves=5))
    made = [ascent.load_route("tw", n) for n in set(ascent.route_names("tw")) - before]
    check("recommend --make generates routes set by the climber",
          len(made) == 2 and all(r.get("by") == "nora" and r["height_cm"] == 165.0 for r in made))


def rehearse_profile():
    """Profiles: sign-up details, stricter rules for minors and health data, delete one person."""
    base = dict(climber=None, goal=None, level=None, height=None, language=None, visibility=None, minor=False,
                adult=False, parental_consent=False, therapist=None, rehab_level=None, sessions_per_week=None,
                delete=False, yes=False)
    prof = lambda **kw: quiet(ascent.cmd_profile, SimpleNamespace(**{**base, **kw}))

    def refused(**kw):
        try:
            prof(**kw)
            return False
        except SystemExit:
            return True

    prof(climber="Lena", goal="train", level="medium", height=165.0, language="de")
    lena = ascent.load_profile("lena")
    check("profile: sign-up details saved, private by default",
          lena["height_cm"] == 165.0 and lena["language"] == "de" and lena["visibility"] == "private")
    st = ascent.climber_settings(SimpleNamespace(climber="lena", height=None, level=None, goal=None))
    check("profile: height and level feed the recommendations", st["height"] == 165.0 and st["level"] == "medium")
    prof(climber="lena", level="hard")
    check("profile: updating one field keeps the others", ascent.load_profile("lena")["height_cm"] == 165.0
          and ascent.load_profile("lena")["level"] == "hard")
    check("profile: a minor can't be public", refused(climber="max", goal="play", minor=True, visibility="public")
          and ascent.load_profile("max") is None)
    check("profile: a minor needs parental consent for friends",
          refused(climber="max", goal="play", minor=True, visibility="friends"))
    prof(climber="max", goal="play", minor=True, visibility="friends", parental_consent=True, height=150.0)
    check("profile: ... and with consent it works", ascent.load_profile("max")["visibility"] == "friends")
    check("profile: rehab settings need goal rehab", refused(climber="lena", rehab_level="easy"))
    prof(climber="laura", goal="rehab", therapist="Dr. Berger", rehab_level="easy", sessions_per_week=2)
    out = prof(climber="laura")
    check("profile: rehab settings shown as health data", "health data - always private" in out
          and "Updated" not in out, out)
    prof(climber="laura", goal="train")
    check("profile: rehab data removed when the goal changes", "rehab" not in ascent.load_profile("laura"))
    check("profile: unknown climber without details is refused", refused(climber="nobody"))

    prof(climber="max", delete=True)
    check("profile: --delete without --yes only shows what would go", ascent.load_profile("max") is not None)
    prof(climber="max", delete=True, yes=True)
    j1 = ascent.load_route("tw", "j1")
    check("profile: --delete --yes removes profile and logbook, routes stay anonymous",
          ascent.load_profile("max") is None and not os.path.exists("logbook/max.json") and "by" not in j1)


def rehearse_routes():
    """Safety card once per climber and wall; the route list with filters."""
    base = dict(wall="tw", train="", grade=None, holds=None, made_by=None, by=None, climber=None, new=False,
                within_reach=False, height=None, level=None, goal=None)
    rows = lambda **kw: ascent.filter_routes(ascent.load_wall("tw")[0], SimpleNamespace(**{**base, **kw}),
                                             kw.get("climber"), kw.get("height"))
    names = lambda **kw: sorted(r["name"] for r, *_ in rows(**kw))
    every = names()
    check("routes: no filter lists every route on this version", len(every) == len(ascent.route_names("tw")))
    jug = names(train="jug")
    check("routes: --train keeps routes with that skill", "j1" in jug and all(
        "jug" in sk for *_, sk in rows(train="jug")))
    g = ascent.grade_range("5a-6a")
    check("routes: --grade range", all(5 >= ascent.GRADES.index(r["estimated_grade"][1:]) >= 1
                                       for r, *_ in rows(grade=g)) and g == (1, 4))
    check("routes: --made-by built", names(made_by="built") == ["t1"])
    check("routes: --by", names(by="nora") and all(r.get("by") == "nora" for r, *_ in rows(by="nora")))
    check("routes: --new hides what the climber has sent", "t1" in every and "t1" not in names(climber="lena",
                                                                                                 new=True))
    tall, short = names(within_reach=True, height=230.0), names(within_reach=True, height=60.0)
    check("routes: --within-reach depends on height", len(short) < len(tall), f"{len(short)} vs {len(tall)} of {every}")
    r, people, me, _ = [x for x in rows(climber="lena") if x[0]["name"] == "t1"][0]
    check("routes: N climbed and your result", "lena" in people and me == "sent",
          f"{people} {me}")
    out = quiet(ascent.cmd_routes, SimpleNamespace(**{**base, "climber": "lena"}))
    again = quiet(ascent.cmd_routes, SimpleNamespace(**{**base, "climber": "lena"}))
    check("safety card the first time a climber opens a wall, in their language",
          "SICHERHEIT" in out and "SICHERHEIT" not in again and "climbed" in again)
    out = quiet(ascent.cmd_safety, SimpleNamespace(climber=None, language=None))
    check("safety card is ASCII and short", out.isascii() and len(out.splitlines()) <= 12)
    try:
        ascent.grade_range("9z")
        bad = False
    except ascent.argparse.ArgumentTypeError:
        bad = True
    check("routes: a wrong grade is refused", bad)


def rehearse_challenges():
    """Challenges: invite, done on a send or a real try, no deadline, minors protected, both win."""
    base = dict(climber=None, to=None, wall=None, route=None, message=None, decline=None)
    ch = lambda **kw: quiet(ascent.cmd_challenge, SimpleNamespace(**{**base, **kw}))
    log = lambda c, r, res: quiet(ascent.cmd_log, SimpleNamespace(climber=c, wall="tw", route=r, result=res,
                                                                  date=None, note=None, undo=False))

    def refused(**kw):
        try:
            ch(**kw)
            return False
        except SystemExit:
            return True

    out = ch(climber="nora", to="Lena", wall="tw", route="j1", message="your turn")
    check("challenge: created", os.path.exists("challenges/c1.json") and "No deadline" in out)
    check("challenge: not to yourself", refused(climber="nora", to="nora", wall="tw", route="j1"))
    quiet(ascent.cmd_profile, SimpleNamespace(climber="kid", goal="play", level=None, height=90.0, language=None,
                                              visibility=None, minor=True, adult=False, parental_consent=False,
                                              therapist=None, rehab_level=None, sessions_per_week=None,
                                              delete=False, yes=False))
    check("challenge: a minor can't get a route past their reach", refused(climber="nora", to="kid", wall="tw",
                                                                            route="t1"))
    log("lena", "j1", "fail")
    check("challenge: a fail doesn't finish it", not ascent.finished_challenges("lena"))
    before = ascent.play_points("lena", ascent.load_log("lena")["entries"])[0]
    out = log("lena", "j1", "tried")
    check("challenge: a real try finishes it, both win", "Challenge c1 done" in out
          and ascent.finished_challenges("nora") and "Team player: finished a challenge"
          in ascent.badges("nora", ascent.load_log("nora")["entries"]))
    check("challenge: worth points for play",
          ascent.play_points("lena", ascent.load_log("lena")["entries"])[0] > before)
    ch(climber="nora", to="lena", wall="tw", route="r1")
    out = ch(climber="lena", decline="c2")
    check("challenge: declining costs nothing", "No penalty" in out
          and json.load(open("challenges/c2.json")).get("declined"))
    check("challenge: only the person challenged can decline", refused(climber="nora", decline="c2"))
    out = ch(climber="lena")
    check("challenge: list shows done and declined", "done" in out and "declined" in out, out)
    quiet(ascent.cmd_profile, SimpleNamespace(climber="nora", goal=None, level=None, height=None, language=None,
                                              visibility=None, minor=False, adult=False, parental_consent=False,
                                              therapist=None, rehab_level=None, sessions_per_week=None,
                                              delete=True, yes=True))
    check("challenge: deleting a person deletes their challenges", ascent.all_challenges() == [])


class Phone:
    """A headless phone: talks to the local server over HTTPS, checking the self-signed certificate."""

    def __init__(self, port, code, cafile):
        import http.client
        import ssl
        self.port, self.code, self.http = port, code, http.client
        self.ctx = ssl.create_default_context(cafile=cafile) if cafile else None

    def request(self, method, path, body=None, ctype="application/json", code=True):
        if code:
            path += ("&" if "?" in path else "?") + "code=" + self.code
        if self.ctx:
            c = self.http.HTTPSConnection("localhost", self.port, context=self.ctx, timeout=30)
        else:
            c = self.http.HTTPConnection("localhost", self.port, timeout=30)
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        c.request(method, path, body=body, headers={"Content-Type": ctype} if body is not None else {})
        r = c.getresponse()
        data = r.read()
        c.close()
        try:
            data = json.loads(data)
        except ValueError:
            pass
        return r.status, data, r

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body if body is not None else {}, **kw)

    def frame(self, sid, img, extra=""):
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return self.post(f"/api/frame?sid={sid}{extra}", jpg.tobytes(), ctype="image/jpeg")


def start_server():
    import threading
    try:
        import cryptography  # noqa: F401
        cert, key = ascent.ensure_certificate(["127.0.0.1"])
    except (ImportError, SystemExit):
        print("[SKIP] HTTPS (cryptography not installed) - testing the same server over plain HTTP")
        cert = key = None
    httpd = ascent.make_server("127.0.0.1", 0, "k3y5ab", cert, key)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, Phone(httpd.server_address[1], "k3y5ab", cert), cert


def phone_view(photo, H, side=800):
    """What the phone sends: the camera view, downscaled so the long side is 800 px. Returns frame, H_frame."""
    view = cv2.warpPerspective(photo, H, (1280, 720), borderValue=(30, 30, 30))
    f = side / 1280
    return cv2.resize(view, (side, int(720 * f)), interpolation=cv2.INTER_AREA), np.diag([f, f, 1.0]) @ H


def rehearse_serve_live(photo):
    """serve + /live: access code, pages, wall list, frames from a moving phone, route buttons."""
    httpd, phone, cert = start_server()
    try:
        st, body, _ = phone.request("GET", "/live", code=False)
        check("serve: no code, no page", st == 403)
        st, body, r = phone.request("GET", "/")
        st2, old, _ = phone.request("GET", "/live")
        check("serve: the code opens the one page (four tabs) and sets a cookie", st == 200
              and all(b'data-tab="%s"' % t in body for t in (b"climb", b"live", b"scan", b"track")) and old == body
              and all(f"web/{f}.js".encode() in body for f in ("common", "live", "scan", "track"))
              and "ascent_code=k3y5ab" in (r.getheader("Set-Cookie") or ""))
        st, _, _ = phone.post("/api/log", {"message": "test error \u00e4", "page": "#scan"})
        st2, _, _ = phone.post("/api/log", {"message": "x"}, code=False)
        check("serve: phone errors are printed on the laptop (code needed)", st == 200 and st2 == 403)
        st, _, _ = phone.request("GET", "/api/walls", code=False)
        check("serve: no code, no data", st == 403)
        st, js, _ = phone.request("GET", "/web/common.js", code=False)
        st2, _, _ = phone.request("GET", "/web/../ascent.py", code=False)
        st3, _, _ = phone.request("GET", "/web/..%2Fascent.py")
        check("serve: scripts load; nothing outside web/", st == 200 and st2 in (403, 404) and st3 == 404,
              f"{st} {st2} {st3}")
        if cert:
            check("serve: HTTPS with the self-signed certificate (checked against it)", True)
        st, walls, _ = phone.request("GET", "/api/walls")
        tw = [w for w in walls["walls"] if w["name"] == "tw"]
        check("serve: wall list with routes", st == 200 and tw and any(r["name"] == "t1" for r in tw[0]["routes"]))

        st, info, _ = phone.post("/api/live/start", {"wall": "tw", "route": "t1", "train": "jug", "moves": 5})
        check("serve: start a live session", st == 200 and info.get("route") == "t1" and info.get("sid"), str(info))
        sid = info["sid"]
        wall = json.load(open("walls/tw/wall.json"))
        px = {h["id"]: h["px"] for h in wall["holds"]}
        route_px = [px[i] for i in ascent.load_route("tw", "t1")["holds"]]
        errs, states = [], []
        for H in camera_path(36)[:12]:
            img, Hf = phone_view(photo, H)
            st, a, _ = phone.frame(sid, img)
            states.append(a.get("state"))
            if a.get("state") == "locked":
                got = np.array([[r["x"], r["y"]] for r in a["rings"]])
                c = ascent.transform(Hf, wall["corners_px"][:2])
                cm_per_px = wall["size_cm"]["w"] / np.linalg.norm(c[1] - c[0])
                errs.append(np.linalg.norm(got - ascent.transform(Hf, route_px), axis=1).max() * cm_per_px)
        check("serve: phone frames lock", states.count("locked") >= 11, str(states))
        check("serve: rings land on the holds (first frame, no smoothing)", errs and errs[0] < 0.5,
              f"{errs[0]:.2f} cm" if errs else "no lock")
        check("serve: ... and within 3 cm on a moving phone, smoothing included", errs and max(errs) < 3,
              f"worst {max(errs):.1f} cm" if errs else "no lock")
        check("serve: numbered start / middle / finish", a["rings"][0]["kind"] == "start" and
              a["rings"][-1]["kind"] == "finish" and [r["n"] for r in a["rings"]] == list(range(1, 6)))
        st, a, _ = phone.frame(sid, np.full((450, 800, 3), 30, np.uint8))
        check("serve: no wall in view - no rings, a message instead", st == 200 and a["state"] != "locked"
              and "rings" not in a and a.get("message"), str(a))
        far, _ = phone_view(photo, np.diag([0.08, 0.08, 1.0]))
        st, a, _ = phone.frame(sid, far)
        check("serve: far away - no rings", "rings" not in a, str(a.get("state")))

        before = set(ascent.route_names("tw"))
        st, info, _ = phone.post(f"/api/route/new?sid={sid}")
        made = set(ascent.route_names("tw")) - before
        check("serve: New route button generates and switches", st == 200 and made == {info["route"]}, str(info))
        st, info2, _ = phone.post(f"/api/route/next?sid={sid}")
        check("serve: Next route button", st == 200 and info2["route"] != info["route"])

        st, e1, _ = phone.post("/api/live/start", {"wall": "../walls"})
        st2, e2, _ = phone.post("/api/live/start", {"wall": "nowall"})
        st3, e3, _ = phone.frame("nosuchsession", far)
        st4, e4, _ = phone.post(f"/api/frame?sid={sid}", b"not a jpeg", ctype="image/jpeg")
        check("serve: bad requests get a message, the server stays up", (st, st2, st3, st4) == (400,) * 4
              and "No wall called" in e2["error"] and "reload" in e3["error"], f"{st} {st2} {st3} {st4}")
        if cert:
            import socket
            idle = socket.create_connection(("127.0.0.1", phone.port))       # connects, never says hello
            st, _, _ = phone.request("GET", "/api/walls")
            idle.close()
            check("serve: a silent connection doesn't block other phones", st == 200)
            m = os.path.getmtime(cert)
            ascent.ensure_certificate(["127.0.0.1"])
            same = os.path.getmtime(cert) == m
            ascent.ensure_certificate(["127.0.0.1", "192.168.1.50"])
            check("serve: certificate kept, and remade for a new laptop IP",
                  same and "192.168.1.50" in json.load(open("tls/ips.json")))
    finally:
        httpd.shutdown()
        httpd.server_close()


def rehearse_serve_scan(photo, holds, corners, mphoto):
    """/scan: the phone's photo, corners, size and holds become the same wall.json and ref.jpg, with versions."""
    import base64
    httpd, phone, _ = start_server()
    b64 = lambda img: "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", img)[1]).decode()
    try:
        types = ["jug", None, "sloper", "crimp", None, "pinch"]
        req = {"wall": "phonewall", "image": b64(photo), "corners": [list(map(float, c)) for c in corners[[2, 0, 3, 1]]],
               "width": 300, "height": None, "holds": [{"px": list(map(float, h)), "type": types[i % 6]}
                                                       for i, h in enumerate(holds)]}
        st, r, _ = phone.post("/api/scan", req)
        wall = json.load(open("walls/phonewall/wall.json"))
        check("scan page: saves wall.json and ref.jpg", st == 200 and r["version"] == 1 and
              os.path.exists("walls/phonewall/ref.jpg") and len(wall["holds"]) == len(holds), str(r))
        check("scan page: corners in any order, height from the photo",
              np.allclose(wall["corners_px"][0], corners[0], atol=1) and abs(wall["size_cm"]["h"] - 300 * 590 / 820) < 2
              and not wall["size_cm"]["assumed"], str(wall["size_cm"]))
        R = ascent.rectify_matrix(np.array(wall["corners_px"], np.float32), 300, wall["size_cm"]["h"])
        cm = ascent.transform(R, holds)
        check("scan page: hold centimetres and types as the CLI computes them",
              np.allclose([h["cm"] for h in wall["holds"]], cm, atol=0.2)
              and [h["type"] for h in wall["holds"]] == [types[i % 6] for i in range(len(holds))])
        ascent.save_route(wall, [1, 2, 3], "p1", "built", 172)
        st, r, _ = phone.post("/api/scan", {**req, "width": None, "holds": req["holds"][:5]})
        v2 = json.load(open("walls/phonewall/wall.json"))
        check("scan page: re-scan is version 2, version 1 and its routes archived",
              r["version"] == 2 and os.path.exists("walls/phonewall/archive_v1/routes/p1.json")
              and v2["size_cm"]["assumed"] and v2["size_cm"]["w"] == 300.0, str(r))

        st, m, _ = phone.post("/api/scan/markers", {"image": b64(mphoto)})
        st2, m2, _ = phone.post("/api/scan/markers", {"image": b64(photo)})
        check("scan page: markers found on the photo, or how many", m["found"] == 4 and m["corners"]
              and m2["found"] == 0 and m2["corners"] is None)
        st, r, _ = phone.post("/api/scan", {"wall": "phonemarkers", "image": b64(mphoto), "markers": True,
                                            "width": 300, "height": 220, "holds": [{"px": [640, 360]}]})
        mw = json.load(open("walls/phonemarkers/wall.json"))
        check("scan page: markers mode", st == 200 and mw["mode"] == "markers" and len(mw["markers_px"]) == 4)

        bad = [
            {**req, "corners": req["corners"][:3]},
            {**req, "holds": [{"px": [10, 10], "type": "foothold"}]},
            {**req, "holds": []},
            {**req, "wall": "../evil"},
            {**req, "holds": [{"px": [99999, 10]}]},
            {**req, "width": -5},
            {**req, "corners": [[10, 10], [11, 10], [11, 11], [10, 11]]},
            {**req, "image": "bm90IGEgcGhvdG8="},
            {"wall": "phonemarkers", "image": b64(photo), "markers": True, "holds": [{"px": [1, 1]}]},
        ]
        codes = [phone.post("/api/scan", b)[0] for b in bad]
        check("scan page: bad scans are refused and nothing is saved", codes == [400] * len(bad)
              and json.load(open("walls/phonewall/wall.json"))["version"] == 2
              and not os.path.exists("walls/evil"), str(codes))
        st, js, _ = phone.request("GET", "/web/scan.js", code=False)
        check("scan page: scan.js loads, with the in-page camera", st == 200 and b"/api/scan" in js
              and b"startCamera" in js)
    finally:
        httpd.shutdown()
        httpd.server_close()


def rehearse_serve_track(photo):
    """/track: the phone's frames, a scripted hand, sounds back to the phone, the result into the logbook."""
    class FakePose:
        pos = None
        closed = False

        def hands(self, frame, t):
            return {"right": FakePose.pos} if FakePose.pos is not None else {}

        def close(self):
            FakePose.closed = True

    real = ascent.make_pose_detector
    ascent.make_pose_detector = lambda path=None: FakePose()
    httpd, phone, _ = start_server()
    try:
        wall = json.load(open("walls/tw/wall.json"))
        px = {h["id"]: h["px"] for h in wall["holds"]}
        route = ascent.load_route("tw", "t1")["holds"]
        off = [i for i in px if i not in route and all(np.linalg.norm(np.subtract(px[i], px[j])) > 60 for j in route)][0]
        quiet(ascent.cmd_profile, SimpleNamespace(climber="tess", goal="train", level=None, height=170.0,
                                                  language="de", visibility=None, minor=False, adult=False,
                                                  parental_consent=False, therapist=None, rehab_level=None,
                                                  sessions_per_week=None, delete=False, yes=False))
        st, info, _ = phone.post("/api/track/start", {"wall": "tw", "route": "t1", "climber": "Tess"})
        check("track page: start, with the safety card the first time", st == 200 and info["safety"]
              and info["safety"][0].startswith("SICHERHEIT"), str(info.get("safety"))[:60])
        st, info2, _ = phone.post("/api/track/start", {"wall": "tw", "route": "t1", "climber": "tess"})
        check("track page: ... and not the second time", info2["safety"] is None)
        sid = info2["sid"]
        Hs = camera_path(60)
        events, states, hands_seen, t = [], [], [], 0.0

        def send(i, hold):
            nonlocal t
            img, Hf = phone_view(photo, Hs[i])
            FakePose.pos = tuple(ascent.transform(Hf, [px[hold]])[0] + [2, -1]) if hold else None
            st, a, _ = phone.frame(sid, img, f"&t={t:.3f}")
            t += 1 / 8
            states.append(a.get("state"))
            events.extend(e["sound"] for e in a.get("events", []))
            if a.get("hands"):
                hands_seen.append(a["hands"])
            return a

        script = [off] * 4 + [h for h in route[:2] for _ in range(5)] + [off] * 5 + \
                 [h for h in route[2:] for _ in range(5)]
        for i, hold in enumerate(script):
            a = send(i, hold)
        check("track page: sounds for each hold, off-route alert, top", events == ["good", "good", "off", "good",
                                                                                  "good", "top"], str(events))
        check("track page: hand positions come back to draw", len(hands_seen) >= len(script) - 2
              and a["next"] == a["of"] == len(route))
        st, a, _ = phone.frame(sid, np.full((450, 800, 3), 30, np.uint8), f"&t={t + 1:.3f}")
        check("track page: no lock - no rings, no hands, no events", "rings" not in a and "hands" not in a
              and a["events"] == [])
        st, res, _ = phone.post(f"/api/track/finish?sid={sid}")
        e = ascent.load_log("tess")["entries"][-1]
        check("track page: Finish gives the camera's guess and saves it in the logbook",
              res["result"] == "tried" and res["off_route"] == [off] and res["logged"]
              and e["by"] == "camera" and e["result"] == "tried" and e["route"] == "t1", str(res))
        events.clear()
        for i, hold in enumerate([h for h in route for _ in range(5)]):
            send(i, hold)
        st, res, _ = phone.post(f"/api/track/finish?sid={sid}")
        check("track page: after Finish, a clean try is a send", res["result"] == "sent"
              and events == ["good"] * (len(route) - 1) + ["top"], f"{res['result']} {events}")
        st, _, _ = phone.post(f"/api/track/reset?sid={sid}")
        check("track page: Try again", st == 200)

        st, r1, _ = phone.post("/api/track/start", {"wall": "tw"})
        ascent.make_pose_detector = lambda path=None: ascent.sys.exit("track needs MediaPipe: pip install mediapipe")
        st2, r2, _ = phone.post("/api/track/start", {"wall": "tw", "route": "t1"})
        st3, r3, _ = phone.post("/api/live/start", {"wall": "tw", "route": "t1"})
        st4, r4, _ = phone.post(f"/api/track/finish?sid={r3['sid']}")
        check("track page: no route, no MediaPipe, or a live session: a clear message, server stays up",
              (st, st2, st3, st4) == (400, 400, 200, 400) and "MediaPipe" in r2["error"], f"{st} {st2} {st3} {st4}")
        st, js, _ = phone.request("GET", "/web/track.js", code=False)
        check("track page: track.js loads", st == 200 and b"AudioContext" in js)
        for _ in range(9):
            ascent.make_pose_detector = lambda path=None: FakePose()
            phone.post("/api/track/start", {"wall": "tw", "route": "t1"})
        check("track page: old sessions are closed (MediaPipe released)", FakePose.closed
              and len(httpd.sessions) <= 8)
    finally:
        ascent.make_pose_detector = real
        httpd.shutdown()
        httpd.server_close()


def rehearse_serve_flow(photo, mphoto, holds, corners):
    """The phone's one-link flow: photo -> corners and holds found by the laptop -> route by skill, previewed
    then saved -> sticker tracking with sounds, colour taught by a tap. Nothing typed, nothing measured."""
    import base64
    b64 = lambda img: "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", img)[1]).decode()

    def score(det, truth):
        P, T = np.array([d["px"] for d in det]), np.array(truth, float)
        d = np.linalg.norm(T[:, None] - P[None], axis=2)
        return int((d.min(axis=1) < 10).sum()), int((d.min(axis=0) >= 10).sum())

    # the board outline, found without markers or taps
    q = ascent.detect_board(photo)
    xx = np.mgrid[0:720, 0:1280][1]
    lit = np.clip(photo * (0.45 + 0.75 * xx / 1280)[..., None], 0, 255).astype(np.uint8)
    H = np.array([[0.9, -0.1, 80], [0.08, 0.95, 20], [0.00005, 0.00004, 1]])
    warped = cv2.warpPerspective(photo, H, (1280, 720), borderValue=(30, 30, 30))
    qw = ascent.detect_board(warped)
    ql = ascent.detect_board(lit)
    check("board outline: found within 2 px, also in uneven light and at an angle",
          q is not None and np.linalg.norm(q - corners, axis=1).max() < 2 and ql is not None
          and np.linalg.norm(ql - corners, axis=1).max() < 2 and qw is not None
          and np.linalg.norm(qw - ascent.transform(H, corners), axis=1).max() < 2,
          "" if q is None else str(np.round(np.linalg.norm(q - corners, axis=1), 1)))
    noise = np.random.default_rng(1).integers(0, 255, (720, 1280, 3), dtype=np.uint8)
    check("board outline: never guesses - a cut-off board, a blank or noisy picture give nothing",
          ascent.detect_board(photo[100:, :]) is None and ascent.detect_board(np.full((720, 1280, 3), 30, np.uint8))
          is None and ascent.detect_board(noise) is None)

    httpd, phone, _ = start_server()
    try:
        st, a, _ = phone.post("/api/scan/auto", {"image": b64(mphoto)})
        mh = make_wall_photo(seed=9, markers=True)[1]
        f, x = score(a["holds"], mh) if a.get("holds") else (0, 99)
        check("flow: markers in the photo give the corners, holds found", st == 200 and a["how"] == "markers"
              and a["markers_found"] == 4 and f >= 25 and x <= 1, f"{a.get('how')} {f} found {x} false")
        st, a, _ = phone.post("/api/scan/auto", {"image": b64(photo)})
        f, x = score(a["holds"], holds) if a.get("holds") else (0, 99)
        check("flow: no markers - the board outline gives the corners, holds found", st == 200
              and a["how"] == "outline" and np.allclose(a["corners"], corners, atol=2) and f >= 25 and x <= 1,
              f"{a.get('how')} {f} found {x} false")
        st, a, _ = phone.post("/api/scan/auto", {"image": b64(photo[100:, :])})
        check("flow: no markers, no outline - the phone is asked for 4 taps, no holds guessed", st == 200
              and a["how"] is None and a["corners"] is None and a["holds"] == [] and "Tap" in a["message"])
        st, a, _ = phone.post("/api/scan/auto", {"image": b64(photo),
                                                 "corners": [list(map(float, c)) for c in corners[[2, 0, 3, 1]]]})
        f, x = score(a["holds"], holds) if a.get("holds") else (0, 99)
        check("flow: ... and with the taps (any order), holds are found", st == 200 and a.get("how") == "taps"
              and f >= 25 and x <= 1, f"{st} {a.get('how', a)} {f} found {x} false")
        st, bad, _ = phone.post("/api/scan/auto", {"image": b64(photo[100:, :]), "corners": [[1, 1], [2, 2]]})
        check("flow: bad taps are refused", st == 400)

        # saving without a size: 300 cm assumed, colours kept
        st, a, _ = phone.post("/api/scan/auto", {"image": b64(photo)})
        st, r, _ = phone.post("/api/scan", {"wall": "flow", "image": b64(photo), "corners": a["corners"],
                                            "width": None, "height": None, "holds": a["holds"]})
        wall = json.load(open("walls/flow/wall.json"))
        check("flow: saved with an assumed size, hold colours kept", st == 200 and wall["size_cm"]["assumed"]
              and sum(1 for h in wall["holds"] if h.get("colour")) == len(wall["holds"]), str(r))
        st, jpg, r2 = phone.request("GET", "/api/wall/photo?wall=flow")
        st2, _, _ = phone.request("GET", "/api/wall/photo?wall=nope")
        st3, _, _ = phone.request("GET", "/api/wall/photo?wall=../x")
        check("flow: the wall's photo can be fetched (with the code), nothing else", st == 200
              and r2.getheader("Content-Type") == "image/jpeg" and len(jpg) > 1000 and st2 == 404 and st3 == 400)

        # routes by skill: reach scaled to the wall, previewed, then saved
        made = {}
        for skill in ("reach", "traverse", "easy", "hard"):
            st, made[skill], _ = phone.post("/api/route/make", {"wall": "flow", "skill": skill, "seed": 3})
        ok = all(st == 200 and 4 <= len(m["holds"]) <= 5 and len(m["holds_px"]) == len(m["holds"])
                 and m["grade"].startswith("~") and not any("past" in w for w in m["warnings"])
                 for m in made.values())
        check("flow: a route for each skill, within a reach scaled to the wall, grade with ~", ok
              and made["reach"]["train"] == ["reach"] and made["hard"]["level"] == "hard"
              and made["reach"]["height"] == 165.0, str({k: len(v.get("holds", [])) for k, v in made.items()}))
        cm = {h["id"]: h["cm"] for h in wall["holds"]}
        trav = made["traverse"]["holds"]
        check("flow: traverse goes sideways", abs(cm[trav[-1]][0] - cm[trav[0]][0]) >= 0.4 * 300)
        st, again, _ = phone.post("/api/route/make", {"wall": "flow", "skill": "reach", "seed": 4})
        check("flow: 'Another one' gives a different route, nothing saved yet",
              again["holds"] != made["reach"]["holds"] and ascent.route_names("flow") == [])
        st, saved, _ = phone.post("/api/route/save", {"wall": "flow", "holds": again["holds"], "skill": "reach"})
        rt = ascent.load_route("flow", "r1")
        check("flow: 'Use this route' saves it as r1 with its skill", st == 200 and saved["route"] == "r1"
              and rt["holds"] == again["holds"] and rt["train"] == ["reach"] and rt["height_cm"] == 165.0)
        st, _, _ = phone.post("/api/route/save", {"wall": "flow", "holds": [1, 1]})
        st2, _, _ = phone.post("/api/route/make", {"wall": "flow", "skill": "flying"})
        check("flow: bad routes and skills are refused", st == 400 and st2 == 400)

        # climbing with a sticker on the fingertip: frames from the phone, sounds back, colour by a tap
        px = {h["id"]: h["px"] for h in wall["holds"]}
        route = rt["holds"]
        off = [i for i in px if i not in route and all(np.linalg.norm(np.subtract(px[i], px[j])) > 60 for j in route)][0]
        st, info, _ = phone.post("/api/track/start", {"wall": "flow", "route": "r1", "touch": "sticker",
                                                      "sticker": "green"})
        check("flow: sticker tracking starts without MediaPipe", st == 200 and info["touch"] == "sticker", str(info))
        sid = info["sid"]
        Hs = camera_path(80)
        events, t, names = [], 0.0, []

        def send(i, hold, colour=(60, 230, 60), extra=""):
            nonlocal t
            img, Hf = phone_view(photo, Hs[i])
            if hold:
                x, y = ascent.transform(Hf, [px[hold]])[0]
                cv2.circle(img, (int(x) + 3, int(y) - 4), 5, colour, -1, cv2.LINE_AA)
            st, a, _ = phone.frame(sid, img, f"&t={t:.3f}" + extra)
            t += 1 / 8
            events.extend(e["sound"] for e in a.get("events", []))
            names.append(a.get("sticker"))
            return a, (x, y) if hold else None

        script = [None] * 2 + [h for h in route[:2] for _ in range(6)] + [off] * 6 + \
                 [h for h in route[2:] for _ in range(6)]
        for i, hold in enumerate(script):
            a, _ = send(i, hold)
        check("flow: sticker touches give the right sounds - good, off-route, top", events ==
              ["good"] * 2 + ["off"] + ["good"] * (len(route) - 3) + ["top"], str(events))
        st, res, _ = phone.post(f"/api/track/finish?sid={sid}")
        check("flow: the result is a 'tried' with the off-route hold", res["result"] == "tried"
              and res["off_route"] == [off], str(res))
        # a pink sticker is invisible to a green detector until the person taps it once
        events.clear()
        for i, hold in enumerate([route[0]] * 6):
            a, pos = send(i, hold, colour=(180, 60, 230))
        check("flow: a sticker of another colour is not seen", events == [] and a["sticker"] == "green")
        a, pos = send(7, route[0], colour=(180, 60, 230), extra=f"&tapx={pos[0]:.0f}&tapy={pos[1]:.0f}")
        check("flow: one tap on the sticker teaches its colour", a.get("learned") is True
              and a["sticker"].startswith("clicked"), str(a.get("sticker")))
        for i, hold in enumerate([route[0]] * 6, start=8):
            send(i, hold, colour=(180, 60, 230))
        check("flow: ... and then it counts", events == ["good"], str(events))
        a, _ = send(20, None, extra="&tapx=5&tapy=5")
        check("flow: a tap on plain wall teaches nothing", a.get("learned") is False)
        st, _, _ = phone.post("/api/track/start", {"wall": "flow", "route": "r1", "touch": "sticker",
                                                   "sticker": "neon"})
        check("flow: an unknown sticker colour is refused", st == 400)
        st, js, _ = phone.request("GET", "/web/flow.js", code=False)
        st2, page, _ = phone.request("GET", "/")
        check("flow: the Climb tab is on the one page", st == 200 and b"/api/scan/auto" in js
              and b"/api/route/make" in js and b'data-tab="climb"' in page and b"web/flow.js" in page)
    finally:
        httpd.shutdown()
        httpd.server_close()


def rehearse_sticker(photo, mphoto, holds, corners):
    """track with coloured stickers instead of MediaPipe: touches, sounds, two stickers, same-colour holds,
    markers mode, colour by click, nothing without a lock."""
    def video(img, wall_name, frames_script, path, sticker_bgr=(60, 230, 60)):
        wall = json.load(open(f"walls/{wall_name}/wall.json"))
        px = {h["id"]: h["px"] for h in wall["holds"]}
        Hs = camera_path(10 * len(frames_script) + 4)
        w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 15, (1280, 720))
        for i, H in enumerate(Hs):
            f = cv2.warpPerspective(img, H, (1280, 720), borderValue=(30, 30, 30))
            k = i // 10
            for hold in (frames_script[k] if k < len(frames_script) else ()):
                x, y = ascent.transform(H, [px[hold]])[0]
                cv2.circle(f, (int(x) + 3, int(y) - 4), 6, sticker_bgr, -1, cv2.LINE_AA)   # the sticker
            w.write(f)
        w.release()

    def run(wall_name, route_name, path, **kw):
        sounds = []
        real = ascent.play_sound
        ascent.play_sound = sounds.append
        try:
            args = dict(wall=wall_name, route=route_name, camera=0, video=path, features="sift", touch_cm=None,
                        pose_model=None, mute=False, climber=None, touch="sticker", sticker="green", dwell=0.5)
            args.update(kw)
            with contextlib.redirect_stdout(io.StringIO()):
                s = ascent.run_track(SimpleNamespace(**args))
        finally:
            ascent.play_sound = real
        return s, sounds

    wall = json.load(open("walls/tw/wall.json"))
    route = ascent.load_route("tw", "t1")["holds"]
    px = {h["id"]: h["px"] for h in wall["holds"]}
    off = [i for i in px if i not in route and all(np.linalg.norm(np.subtract(px[i], px[j])) > 60 for j in route)][0]
    check("sticker: touch distance comes from the hold spacing", 2 <= ascent.auto_touch_cm(wall) <= 12,
          f"{ascent.auto_touch_cm(wall):.1f} cm")
    gui = FakeGUI()
    gui.install()
    gui.strict = False

    video(photo, "tw", [(), (route[0],), (route[1],), (off,), (route[2],), (route[3],), (route[4],)], "st1.avi")
    s, sounds = run("tw", "t1", "st1.avi")
    check("sticker: positive sound for each hold in order, negative for an off-route hold",
          sounds == ["good", "good", "off", "good", "good", "top"] and s["off_route"] == [off], str(sounds))
    # two stickers: one stays on the start hold, the other climbs
    video(photo, "tw", [(route[0], route[1])] + [(route[0], h) for h in route[1:]], "st2.avi")
    s, sounds = run("tw", "t1", "st2.avi")
    check("sticker: two stickers at once (one stays on the start)", s["result"] == "sent"
          and sounds == ["good"] * 4 + ["top"], f"{s['result']} {sounds}")
    # nothing without a lock
    real_locate = ascent.Tracker.locate
    ascent.Tracker.locate = lambda self, frame: (None, "lost")
    try:
        s, sounds = run("tw", "t1", "st1.avi")
    finally:
        ascent.Tracker.locate = real_locate
    check("sticker: no lock, no touches, no sounds", s["reached"] == 0 and sounds == [])
    # a sticker of a colour that some holds have: those holds are ignored, the sticker still counts
    video(photo, "tw", [()] * 3, "st3.avi")
    s, sounds = run("tw", "t1", "st3.avi", sticker="orange")
    check("sticker: holds of the sticker's colour are not stickers", sounds == [] and s["reached"] == 0, str(sounds))
    # in make_wall_photo every 5th hold (i % 5 == 4) is orange; ids follow the click order (id = i + 1)
    plain = [h for h in sorted(px, key=lambda i: -px[i][1]) if (h - 1) % 5 != 4]
    ascent.save_route(wall, [plain[0], plain[6], plain[12]], "o1", "built", 172)
    o1 = ascent.load_route("tw", "o1")["holds"]
    video(photo, "tw", [(h,) for h in o1], "st4.avi", sticker_bgr=(30, 140, 250))
    s, sounds = run("tw", "o1", "st4.avi", sticker="orange")
    check("sticker: ... but an orange sticker on other holds counts", sounds == ["good", "good", "top"], str(sounds))

    det = ascent.StickerDetector("pink")
    frame = np.full((100, 100, 3), 90, np.uint8)
    cv2.circle(frame, (50, 50), 8, (60, 230, 60), -1)
    check("sticker: clicking the sticker teaches its colour", det.sample(frame, 50, 50)
          and det.hands(frame, 0) and not det.sample(frame, 5, 5))

    # a prop wall and a 30 cm puppet: routes fit the puppet's reach
    pwall = ascent.save_scan("prop", photo, corners, 60.0, 43.0, False,
                             [{"px": list(map(float, h)), "type": None} for h in holds])
    made = [quiet(ascent.cmd_generate, SimpleNamespace(wall="prop", name=f"p{i}", moves=5, height=30.0, train=t,
                                                      level=lv, seed=i, preview=False, by=None))
            for i, (t, lv) in enumerate([("", "easy"), ("reach", "medium"), ("traverse", "medium"), ("", "hard")])]
    routes = [ascent.load_route("prop", f"p{i}") for i in range(4)]
    check("prop wall: routes for a 30 cm puppet (easy, reach, traverse, hard), all within its reach",
          all(len(r["holds"]) >= 4 and not any("past" in w for w in r["warnings"]) for r in routes),
          str([len(r["holds"]) for r in routes]))

    # markers wall + sticker
    mwall = json.load(open("walls/mpanel/wall.json"))
    ascent.save_route(mwall, [h["id"] for h in sorted(mwall["holds"], key=lambda h: -h["px"][1])[:4]], "m1",
                      "built", 172)
    mroute = ascent.load_route("mpanel", "m1")["holds"]
    video(mphoto, "mpanel", [(h,) for h in mroute], "st5.avi")
    s, sounds = run("mpanel", "m1", "st5.avi")
    check("sticker: works on a markers wall", s["result"] == "sent" and sounds[-1] == "top", f"{s['result']} {sounds}")


def rehearse_auto_scan(gui):
    """scan --auto: holds found on a plain board, shown, one wrong one removed, one missed one added."""
    gui.install()
    def score(det, holds):
        P, T = np.array([d["px"] for d in det]), np.array(holds, float)
        d = np.linalg.norm(T[:, None] - P[None], axis=2)
        return int((d.min(axis=1) < 10).sum()), int((d.min(axis=0) >= 10).sum())

    results = []
    for seed in (5, 9, 23):
        photo, holds, corners = make_wall_photo(seed=seed)
        results.append(score(ascent.detect_holds(photo, corners), holds))
    check("auto holds: finds the holds on a plain board, no false ones",
          all(f >= 25 and x <= 1 for f, x in results), str(results))
    photo, holds, corners = make_wall_photo(seed=5)
    xx = np.mgrid[0:720, 0:1280][1]
    lit = np.clip(photo * (0.45 + 0.75 * xx / 1280)[..., None], 0, 255).astype(np.uint8)
    f, x = score(ascent.detect_holds(lit, corners), holds)
    check("auto holds: uneven light (dark on the left, bright on the right)", f >= 24 and x <= 5, f"{f} found, {x} false")
    det = ascent.detect_holds(photo, corners)
    truth = {0: "black", 1: "yellow", 2: "blue", 3: "red", 4: "orange"}         # make_wall_photo's colours
    named = [(d["colour"], truth[int(np.argmin(np.linalg.norm(np.array(holds) - d["px"], axis=1))) % 5]) for d in det]
    check("auto holds: hold colours named", sum(a == b for a, b in named) >= 0.9 * len(named),
          f"{sum(a == b for a, b in named)}/{len(named)}")

    # the scan with markers: corners found, holds found, the markers themselves are not holds
    mphoto, mholds, _ = make_wall_photo(seed=9, markers=True)
    cv2.imwrite("auto_m.jpg", mphoto)
    found = ascent.detect_holds(mphoto, ascent.order_corners(
        [c.mean(axis=0) for c in ascent.aruco_detect(cv2.cvtColor(mphoto, cv2.COLOR_BGR2GRAY)).values()]),
        {str(k): v.tolist() for k, v in ascent.aruco_detect(cv2.cvtColor(mphoto, cv2.COLOR_BGR2GRAY)).items()})
    _, ms = ascent.fit(mphoto)
    grid = [(x, y) for x in range(260, 1020, 10) for y in range(100, 640, 10)]
    empty = max(grid, key=lambda p: min((p[0] - a) ** 2 + (p[1] - b) ** 2 for a, b in mholds))
    wrong = found[3]["px"]
    gui.strict = True
    gui.actions = [("click", wrong[0] * ms, wrong[1] * ms),            # remove one
                   ("click", empty[0] * ms, empty[1] * ms), ("key", "s"),   # add one, tag it sloper
                   ("click", 1, 1), ("key", "u"),                      # a stray click, undone
                   ("key", 13)]
    quiet(ascent.cmd_scan, SimpleNamespace(wall="autoprop", image="auto_m.jpg", markers=True, camera=0, auto=True,
                                           width=60.0, height=45.0))
    w = json.load(open("walls/autoprop/wall.json"))
    pxs = [h["px"] for h in w["holds"]]
    check("scan --auto: one removed, one added and tagged, markers are not holds",
          len(w["holds"]) == len(found) and wrong not in pxs and w["holds"][-1]["type"] == "sloper"
          and w["mode"] == "markers" and all(h.get("colour") for h in w["holds"]), f"{len(w['holds'])} holds")
    gen = quiet(ascent.cmd_generate, SimpleNamespace(wall="autoprop", name="a1", moves=5, height=30.0, train="",
                                                     level="medium", seed=1, preview=False, by=None))
    check("scan --auto: a route can be made for a 30 cm puppet", "Route 'a1'" in gen, gen.strip()[:80])
    cols = {h["id"]: h["colour"] for h in w["holds"]}
    gen = quiet(ascent.cmd_generate, SimpleNamespace(wall="autoprop", name="c1", moves=4, height=30.0, train="traverse",
                                                     level="easy", seed=2, preview=False, by=None, colour="red,blue"))
    c1 = ascent.load_route("autoprop", "c1")
    check("generate --colour: only holds of those colours", "Route 'c1'" in gen
          and all(cols[i] in ("red", "blue") for i in c1["holds"]) and "red" in c1["train"], str(c1["holds"]))
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            ascent.cmd_generate(SimpleNamespace(wall="autoprop", name="c2", moves=4, height=30.0, train="",
                                                level="easy", seed=2, preview=False, by=None, colour="green"))
    except SystemExit:
        pass
    check("generate --colour: a colour no hold has is explained", "no hold has the colour 'green'" in buf.getvalue()
          and "c2" not in ascent.route_names("autoprop"))


def check(label, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        check.failed += 1


check.failed = 0


def main():
    gui = FakeGUI()
    gui.install()
    work = tempfile.mkdtemp(prefix="ascent_rehearsal_")
    os.chdir(work)
    try:
        photo, holds, corners = make_wall_photo()
        cv2.imwrite("panel.jpg", photo)
        _, s = ascent.fit(photo)
        disp = lambda p: ("click", p[0] * s, p[1] * s)

        # --- scan: 4 corners (deliberately in the wrong order + one undo), sizes, holds with types
        gui.strict = True
        gui.actions = [disp(corners[2]), disp(corners[0]), disp((600, 300)), ("key", "u"),
                       disp(corners[1]), disp(corners[3]), ("key", 13)]
        types = "jcspk"
        for i, h in enumerate(holds):
            gui.actions.append(disp(h))
            if i % 2 == 0:
                gui.actions.append(("key", types[i % 5]))
        gui.actions.append(("key", 13))
        answers = iter(["300", ""])
        builtins.input = lambda prompt="": next(answers)
        ascent.cmd_scan(SimpleNamespace(wall="panel", image="panel.jpg", markers=False, camera=0))
        wall = json.load(open("walls/panel/wall.json"))
        check("scan saves every hold", len(wall["holds"]) == len(holds), f"{len(wall['holds'])} holds")
        tl = np.array(wall["corners_px"][0])
        check("corners re-ordered correctly", np.allclose(tl, corners[0], atol=1))
        check("height estimated from photo", abs(wall["size_cm"]["h"] - 300 * 590 / 820) < 2,
              f"{wall['size_cm']['h']} cm")
        check("hold types tagged", sum(1 for h in wall["holds"] if h["type"]) == (len(holds) + 1) // 2)
        cms = np.array([h["cm"] for h in wall["holds"]])
        check("hold positions inside the wall in cm", cms.min() > 0 and cms[:, 0].max() < 300)

        # --- generate, with and without filters
        for train in ("", "reach", "sloper", "traverse"):
            ascent.cmd_generate(SimpleNamespace(wall="panel", name=None, moves=5, height=172, train=train,
                                                level="medium", seed=1, preview=False))
        check("four generated routes saved", ascent.route_names("panel") == ["r1", "r2", "r3", "r4"],
              str(ascent.route_names("panel")))

        # --- build: click 4 holds, one click on empty wall is ignored, then Enter
        gui.strict = True
        grid = [(x, y) for x in range(240, 1050, 10) for y in range(80, 660, 10)]
        empty = max(grid, key=lambda p: min((p[0] - a) ** 2 + (p[1] - b) ** 2 for a, b in holds))
        gui.actions = [disp(holds[0]), disp(empty), disp(holds[3]), disp(holds[7]), disp(holds[12]),
                       ("key", 13)]
        ascent.cmd_build(SimpleNamespace(wall="panel", name="mine", height=172))
        built = ascent.load_route("panel", "mine")
        check("build snaps clicks to holds", built["holds"] == [1, 4, 8, 13], str(built["holds"]))

        # --- preview
        gui.actions = [("key", "x")]
        ascent.cmd_preview(SimpleNamespace(wall="panel", route="r1"))
        check("preview opens and closes", True)

        # --- live on a moving camera, then the camera turns away from the wall
        Hs = camera_path(36)
        write_video("cam.avi", photo, Hs, blank_tail=8)
        states, located = [], []
        real_locate = ascent.Tracker.locate

        def spy(self, frame):
            H, st = real_locate(self, frame)
            states.append(st)
            located.append(H)
            return H, st

        ascent.Tracker.locate = spy
        gui.strict = False
        gui.actions = [("key", -1)] * 10 + [("key", "g")] + [("key", -1)] * 8 + [("key", "n")] + \
                      [("key", -1)] * 4 + [("key", "s"), ("key", "f"), ("key", -1), ("key", "f")]
        ascent.cmd_live(SimpleNamespace(wall="panel", route="r2", camera=0, video="cam.avi", features="sift",
                                        train="sloper", moves=5, height=172, level="medium"))
        ascent.Tracker.locate = real_locate
        locked = states[:36].count("locked")
        check("live locks while the wall is in view", locked >= 33, f"{locked}/36 frames")
        check("live draws nothing when the wall is gone", all(h is None for h in located[36:]),
              f"states {states[36:]}")
        errs = []
        r2 = ascent.load_route("panel", "r2")
        px = {h["id"]: h["px"] for h in wall["holds"]}
        pts = [px[i] for i in r2["holds"]]
        for H_true, H_est in zip(Hs[:10], located[:10]):
            if H_est is not None:
                errs.append(np.linalg.norm(ascent.transform(H_est, pts) - ascent.transform(H_true, pts), axis=1).max())
        check("rings land on the holds", errs and max(errs) < 6, f"worst {max(errs):.1f} px, all {np.round(errs, 1).tolist()}" if errs else "no lock")
        check("g key generated a new route", "r5" in ascent.route_names("panel"), str(ascent.route_names("panel")))
        check("screenshot saved", os.path.exists("ascent_shot_1.png"))

        # --- venue lighting: the wall must still lock in dim light, glare and a harsh spotlight
        tracker = ascent.Tracker(wall, photo)
        H_mid = Hs[18]
        base = cv2.warpPerspective(photo, H_mid, (1280, 720), borderValue=(30, 30, 30))
        yy, xx = np.mgrid[0:720, 0:1280]
        spot = np.exp(-(((xx - 900) / 450) ** 2 + ((yy - 220) / 320) ** 2))
        lights = {
            "dim": cv2.convertScaleAbs(base, alpha=0.25),
            "glare": cv2.convertScaleAbs(base, alpha=1.8, beta=40),
            "spotlight": np.clip(base * (0.05 + 0.95 * spot)[..., None], 0, 255).astype(np.uint8),
            "dim+noise+blur": cv2.GaussianBlur(cv2.add(cv2.convertScaleAbs(base, alpha=0.35),
                                               np.random.default_rng(2).integers(0, 25, base.shape, dtype=np.uint8)),
                                               (5, 5), 0),
        }
        held = [name for name, img in lights.items() if tracker.locate(img)[0] is not None]
        check("locks in bad venue lighting", len(held) == len(lights), f"{held}")

        # --- live with no --route picks the newest one and still runs
        gui.actions = []
        ascent.cmd_live(SimpleNamespace(wall="panel", route=None, camera=0, video="cam.avi", features="orb",
                                        train="", moves=5, height=172, level="medium"))
        check("live without --route, ORB features", True)

        # --- markers: scan finds the corners itself, live locks on the markers
        mphoto, mholds, _ = make_wall_photo(seed=9, markers=True)
        cv2.imwrite("mpanel.jpg", mphoto)
        _, ms = ascent.fit(mphoto)
        gui.strict = True
        gui.actions = [("click", x * ms, y * ms) for x, y in mholds] + [("key", 13)]
        answers = iter(["300", "220"])
        builtins.input = lambda prompt="": next(answers)
        ascent.cmd_scan(SimpleNamespace(wall="mpanel", image="mpanel.jpg", markers=True, camera=0))
        ascent.cmd_generate(SimpleNamespace(wall="mpanel", name=None, moves=5, height=172, train="",
                                            level="easy", seed=2, preview=False))
        write_video("mcam.avi", mphoto, camera_path(20))
        states = []
        ascent.Tracker.locate = spy
        gui.strict = False
        gui.actions = []
        ascent.cmd_live(SimpleNamespace(wall="mpanel", route="r1", camera=0, video="mcam.avi", features="sift",
                                        train="", moves=5, height=172, level="medium"))
        ascent.Tracker.locate = real_locate
        check("markers mode locks", states.count("locked") >= 18, f"{states.count('locked')}/20 frames")

        # --- re-scan makes version 2 and archives version 1 with its routes
        gui.strict = True
        gui.actions = [disp(c) for c in corners] + [("key", 13)] + [disp(h) for h in holds[:10]] + [("key", 13)]
        answers = iter(["300", ""])
        builtins.input = lambda prompt="": next(answers)
        ascent.cmd_scan(SimpleNamespace(wall="panel", image="panel.jpg", markers=False, camera=0))
        v2 = json.load(open("walls/panel/wall.json"))
        check("re-scan makes version 2", v2["version"] == 2)
        check("version 1 and its routes archived", os.path.exists("walls/panel/archive_v1/routes/r1.json"))
        check("version 2 starts with no routes", ascent.route_names("panel") == [])

        # --- scan --width --height: sizes from the command line, no typing at all
        gui.strict = True
        gui.actions = [disp(c) for c in corners] + [("key", 13)] + [disp(h) for h in holds[:6]] + [("key", 13)]

        def no_typing(prompt=""):
            raise RuntimeError("scan asked a question although --width and --height were given")
        builtins.input = no_typing
        ascent.cmd_scan(SimpleNamespace(wall="sized", image="panel.jpg", markers=False, camera=0,
                                        width=250.0, height=180.0))
        sized = json.load(open("walls/sized/wall.json"))
        check("scan --width --height needs no typing",
              sized["size_cm"] == {"w": 250.0, "h": 180.0, "assumed": False}, str(sized["size_cm"]))
        try:
            ascent.positive_cm("0")
            refused = False
        except ascent.argparse.ArgumentTypeError:
            refused = True
        check("scan refuses a size of 0 cm", refused and ascent.positive_cm("2,5") == 2.5)

        rehearse_track(gui, photo, holds, corners)
        rehearse_log()
        rehearse_progress()
        rehearse_profile()
        rehearse_routes()
        rehearse_challenges()
        rehearse_serve_live(photo)
        rehearse_serve_scan(photo, holds, corners, mphoto)
        rehearse_serve_track(photo)
        rehearse_sticker(photo, mphoto, holds, corners)
        rehearse_auto_scan(gui)
        rehearse_serve_flow(photo, mphoto, holds, corners)
    finally:
        os.chdir(ROOT)
        shutil.rmtree(work, ignore_errors=True)

    print("\nAll checks passed." if check.failed == 0 else f"\n{check.failed} check(s) failed.")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
