# 08 · Status and next steps

Status as of the night of 5 Nov 2026, before the final day.

## Done

- **Research:** competitors, ClimbAI, the Kilter–Aurora split (03-market.md).
- **Users:** three personas with full canvases and critique (02-users.md).
- **Concept:** fundamental decisions, scope, roadmap (04-product.md).
- **Design:** nine phone screens on the canvas, in two rows (05-design.md).
- **Prototype** (`ascent.py`): scan with corners, scale, hold tapping and types; markers fallback; rules-based generator with reach guardrails and skill filters; build mode; live overlay with route switching and live generation; never guessing; two-look tracking for venue lighting; full screen; screenshots and recording; wall versioning.
- **Motion tracking with audio** (`track`, 6 Nov): MediaPipe hand tracking mapped into wall centimetres, sounds for right/wrong order, the camera's guess of sent / tried / fail. Tested with a scripted hand and the real model on an empty frame; **not yet tested with a real person or the wooden mannequin.**
- **Logbook** (`log`, 6 Nov): route + result (sent / tried / fail) + date, typed or from `track --climber`; "N people climbed this" counted from it. Stored per person under `logbook/`, out of git.
- **Progress and recommendations** (`progress`, `recommend`, 6 Nov): skills for Lena, levels without grade points for Max, sessions against the therapist's goal for Laura; milestones; rule-based "you rarely climb pinches" recommendations that can generate the routes. `generate` and `build` take an optional `--by`.
- **Profile** (`profile`, 6 Nov): goal, language, level, height, age group, visibility with stricter rules for minors and health data, therapist-set rehab settings, delete one person from everything. Local files only; accounts still need a server.
- **Safety card and route filters** (`safety`, `routes`, 6 Nov): a 7-line card in English or German, shown once per climber and wall; the boulder list filtered by skill, grade, holds, made by, setter, not yet sent, within reach, with "N climbed".
- **Challenges** (`challenge`, 6 Nov): invite someone on the same laptop to a route; done when they send it or give it a real try; both get a milestone and points; no deadline; minors can't be sent routes past their reach. Sending between phones needs the server.
- **Phone as camera, live** (`serve` + `/live`, 6 Nov): local HTTPS server, the phone streams frames, the laptop tracks and answers with ring positions. Tested headlessly with synthetic frames and in headless Chromium with a fake camera; **not yet on a real phone.**
- **One phone page, three tabs** (6 Nov, after the first try on a phone): `serve` prints one link. The scan photo is now taken inside the page (the first version opened the phone's camera app and then got stuck after the photo on a real phone; not reproducible in Chromium, so the camera-app step was removed). Errors on the phone are printed in the laptop terminal.
- **Phone scan** (`/scan`, 6 Nov): photo, 4 corners or markers, size, holds and types on the phone, saved through the same `save_scan` as the CLI. Tested headlessly and in headless Chromium; not yet on a real phone.
- **Phone track** (`/track`, 6 Nov): record my try from the phone; MediaPipe on the laptop, sounds on the phone with Web Audio, the result into the logbook. Tested headlessly with a scripted hand and in headless Chromium with the real model (no person in the test video); **not yet with a real climber.**
- **Tests:** selftest and the rehearsal (115 checks, 116 with MediaPipe), all passing.
- **Demo script:** DEMO.md.

## Not yet tested

- A real webcam and real windows on Windows.
- The ArtRock test panel under the venue's lighting.
- Run `scan` on the panel first thing on day two.

## Open questions

- **Panel size.** Measure it once for the scale.
- **Wall angle.** Does ArtRock's panel or product adjust its angle? If yes, hold positions move with it.
- **Hold data.** Do ArtRock route setters design walls digitally? A CAD file would replace manual hold tapping.
- **Platform.** Would ArtRock own the app, or plug into an existing platform? After the Kilter–Aurora split, this matters.
- **Business model.** Gyms per wall, therapists per practice, or bundled with walls?
- **Motion tracking owner.** A minimal version is built (`track`); someone still needs to own testing it on the mannequin and tuning the 12 cm / 0.4 s touch rule.

## Next steps

### Group 1 (wall and boulders)

- Scan the real panel, generate routes, record a demo video.
- Update the canvas: add a hold-tapping screen, rename "Tap fixed points" to "Tap the four corners", design the Build tab.
- Done (6 Nov): `scan --width --height` options, so no typing is needed during the scan.
- Done (6 Nov): safety card (`safety`) and list filters (`routes`). Later: GPS wall list, community grading, the card in `live` (left out on demo day so `live` stays exactly as rehearsed).

### Group 2 (training and progress)

- Done (6 Nov): logbook format and `log` command (06-architecture.md). Still open: calibrating grades from it.
- Done (6 Nov): rule-based recommendations reusing the generator (`recommend`), progress per persona (`progress`): levels (Max), rehab goals (Laura), skills (Lena). Rules in 06-architecture.md. Still open: a coach-plan format, and the dashboard screen on the canvas.

- Done locally (6 Nov): challenges (`challenge`) — "how do you challenge someone and what do you win": you invite, they try, you both win. Still open: the "send a challenge" screen, and real rewards (sponsors) that don't favour difficulty.

### Group 3 (community and app basics)

- Done locally (6 Nov, `profile`): sign-up asks for goal (Play / Rehab / Train), language, level and height — height feeds `recommend`; visibility private / friends / public with stricter rules for minors and health data; delete one person. Still open: real accounts and sign-in (server), and parental consent as a real flow, not a flag.
- Duplicate walls: merge by gym and location.

### Motion tracking with audio — minimal version built (`track`)

- MediaPipe Pose on the recorded or live frame; map wrists and ankles through the same homography into wall coordinates; a hold is "touched" when a hand stays within a few centimetres of it.
- Audio: a positive sound for the next hold in order, an alert for an off-route hold.
- Built: everything above. Next: test on the wooden mannequin from the test rig and tune the touch rule.
- Keep it minimal and pitch a ClimbAI partnership for deep analysis.

## Moving beyond the hackathon

**Decided 6 Nov (Emilio): the phone becomes the camera, through a local server on the laptop.** `python ascent.py serve` runs an HTTPS server on the laptop (standard library only); the phone opens a page, sends camera frames over the Wi-Fi, and the laptop runs the same tracker and sends back where to draw the rings. This is a step towards the smartphone prototype, not the platform decision below: there is still no app, no cloud and no shared database.

If the project continues, the first deliberate decision is the platform: a phone app (for example Flutter or React Native with an on-device vision library) talking to a shared backend for walls and routes. The wall and route formats in 06-architecture.md are a reasonable starting schema. Until that decision is made, keep the prototype one Python file, as CLAUDE.md says.
