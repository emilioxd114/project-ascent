# Project Ascent — prototype, start here

Presenting? The on-stage script is in [DEMO.md](DEMO.md).

One Python file, runs on a laptop with its webcam. No app, no server, no internet.

## 1. Install (5 minutes, do it tonight)

```
pip install opencv-contrib-python numpy
python ascent.py selftest
```

It must be `opencv-contrib-python`, not `opencv-python`: the marker detection only exists in the contrib package.

`selftest` needs no camera. It builds a fake wall, looks at it from another angle and checks the overlay lands on the holds. You want to see `OK - the install works.`

## 2. Tomorrow morning, at the ArtRock test panel (about 30 minutes)

**Scan the panel once**

```
python ascent.py scan --wall panel
```

1. Webcam opens. Stand back until the whole panel is in frame, then press **SPACE**.
2. Click the 4 corners of the climbing area: top-left, top-right, bottom-right, bottom-left. Press **Enter**.
3. In the console window, type the distance between the two top corners in cm, then the two left corners. Measure the panel once with a tape. Press Enter to skip, but then reach checks are only approximate. Or give the sizes up front and skip the typing: `python ascent.py scan --wall panel --width 300 --height 220` (your measured cm).
4. Click every hold. After each click you can press **j c s p k** to tag it jug / crimp / sloper / pinch / pocket. Tag at least a few slopers if you want to demo the sloper filter. Press **Enter**.

**Make a route**

```
python ascent.py generate --wall panel --train reach --preview
python ascent.py generate --wall panel --train sloper --level easy --preview
python ascent.py build --wall panel
```

`generate` uses rules, not AI: it only chooses moves within reach (55% of the climber's height, default 172 cm), always going up, or sideways with `--train traverse`. `build` lets you click your own holds in order and warns you about moves that are too long.

**See it on the wall**

```
python ascent.py live --wall panel --route r1
```

Move the laptop around. The numbered rings should stay on the holds. If they don't, the screen says which way to move instead of guessing.

Keys: **g** generate a new route on the spot, **n** next saved route, **f** full screen (for the projector), **s** screenshot, **v** start/stop recording a video, **q** quit.

`--route` is optional: without it, `live` shows the newest route. To control what **g** generates, add the same options as `generate`, for example `--train sloper --moves 5`.

**The demo moment:** `python ascent.py live --wall panel --train sloper`, point at the panel, press **g**. A new sloper route appears on the real holds.

## 3. Record the demo the moment it works

Press **v** in `live`, move the camera slowly for 20 seconds, press **v** again. That video is your insurance if the live demo fails on stage.

## 4. If the overlay is unstable on the panel

The panel may have too little texture for photo matching. Switch to the printed markers (PDF from earlier, print at 100%):

1. Tape one marker near each corner of the panel, flat.
2. `python ascent.py scan --wall panel --markers`. The corners are found automatically, so you only tap holds.
3. `python ascent.py live --wall panel --route r1`

At least two markers must be visible during `live`.

## 5. If the camera fails completely

```
python ascent.py preview --wall panel --route r1
```

This draws the route on the saved photo. Combined with the recorded video and the design canvas, it's still a complete story.

## What is tested and what is not

```
python tests/rehearsal.py
```

This plays a whole session with scripted clicks, keys and a fake camera video: scan, generate with every filter, build, preview, live (including the g and n keys), markers mode, re-scanning, and locking in dim light, glare and a harsh spotlight. Plus motion tracking with a scripted hand. Plus the logbook. 33 checks (34 with MediaPipe installed), all passing.

- **Tested:** all of the logic above, and that the rings land on the holds (under 1 pixel of error on simulated video).
- **Not tested:** a real webcam, real windows on Windows, and the real panel in real light. Run `scan` early tomorrow so there's time to fix anything.

To replay a recording instead of the webcam: `python ascent.py live --wall panel --video clip.mp4`.

## Record my try (motion tracking with sounds)

Needs MediaPipe once: `pip install mediapipe`. Everything else works without it.

```
python ascent.py track --wall panel --route r1
```

Put the laptop 3-4 m back with the whole panel in frame, never on the landing zone. Climb the route: a high beep for each hold reached in order, a low buzz for a hold that is not on the route, a double beep for out of order, a little tune at the top. At the end it prints the camera's guess (sent / tried / fail). Keys: **m** sound on/off, **q** stop. `--mute` for no sound, `--video clip.mp4` to replay a recording.

The first run downloads a 5.5 MB pose model into `models/` - do it once while there is wifi. No video is saved. Installing MediaPipe can also update OpenCV, so on demo day install it after the pitch, or in a separate virtual environment.

Add `--climber lena` to save the attempt in Lena's logbook.

## Logbook

```
python ascent.py log --climber lena --wall panel --route r1 --result sent
python ascent.py log --climber lena
```

Results: **sent** (reached the top in order), **tried** (got past the start), **fail** (didn't get going). Add `--note "slipped off 4"` or `--date 2026-11-02`. `--undo` removes the last entry. Logbooks are personal data: they stay in `logbook/` on this laptop and are not pushed to GitHub.

## Re-scanning after a reset

Running `scan --wall panel` again makes version 2. Version 1, with its photo and routes, moves into `walls/panel/archive_v1`. Nothing is deleted.
