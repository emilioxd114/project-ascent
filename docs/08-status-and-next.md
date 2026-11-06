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
- **Tests:** selftest and the rehearsal (56 checks, 57 with MediaPipe), all passing.
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
- Later: GPS wall list, safety card, community grading.

### Group 2 (training and progress)

- Done (6 Nov): logbook format and `log` command (06-architecture.md). Still open: calibrating grades from it.
- Done (6 Nov): rule-based recommendations reusing the generator (`recommend`), progress per persona (`progress`): levels (Max), rehab goals (Laura), skills (Lena). Rules in 06-architecture.md. Still open: a coach-plan format, and the dashboard screen on the canvas.

### Group 3 (community and app basics)

- Done locally (6 Nov, `profile`): sign-up asks for goal (Play / Rehab / Train), language, level and height — height feeds `recommend`; visibility private / friends / public with stricter rules for minors and health data; delete one person. Still open: real accounts and sign-in (server), and parental consent as a real flow, not a flag.
- Duplicate walls: merge by gym and location.

### Motion tracking with audio — minimal version built (`track`)

- MediaPipe Pose on the recorded or live frame; map wrists and ankles through the same homography into wall coordinates; a hold is "touched" when a hand stays within a few centimetres of it.
- Audio: a positive sound for the next hold in order, an alert for an off-route hold.
- Built: everything above. Next: test on the wooden mannequin from the test rig and tune the touch rule.
- Keep it minimal and pitch a ClimbAI partnership for deep analysis.

## Moving beyond the hackathon

If the project continues, the first deliberate decision is the platform: a phone app (for example Flutter or React Native with an on-device vision library) talking to a shared backend for walls and routes. The wall and route formats in 06-architecture.md are a reasonable starting schema. Until that decision is made, keep the prototype one Python file, as CLAUDE.md says.
