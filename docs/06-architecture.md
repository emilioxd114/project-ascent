# 06 · Architecture of the prototype

Everything is in `ascent.py` — one Python file, OpenCV and numpy, running on a laptop with its webcam. This is a deliberate hackathon choice (see CLAUDE.md). Moving to a phone app is a separate decision for later.

## Commands

| Command | What it does |
| --- | --- |
| `selftest` | Builds a synthetic wall, views it from another angle, checks the overlay error. No camera needed. |
| `scan` | Photo (webcam or `--image`) → click 4 corners → type real size in cm (or pass `--width` / `--height` in cm to skip the questions) → click and tag every hold → save. `--markers` finds the corners from printed markers instead. |
| `generate` | Rules-based route; `--train`, `--moves`, `--height`, `--level`, `--seed`, `--preview`. |
| `build` | Click holds in order on the photo; warns about moves past reach. |
| `live` | Route on the live camera. Keys: g new route, n next, f full screen, s screenshot, v record, q quit. `--video` replays a file instead of the webcam. |
| `preview` | Route drawn on the saved photo — the no-camera backup. |
| `list` | Walls and routes. |
| `track` | "Record my try": the route on the live camera plus MediaPipe hand tracking; a sound for each hold reached in order, an alert for an off-route or out-of-order hold. Keys: m sound on/off, q stop. `--video`, `--mute`, `--touch-cm`, `--pose-model`. Needs `pip install mediapipe`. |

## Data on disk

```
walls/<wall>/
  ref.jpg              the reference photo
  wall.json            the wall map
  routes/<name>.json   routes on this version
  archive_vN/          an older version with its own ref.jpg, wall.json and routes
```

**wall.json**

```json
{
  "name": "panel", "version": 1, "scanned": "2026-11-06 09:12",
  "mode": "features",
  "corners_px": [[x, y], [x, y], [x, y], [x, y]],
  "size_cm": {"w": 300, "h": 216, "assumed": false},
  "holds": [{"id": 1, "px": [x, y], "cm": [x, y], "type": "sloper"}],
  "markers_px": {"0": [[x, y], ...]}
}
```

- `corners_px` are ordered top-left, top-right, bottom-right, bottom-left, in photo pixels.
- Hold `cm` coordinates: x to the right, **y upwards**, origin at the bottom-left corner.
- `type` is one of jug, crimp, sloper, pinch, pocket, or null.
- `markers_px` exists only in markers mode.

**route json**

```json
{
  "name": "r1", "wall": "panel", "wall_version": 1, "holds": [12, 7, 3, 9, 15],
  "estimated_grade": "~6a", "train": ["sloper"], "made_by": "generated",
  "height_cm": 172, "created": "...", "warnings": ["Move 3 -> 4 is 6 cm past your reach"]
}
```

The first hold is the start (green), the last the finish (red), the rest the middle (blue).

## Geometry

- **Rectification:** the four corners and the real width and height give a perspective transform from photo pixels to wall centimetres. Every hold gets both coordinates at scan time.
- **Overlay:** the tracker returns a homography H from photo pixels to live-frame pixels; holds are drawn at `H · px`. Ring size follows H, so rings shrink with distance.
- **Scale skipped:** the wall is assumed 300 cm wide and every warning says reach checks are approximate.

## Tracking

**Features mode (default).** SIFT keypoints on the saved photo (scaled to 1000 px wide) and on each frame (960 px), FLANN matching with Lowe's ratio test (0.75), RANSAC homography (5 px). Locked when ≥ 20 inliers and the projected wall passes sanity checks: convex, area between 1 % and 25× the frame, finite.

**Two looks at every image.** Each frame is matched as it is, and — if that fails — again with CLAHE local-contrast correction; reference features exist for both. The plain look copes with dim light, the corrected one with spotlights. The tracker tries whichever worked last time first.

**States.** `locked` · `far` (projected wall under 10 % of the frame → "Move closer") · `close` (under 60 % of the wall inside the frame → "Step back") · `lost`. After 9 s without lock: "Has this wall been reset?". A 0.25 s grace period stops flicker; nothing is drawn otherwise.

**Markers mode.** ArUco DICT_4X4_50, IDs 0–3, printed 12 cm. Any detected marker's four corners are matched to the same marker in the photo; at least two markers are needed (one gives "Step back").

**Smoothing.** Ring positions are averaged 50/50 with the previous frame when they moved less than 40 px.

**Speed.** About 60–80 ms per frame for SIFT on a laptop-class CPU; ORB (`--features orb`) is about twice as fast and less robust.

## Motion tracking (`track`)

- **Pose:** MediaPipe Pose, imported only inside `track`, so every other command works without it. Supports the old `mediapipe.solutions` API and the newer Tasks API (MediaPipe 1.x), which needs `models/pose_landmarker_lite.task` (5.5 MB, downloaded once on first use, kept out of git; `--pose-model FILE` to use a copy).
- **Hands only.** A hand's position is the mean of wrist, index and pinky landmarks (visibility > 0.5). Feet are free, as for generated routes.
- **Into wall centimetres:** frame pixels → photo pixels with the inverse of the tracker's H → wall cm with the scan's rectification. Hands only count, and rings are only drawn, while the wall is **locked**.
- **Touch rule:** a hand within 12 cm (`--touch-cm`) of a hold's centre for 0.4 s is on that hold.
- **Order:** the next hold in the route → "good" sound; the finish → "top"; a route hold further ahead → "order" alert, the holds in between count as skipped; a hold not on the route → "off" alert (at most once per hold per 2 s). Touches before the start or after the top don't count; going back to a hold already reached is silent.
- **The camera's guess:** `sent` = finish reached in order with no off-route holds; `tried` = got past the start; `fail` = did not. Always shown as a suggestion.
- **Sounds:** four short tones made with the standard library at start-up; played without waiting through winsound (Windows), afplay (macOS) or paplay/aplay (Linux), otherwise the terminal bell. No sound files in git.
- **Privacy:** no video is saved, nothing leaves the laptop; the screen and console say that an AI model is tracking the body (AI Act Art. 50) and that it does not judge whether a movement is safe.

## Route generator (rules, no AI)

- **Reach** = 0.55 × climber height (95 cm for 172 cm). No move may exceed it.
- **Target move length** by level: easy 0.30, medium 0.40, hard 0.50 × height. Candidates are weighted by a Gaussian around the target.
- **Normal routes:** start in the bottom 35 % of the wall, every move goes up at least 5 cm, finish in the top 30 %.
- **Traverse:** start in the left or right 30 %, move sideways towards the other side, vertical change under 0.35 × height.
- **Skill weights:** reach ×(1 + 2·d/reach); a matching hold type ×3.
- 600 random weighted attempts; the best-scoring finished route wins. If the requested number of holds doesn't fit, it steps down and says so.
- **Estimated grade:** mean move length relative to height, +0.02 for slopers, crimps and pockets, −0.02 for jugs, mapped to 4 … 7a and shown with `~`.
- Feet are free ("hands only, feet anywhere"), a normal spray-wall convention.

## Tests

- `python ascent.py selftest` — install check, overlay error on a synthetic warped wall.
- `python tests/rehearsal.py` — a full session with scripted clicks, keys and a synthetic moving camera: scan (with undo and out-of-order corners), generate with every filter, build, preview, live (g, n, s, f), lighting (dim, glare, spotlight, noise), markers mode, re-scan versioning, `--width`/`--height` without typing, motion tracking with a scripted hand (in order, off-route, out of order, no lock). 27 checks, plus one that runs the real MediaPipe model when it is installed.

**Not covered:** a real webcam, real windows on Windows, the real panel under venue light.

## Known technical limits

- **Partial resets:** if a few holds move, the wall still matches and routes using those holds draw onto empty wall.
- **Flat walls only:** one homography assumes a plane; overhangs and volumes need multiple planes or 3D.
- **Low-texture walls** may not match — use markers.
- **Grades** are rough estimates.
- **Hold type detection** is manual.
