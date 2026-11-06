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
        check("rings land on the holds", errs and max(errs) < 6, f"worst {max(errs):.1f} px" if errs else "no lock")
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
    finally:
        os.chdir(ROOT)
        shutil.rmtree(work, ignore_errors=True)

    print("\nAll checks passed." if check.failed == 0 else f"\n{check.failed} check(s) failed.")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
