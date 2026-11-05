# Project Ascent — context for Claude Code

Hackathon prototype for ArtRock (climbing walls), Tirol Hackathon, 5–6 Nov 2026. Demo is on Friday 6 Nov.

## What it does

A laptop webcam looks at a climbing wall and draws a climbing route (numbered rings) onto the real holds, live. It replaces expensive LED systems with a camera.

Everything lives in `ascent.py`. Read `START_HERE.md` for commands.

- `scan`: photo of the wall, user clicks the 4 corners, types the real size in cm, clicks and tags every hold. Saves `walls/<name>/wall.json` and `ref.jpg`.
- `generate`: rules-based route generator, no AI. Moves within reach (0.55 × height), going up, or sideways for traverse. Skill filters: reach, traverse, and the hold types tagged by hand.
- `build`: user clicks holds in order. Warns about moves that are past reach.
- `live`: SIFT feature matching between the saved photo and the camera, then a RANSAC homography. Draws white-haloed rings. When it can't lock it says "move closer" or "step back", and it never draws a guessed overlay.
- `--markers`: fallback using printed ArUco markers (DICT_4X4_50, IDs 0–3) instead of photo matching.
- Re-scanning archives the old version in `walls/<name>/archive_vN`. Nothing is deleted.

## Rules for changing this code

- Keep it ONE Python file. No frameworks, no web app, no mobile build, no database. OpenCV + numpy only.
- Make small changes, then run them. Run `python ascent.py selftest` after any change to tracking code.
- Keep printed and on-screen strings ASCII-only. The OpenCV text renderer and some Windows consoles can't show other characters.
- Don't change `wall.json` and route file formats without a reason. Existing scans must keep working.
- Never draw an overlay when the wall is not locked. Showing nothing is better than a wrong overlay.
- The generator stays rules-based. Do not add an AI model to it.
- The team is not professional developers. Explain every change in plain language.

## Known gaps

- The click windows and the live webcam were not tested before the event. Test them first.
- Photo matching may struggle on a low-texture panel. Switch to `--markers` if so.
- Grades are estimates from move length, shown with a `~`.
