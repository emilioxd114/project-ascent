# 08 · Status and next steps

Status as of the night of 5 Nov 2026, before the final day.

## Done

- **Research:** competitors, ClimbAI, the Kilter–Aurora split (03-market.md).
- **Users:** three personas with full canvases and critique (02-users.md).
- **Concept:** fundamental decisions, scope, roadmap (04-product.md).
- **Design:** nine phone screens on the canvas, in two rows (05-design.md).
- **Prototype** (`ascent.py`): scan with corners, scale, hold tapping and types; markers fallback; rules-based generator with reach guardrails and skill filters; build mode; live overlay with route switching and live generation; never guessing; two-look tracking for venue lighting; full screen; screenshots and recording; wall versioning.
- **Tests:** selftest and the 19-check rehearsal, all passing.
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
- **Motion tracking owner.** Still unassigned.

## Next steps

### Group 1 (wall and boulders)

- Scan the real panel, generate routes, record a demo video.
- Update the canvas: add a hold-tapping screen, rename "Tap fixed points" to "Tap the four corners", design the Build tab.
- Small code task: `scan --width --height` options so no typing is needed during the scan (a good first Claude Code exercise).
- Later: GPS wall list, safety card, community grading.

### Group 2 (training and progress)

- Logbook format: route + result (sent / tried / fail) + date; this feeds "N people climbed this" and calibrates grades.
- Rule-based recommendations reuse the route generator: "you rarely climb pinches" → `generate --train pinch`.
- Progress per persona: levels (Max), rehab goals (Laura), skills (Lena).

### Group 3 (community and app basics)

- Sign-up asks for goal (Play / Rehab / Train), language, level and height — height feeds the reach guardrail.
- Visibility model first: private / friends / public, with stricter defaults for minors and health data.
- Duplicate walls: merge by gym and location.

### Unassigned — motion tracking with audio

- MediaPipe Pose on the recorded or live frame; map wrists and ankles through the same homography into wall coordinates; a hold is "touched" when a hand stays within a few centimetres of it.
- Audio: a positive sound for the next hold in order, an alert for an off-route hold.
- Test on the wooden mannequin from the test rig.
- Keep it minimal and pitch a ClimbAI partnership for deep analysis.

## Moving beyond the hackathon

If the project continues, the first deliberate decision is the platform: a phone app (for example Flutter or React Native with an on-device vision library) talking to a shared backend for walls and routes. The wall and route formats in 06-architecture.md are a reasonable starting schema. Until that decision is made, keep the prototype one Python file, as CLAUDE.md says.
