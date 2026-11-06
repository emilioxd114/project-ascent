# 06 · Architecture of the prototype

Everything is in `ascent.py` — one Python file, OpenCV and numpy, running on a laptop with its webcam. This is a deliberate hackathon choice (see CLAUDE.md). Since 6 Nov a phone can be the camera instead: `serve` (below) is a local HTTPS server, standard library only, with plain HTML and JavaScript pages in `web/`. Moving to a real phone app is a separate decision for later.

## Commands

| Command | What it does |
| --- | --- |
| `serve` | Phone as camera: HTTPS server on 0.0.0.0:8443 (`--port`, `--host`, `--code`), prints one phone link with the laptop's IP and an access code. One page with four tabs: **Climb** (the whole flow, nothing typed: photo -> wall and holds found -> route by skill -> phone down, sounds), See a route, Scan a wall, Record my try (`#climb`, `#climb`, `#live`, `#scan`, `#track`; the addresses `/live`, `/scan`, `/track` open the same page on that tab, the plain link opens Climb). |
| `selftest` | Builds a synthetic wall, views it from another angle, checks the overlay error. No camera needed. |
| `scan` | Photo (webcam or `--image`) → click 4 corners → type real size in cm (or pass `--width` / `--height` in cm to skip the questions) → click and tag every hold → save. `--markers` finds the corners from printed markers instead. `--auto` finds the holds automatically and shows them for checking (click a ring = remove, click elsewhere = add, u = undo); without it, every hold is clicked by hand as before. |
| `generate` | Rules-based route; `--train`, `--moves`, `--height`, `--level`, `--seed`, `--preview`, `--by NAME` (who set it, optional), `--colour red[,blue]` (only holds of those colours, from `scan --auto`; the colours are added to the route's `train` tags). |
| `build` | Click holds in order on the photo; warns about moves past reach. `--by NAME` optional. |
| `live` | Route on the live camera. Keys: g new route, n next, f full screen, s screenshot, v record, q quit. `--video` replays a file instead of the webcam. |
| `preview` | Route drawn on the saved photo — the no-camera backup. |
| `list` | Walls and routes. |
| `track` | "Record my try": the route on the live camera plus touch tracking (`--touch sticker` by colour, `hands` MediaPipe hand landmarks, `pose` MediaPipe body); a sound for each hold reached in order, an alert for an off-route or out-of-order hold. Keys: m sound on/off, q stop. `--video`, `--mute`, `--touch-cm`, `--pose-model`. Needs `pip install mediapipe`. `--climber NAME` saves the camera's guess in the logbook. |
| `log` | Logbook. `log --climber lena --wall panel --route r1 --result sent\|tried\|fail [--note ...] [--date YYYY-MM-DD]` adds a climb; `log --climber lena` shows the history; `--undo` removes the last entry. |
| `profile` | `--climber NAME` with `--goal --level --height --language --visibility --minor/--adult --parental-consent`, rehab: `--therapist --rehab-level --sessions-per-week`. Only given fields change. No `--climber`: list profiles. `--delete` shows what would be deleted, `--delete --yes` deletes it. |
| `safety` | The safety card, `--language en\|de` or the climber's language. |
| `routes` | The route list with filters: `--train`, `--grade 6a\|5a-6a`, `--holds 4-6`, `--made-by generated\|built`, `--by NAME`; with `--climber NAME`: your result per route, `--new` (not sent yet), `--within-reach` (no move past 0.55 × your height). Shows "N climbed". |
| `challenge` | `--climber me --to NAME --wall W --route R [--message ...]` invites someone on this laptop; `--climber me` lists challenges to and from me; `--decline c3`. |
| `progress` | `--climber NAME [--goal train\|play\|rehab]`: counts, then skills (train), level (play) or sessions per week (rehab), then milestones. |
| `recommend` | `--climber NAME --wall W [--height --level --goal] [--make N]`: what to climb next, every line with its reason; `--make` generates N routes set by the climber. |

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
- `colour` (from `scan --auto`, optional): red, orange, yellow, green, blue, purple, pink, black, white or grey.
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

**profiles/&lt;climber&gt;.json** — the sign-up answers. Kept out of git.

```json
{"name": "laura", "goal": "rehab", "level": "medium", "height_cm": 168, "language": "de",
 "minor": false, "visibility": "private", "created": "...",
 "rehab": {"therapist": "Dr. Berger", "level": "easy", "sessions_per_week": 2}}
```

- `goal`: train (Lena) / play (Max) / rehab (Laura). `language`: en / de (stored; the safety card uses it, other text is English for now).
- **Age group, not birth date** (`minor`), to store the minimum.
- **Visibility** private / friends / public, private by default. A minor can't be public, and needs `parental_consent` for friends. Sharing isn't built (it needs a server); the rules exist first, as 07-legal-and-safety.md asks.
- **`rehab`** is health data: only the therapist's settings, no diagnosis, always private whatever `visibility` says, removed when the goal stops being rehab. A rehab level always wins over `level`.
- `safety_seen`: walls on which this climber has seen the safety card. `routes --climber` and `track --climber` show it the first time on each wall, in the profile's language; without a profile it is shown every time. `live` is unchanged, so it does not show the card (yet).
- **Delete one person:** removes their profile and logbook, and removes `by` from routes they set (the routes stay, anonymous).

**challenges/c&lt;n&gt;.json** — kept out of git.

```json
{"id": "c1", "from": "max", "to": "lena", "wall": "panel", "wall_version": 1, "route": "r3",
 "estimated_grade": "~5c", "created": "2026-11-06 11:02", "message": "your turn",
 "done": {"date": "2026-11-06 11:20", "result": "tried"}, "declined": null}
```

- **Done** when the person challenged logs the route after it was created with **sent or tried** (typed or by `track`). Trying counts; a `fail` doesn't finish it.
- **Both win:** sender and receiver get the "Team player" milestone and 2 play points. Nobody wins *against* anyone.
- **No deadline, no expiry, no penalty.** `--decline` is always fine.
- **Minors:** a route with a move past the receiver's reach (profile height) is refused; the receiver is told to climb it together or with an adult nearby. For adults it's a note.
- Deleting a person deletes every challenge they sent or received.
- Local only: both people need a profile name on the same laptop. Sending to another phone needs the shared server.

Routes may also have `"by": "max"` (who set them, from `--by`); older routes without it still load.

**logbook/&lt;climber&gt;.json** — one file per person, so one person can be deleted from everything (GDPR question 6). Kept out of git.

```json
{"climber": "lena", "entries": [
  {"date": "2026-11-06 10:40", "wall": "panel", "wall_version": 1, "route": "r1",
   "result": "sent", "by": "self", "estimated_grade": "~6a", "train": ["sloper"],
   "hold_types": ["jug", "sloper"], "moves": 5, "note": "...",
   "attempt": {"reached": 6, "of": 6, "skipped": [], "off_route": [], "seconds": 21.4}}
]}
```

- `result`: **sent** = reached the finish in order; **tried** = got past the start; **fail** = didn't get going.
- `by`: `self` (typed) or `camera` (from `track --climber`). `attempt` exists only for camera entries and holds counts, never video or raw hand positions.
- Each entry keeps a copy of the route's grade, skills and hold types, so the history still means something after the wall is re-scanned.
- Names become file names: lower case, spaces to `_`, umlauts to ae/oe/ue/ss, other characters dropped.
- **"N people climbed this"** = number of different climbers with a `sent` entry for that route on that wall version.

## Automatic hold detection (`scan --auto`)

Rules, no AI; made for a **plain, single-colour board with coloured holds** (the prop wall).

- Works on a copy of the photo at most 900 px, only **inside the four corners** with a margin of 1.5% of the wall's width (the board's edge and the corners are never holds), and never on the printed markers.
- **The board's colour around every point** = a large median filter (a sixth of the wall's width) of the photo in Lab colour, with everything outside the wall painted in the board's colour first. A pixel belongs to a hold when it differs from that by more than max(22, median + 4 robust deviations). This copes with uneven light.
- **Blobs** after a little clean-up count as holds when they are at least 1.2% of the wall's width across (smaller: bolt holes, specks), at most 3% of the wall's area, not long and thin (tape, seams), and not ragged (shadows, chalk).
- **Colour name** per hold (red, orange, yellow, green, blue, purple, pink, black, white, grey) from its median hue, saturation and brightness, saved as `"colour"` in `wall.json` (an extra field; older scans without it still load).
- **Always checked by a person:** the review window shows every found hold; that is also the fallback - if nothing is found, it is the old click-every-hold window.
- On the synthetic test walls: 26 of 26 holds, no false ones; under a strong light gradient 25 of 26.

## Board outline (`detect_board`, the Climb tab)

Finds the board without markers or taps: the largest plain, four-sided area whose outline is a real edge. Rules, no AI, on a copy of the photo at most 640 px:

- **A, by colour:** the colour of the middle of the picture (Lab median of the central eighth) is the board's; pixels within 2.5 or 4 robust spreads of it, closed and opened, largest component, its contour simplified to 4 points (`approxPolyDP`, growing tolerance; else the minimum-area box if it fills 80 % of it).
- **B, by edges:** the largest Canny contours simplified the same way.
- **Checks on every candidate:** convex; 12-97 % of the picture; no side shorter than 12 % of the picture; **at most one side along the picture's edge** (the whole board must be in the photo); and at least 60 % of the outline must lie on edge pixels. A plain-colour candidate beats an edge-only one.
- The corners are then sharpened on the full-size photo (`cornerSubPix`); a corner that wanders off stays where it was.
- **Never guesses:** a cut-off board, a wall that fills the whole picture, a blank or a noisy picture give `None`, and the phone asks for 4 taps. On the synthetic walls (plain, uneven light, at an angle) the corners are within 1 px.

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

## Phone as camera (`serve`)

- **Standard library only:** `http.server.ThreadingHTTPServer` + `ssl` + `threading`. One plain HTML page, `web/index.html`, with four tabs; each tab's code is its own plain script (`flow.js`, `live.js`, `scan.js`, `track.js`, sharing `common.js`). Leaving a tab stops its camera. No framework, no build step.
- **Errors are reported:** any JavaScript error or failed promise shows in an amber box on the phone and is sent to `POST /api/log`, which prints it in the laptop's terminal as `Phone error (#tab): ...` with the phone's browser name.
- **Certificate:** self-signed, made on first run with the optional `cryptography` package, in `tls/` (out of git - it holds a private key). It names `localhost`, `127.0.0.1` and the laptop's LAN IPs, and is remade when the laptop gets an IP it doesn't name (e.g. on the phone's hotspot); the phone then warns once more.
- **Access code:** 6 random characters per run (or `--code`), in the link printed on the laptop. Pages and API calls need it, either in the URL or in the cookie the first page sets (`Secure; HttpOnly; SameSite=Strict`). Only `web/*.js` and `web/*.css` load without it; they hold no data. Other people on the Wi-Fi get "Ask for the link with the code".
- **Live loop:** the phone's back camera fills the screen (`object-fit: cover`); at most 8 times a second, with one request in flight, it sends a JPEG of the current frame (long side 800 px, quality 0.7) to `POST /api/frame?sid=...`. The laptop runs the same `Tracker` and smoothing as `live` and answers either `{"state": "locked", "rings": [{"x", "y", "n", "kind"}], "radius", "w", "h"}` in frame pixels, or `{"state": "far" | "close" | "lost", "message"}` (after 9 s without lock: "Has it been reset?"). The phone maps frame pixels to the screen and draws the haloed, numbered rings on a canvas over the video.
- **Never guess on the phone either:** rings are drawn only for a `locked` answer, and the canvas is cleared when no answer arrived for 0.6 s.
- **Latency:** the rings belong to the frame sent ~100-200 ms earlier, so they trail a moving phone slightly; held still, they settle on the holds.
- **API:** `GET /api/walls` (walls and routes); `POST /api/live/start` `{wall, route?, train?, level?, moves?, height?}` → session id and route info; `POST /api/frame?sid=`; `POST /api/route/new?sid=` (like **g**) and `/api/route/next?sid=` (like **n**). Sessions expire after 15 idle minutes, at most 8 at once.
- **Scan tab:** the photo is taken **inside the page** from the same camera stream as the live view (1920x1080 requested, preview shows the whole frame), so the phone never switches to its camera app - on some phones that switch reloads the page and loses the photo. **Choose a photo** (gallery) is the backup; it is decoded upright by the browser, with a plain fallback if that takes over 5 s. Either way the picture is downscaled to at most 1600 px, so the laptop gets exactly the image that was tapped on. Then: tap 4 corners in any order (or "use the printed markers": `POST /api/scan/markers` finds them), width and height in cm (width empty = 300 cm assumed; height empty = from the photo's proportions, as in the CLI), tap holds and tag types. `POST /api/scan` `{wall, image, markers, corners, width, height, holds: [{px, type}]}` checks everything first (4 corners forming a convex shape, taps inside the photo, known hold types, at least one hold, enough markers) and then calls `save_scan` - the same function the CLI `scan` uses - so `wall.json`, `ref.jpg` and versioning are identical. Nothing is archived when a check fails. The page asks before making version N+1 of an existing wall.
- **/track:** like `/live`, plus `POST /api/track/start` `{wall, route, climber?, touch?: sticker|hands|pose|auto, sticker?: green|pink|orange|yellow|blue|red, touch_cm?}` makes a session with its own detector - the CLI's `StickerDetector` for `touch: sticker` (no MediaPipe; `&tapx=&tapy=` on a frame teaches the sticker's colour from that frame, the answer says `learned` and `sticker`), `HandDetector` for `hands`, `PoseDetector` for `pose`, `auto` = hands if MediaPipe is installed else sticker - and `AttemptWatcher` (the same touch rule as the CLI `track`; the touch radius comes from the wall's hold spacing unless `touch_cm` is given, and the start answer reports it as `touch_cm`). Each frame carries the phone's capture time (`&t=` seconds); when locked, the laptop finds the hands, maps them into wall centimetres and answers with `hands` (to draw), `next`/`of` and `events` [`{sound: good|order|off|top, message}`]; the phone plays the same four tones with Web Audio (switched on by the Start tap, as iPhones require). Not locked: no hands, no events. `POST /api/track/finish` returns the camera's guess and, with a climber name, saves it in their logbook (counts only) and finishes any challenge it completes; `/api/track/reset` = Try again. The safety card comes with the start answer the first time a climber opens the wall. Without MediaPipe on the laptop the page shows "track needs MediaPipe" and the server keeps running. Old sessions release their MediaPipe detector.
- **The Climb tab** (`web/flow.js`) connects the pieces above in one guided flow and adds three calls:
  - `POST /api/scan/auto` `{image, corners?}` -> `{how: markers|outline|taps|null, corners, holds: [{px, type, colour}], markers_found, message?}`. Corners: the 4 markers when all are in the photo; else `detect_board` (below); else the taps the phone sends after asking for them; `how: null` = ask for 4 taps. Holds: `detect_holds`, the same as `scan --auto`. Saving goes through the same `POST /api/scan` (width empty = 300 cm assumed; hold colours are kept).
  - `POST /api/route/make` `{wall, skill: reach|traverse|easy|hard, moves?, height?, seed?}` -> the route previewed, not saved: `holds`, `holds_px` (photo pixels, to draw on the photo), `grade`, `warnings`, `short`. `POST /api/route/save` `{wall, holds, skill, how?: generated|built}` saves it as the next `rN` (`route_record` builds the record, `save_route` writes it); `built` = tapped or edited by hand on the phone, saved like the CLI's `build` (made_by `built`, no skill tag). The climber height defaults to `height_for_wall` = 0.55 x the wall's width, so reach is ~0.3 x the width whether the wall is a 300 cm panel or a 60 cm prop wall. **On an unmeasured wall** (size assumed, 300 cm wide) the height is raised until the reach covers 1.15 x the usual step to the second-nearest hold: on the first real prop wall (tall and narrow) the width-scaled reach was 91 'cm' and the nearest holds 95 apart, so no move fit and the phone said "3 holds, that is all that fits". The route keeps its "size not measured" warning.
  - `POST /api/route/check` `{wall, holds}` -> the same preview (`holds_px`, `grade`, `warnings`) for a route tapped in by hand, so the phone can show the grade and a "past your reach" warning while the person builds or edits it. Two or more different holds of the wall, else 400.
  - `GET /api/wall/photo?wall=` serves `ref.jpg` (code needed), so a route can be drawn on an already scanned wall; `GET /api/wall/holds?wall=` gives its corners, hold ids and positions, so the phone can draw every hold faintly (tap one to add it to the route) and bring the saved scan back for **Fix the holds** (Looks good then saves version N+1 through the same `/api/scan`).
  - Climbing is `/api/track/start` with `touch: auto` (hands when the laptop has MediaPipe, else sticker; Options can force one) - the answer says which, and the phone shows "the laptop tracks your hands" or "tap the sticker once". The tap on the live view is mapped to the sent frame's pixels and travels with the next frame. The sounds are `Ascent.makeSounds()` in `common.js`, the same four tones.
- **TLS handshake** happens in each request's thread (`do_handshake_on_connect=False`) with a 30 s timeout, so a silent or refusing phone can't stall others; dropped connections and refused certificates don't print tracebacks.
- **Safety of the server:** wall and route names from the phone must be letters, digits, `-`, `_`; only files listed in `web/` are served; uploads are capped at 25 MB; the CLI helpers' error exits become a 400 with the message, so the server stays up.

## Motion tracking (`track`)

**Default since 6 Nov: touch tracking by sticker colour, no AI** (`--touch sticker`). For the demo a puppet (or a fingertip) wears a bright sticker on each hand; MediaPipe stays available with `--touch pose`.

- **Sticker detector:** HSV colour range (`--sticker green|pink|orange|yellow|blue|red`, or click the sticker in the window to learn its exact colour), small noise removed, only inside the locked wall (a little margin around it), blobs from 10 px up to 3% of the wall's area, the 2 largest. Each sticker keeps its name from frame to frame (nearest to where it was).
- **Same-colour holds are ignored:** pixels of the sticker colour in the scan photo are warped into the frame and removed, so an orange hold is never mistaken for an orange sticker. The flip side: a sticker on a hold of its own colour is invisible. **Choose a sticker colour that no hold has.** Key `d` shows what counts as sticker.
- **Touch rule:** a sticker within the touch distance of a hold's centre for 0.5 s (`--dwell`). The touch distance is 45% of the usual gap between neighbouring holds, at most 12 cm (`--touch-cm` to set it) - small on a prop wall, so one touch can't land on two holds. Two stickers arriving in the same moment count in climbing order.
- Sounds, order rules, "never draw / count without a lock", the result and `--climber` are the same as below.
- **Touch radius on an unmeasured wall:** the 12 cm cap is in the wall's own centimetres; when the size was only assumed (300 cm wide) the cap is 8% of the width instead, because 12 'cm' on a 60 cm prop wall is 2.4 real cm and a fingertip on the edge of a hold would miss. It stays at most 45% of the gap between neighbouring holds, so a touch never lands on two holds.

- **Hands (`--touch hands`, `HandDetector`):** MediaPipe Hands (Tasks API, `hand_landmarker.task`, 7.8 MB, downloaded once into `models/`), up to two hands, each given by the mean of its index and middle fingertips in frame pixels - the part of a hand that is on a hold. Chosen after the first real photo (6 Nov, only the climber's arm in view): the pose model put the wrist 20 cm off with low visibility, the hand model found the fingertip, 26-45 ms per 800 px frame on a laptop CPU. Same interface as the pose detector; the Climb tab uses it through `touch: auto`. Nothing is saved; it only says where the hands are.

- **Pose:** MediaPipe Pose, imported only inside `track`, so every other command works without it. Supports the old `mediapipe.solutions` API and the newer Tasks API (MediaPipe 1.x), which needs `models/pose_landmarker_lite.task` (5.5 MB, downloaded once on first use, kept out of git; `--pose-model FILE` to use a copy).
- **Hands only.** A hand's position is the mean of wrist, index and pinky landmarks (visibility > 0.5). Feet are free, as for generated routes.
- **Into wall centimetres:** frame pixels → photo pixels with the inverse of the tracker's H → wall cm with the scan's rectification. Hands only count, and rings are only drawn, while the wall is **locked**.
- **Touch rule:** a hand within 12 cm (`--touch-cm`) of a hold's centre for 0.4 s is on that hold.
- **Order:** the next hold in the route → "good" sound; the finish → "top"; a route hold further ahead → "order" alert, the holds in between count as skipped; a hold not on the route → "off" alert (at most once per hold per 2 s). Touches before the start or after the top don't count; going back to a hold already reached is silent.
- **The camera's guess:** `sent` = finish reached in order with no off-route holds; `tried` = got past the start; `fail` = did not. Always shown as a suggestion.
- **Sounds:** four short tones made with the standard library at start-up; played without waiting through winsound (Windows), afplay (macOS) or paplay/aplay (Linux), otherwise the terminal bell. No sound files in git.
- **Privacy:** no video is saved, nothing leaves the laptop; the screen and console say that an AI model is tracking the body (AI Act Art. 50) and that it does not judge whether a movement is safe.

## Progress and recommendations (rules, no AI)

Settings come from the options, else the climber's profile (`profiles/<name>.json`), else height 172, level medium, goal train.

- **train (Lena) - skills:** for each hold type plus reach and traverse, how many logged climbs had it (route hold types and `--train` tags) and how many were sent.
- **play (Max) - level:** points = climbing days + 2 per different route + 1 per hold type tried + 3 per send of a route you set by someone else + 2 per finished challenge. Level = 1 + points / 10. **No points for grade**, no streaks: a rest day costs nothing.
- **rehab (Laura) - sessions:** climbing days per ISO week against the therapist's `sessions_per_week`, and the therapist's level. Always says it does not judge whether a movement is safe.
- **Milestones:** first climb, first send, 5 different routes, every hold type, 4 different weeks, someone else sent your route, finished a challenge. Never a hardest-grade milestone.
- **Recommendation rules:** (1) the skill available on this wall that the climber has climbed least → generate with `--train` that skill, and list up to 3 existing routes with it not yet sent; (2) 3 or more of the last 5 climbs were `fail` → one level easier; (3) all of the last 5 sent → *offer* one level harder, only for goal train and adults; minors and play never get "harder"; (4) rehab always uses the therapist's level. No log yet → an easy warm-up route.

## Route generator (rules, no AI)

- **Reach** = 0.55 × climber height (95 cm for 172 cm). No move may exceed it.
- **Fixed minimums** (a move at least 15 cm, at least 5 cm up or sideways) are for people. Below 120 cm - a puppet or a small child on a prop wall - they scale with height (× height / 172), so a 30 cm puppet gets moves of 2.6 cm and more within its 16.5 cm reach. People's routes are unchanged.
- **Target move length** by level: easy 0.30, medium 0.40, hard 0.50 × height. Candidates are weighted by a Gaussian around the target.
- **Normal routes:** start in the bottom 35 % of the wall, every move goes up at least 5 cm, finish in the top 30 %.
- **Traverse:** start in the left or right 30 %, move sideways towards the other side, vertical change under 0.35 × height.
- **Skill weights:** reach ×(1 + 2·d/reach); a matching hold type ×3.
- 600 random weighted attempts; the best-scoring finished route wins. If the requested number of holds doesn't fit, it steps down and says so.
- **Estimated grade:** mean move length relative to height, +0.02 for slopers, crimps and pockets, −0.02 for jugs, mapped to 4 … 7a and shown with `~`.
- Feet are free ("hands only, feet anywhere"), a normal spray-wall convention.

## Tests

- `python ascent.py selftest` — install check, overlay error on a synthetic warped wall.
- `python tests/rehearsal.py` — a full session with scripted clicks, keys and a synthetic moving camera: scan (with undo and out-of-order corners), generate with every filter, build, preview, live (g, n, s, f), lighting (dim, glare, spotlight, noise), markers mode, re-scan versioning, `--width`/`--height` without typing, motion tracking with a scripted hand (in order, off-route, out of order, no lock), sticker tracking on a synthetic video (sounds, two stickers, no lock, same-colour holds ignored, click to learn the colour, markers wall), logbook (log, undo, N people climbed this, names), progress and recommendations (no grade points, minors never pushed harder, rehab level fixed), profiles (minors, health data, delete one person), safety card once per wall, route filters, challenges (sent or tried finishes it, minors, decline, delete), `serve` + `/live` over real HTTPS with synthetic phone frames (access code, no path escapes, lock, ring accuracy in cm, no rings when lost or far, new/next route, bad requests, certificate reuse), `/scan` (same wall.json and cm as the CLI, versioning and archiving, markers, nine kinds of bad scan refused with nothing saved), `/track` with a scripted hand (sounds, off-route, no lock, Finish into the logbook, safety card once, missing MediaPipe, sessions released), a silent connection not blocking others, the one page with four tabs, phone errors printed on the laptop, the Climb flow (board outline found within 2 px and never guessed, `/api/scan/auto` by markers / outline / taps, saving with an assumed size, routes for every skill within a wall-scaled reach, preview then save, sticker tracking from the phone with sounds, a tap teaching the colour, bad input refused, a saved wall's holds fetched, a hand-built route checked and saved as `built`, `touch: auto` picking sticker or hands, fingertips from a faked hand model counted in order, hands without MediaPipe refused clearly), and the hold layout of the first real prop wall (unmeasured: reach covers the step between holds, 5-hold routes for reach / easy / hard, a fingertip-sized touch radius; measured: unchanged). 168 checks, plus two that run the real MediaPipe pose and hand models when they are installed.
- `python tests/e2e/flow_e2e.py` — the Climb tab in a headless Chromium with a fake camera playing synthetic wall footage against the real server: wall saved with its holds, Build my own (three taps, grade and a reach warning), a ring tapped out again, route by skill, Use this route, Start (sticker mode, as the footage shows a sticker), four goods and a top, Done says sent, Fix the holds brings the scan back and Looks good saves version 2. Needs Node with Playwright, so it is run by hand, not by the rehearsal. The corner-tap path was also driven this way with the photo of the real prop wall: corners within 4 px, 11 of 11 holds found (not in git: the photo shows the venue).

**Not covered:** a real webcam, real windows on Windows, the real panel under venue light.

## Known technical limits

- **Partial resets:** if a few holds move, the wall still matches and routes using those holds draw onto empty wall.
- **Flat walls only:** one homography assumes a plane; overhangs and volumes need multiple planes or 3D.
- **Low-texture walls** may not match — use markers.
- **Grades** are rough estimates.
- **Hold type detection** is manual.
