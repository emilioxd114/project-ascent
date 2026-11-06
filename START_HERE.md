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

This plays a whole session with scripted clicks, keys and a fake camera video: scan, generate with every filter, build, preview, live (including the g and n keys), markers mode, re-scanning, and locking in dim light, glare and a harsh spotlight. Plus motion tracking with a scripted hand. Plus the logbook, progress, recommendations, profiles, safety card, route filters and challenges. 77 checks (78 with MediaPipe installed), all passing.

- **Tested:** all of the logic above, and that the rings land on the holds (under 1 pixel of error on simulated video).
- **Not tested:** a real webcam, real windows on Windows, and the real panel in real light. Run `scan` early tomorrow so there's time to fix anything.

To replay a recording instead of the webcam: `python ascent.py live --wall panel --video clip.mp4`.

## Phone as camera (`serve`)

The laptop does the work; the phone is the camera and the screen. Install once (it only makes the certificate): `pip install cryptography`.

```
python ascent.py serve
```

It prints links like `https://192.168.1.23:8443/live?code=k7mz2p`. Type the whole link into the phone's browser (Safari on iPhone, Chrome on Android) - the code is part of it, and without it the page says "Ask for the link with the code". A new code is made every time you start `serve`; `--code` sets your own.

- **/scan** - scan a wall with the phone: name it, **Take photo** (whole wall in frame), tap the 4 corners, type width and height in cm (or leave the width empty to skip), tap every hold and its type, **Save wall**. Same result as `python ascent.py scan`, versions included: scanning an existing wall again makes a new version and archives the old one. Small holds: turn the phone sideways and pinch to zoom.
- **/track** - record my try from the phone: pick wall and route, optionally your name (then the result goes into your logbook), tap **Start camera and sound**, put the phone 3-4 m back. The phone beeps; **Finish** shows the camera's guess, **Try again** starts over. Needs MediaPipe on the laptop (see "Record my try" below); without it the page says so.
- **/live** - pick wall and route, tap **Start camera**, point at the wall. Rings appear only while the wall is matched. **New route** = the `g` key, **Next route** = `n`. Hold the phone sideways to fit a whole wall.

### Connecting phone and laptop

1. **Same Wi-Fi.** Phone and laptop must be on the same network.
2. **If the page doesn't load on the venue Wi-Fi**, the network probably stops devices from seeing each other (common on event and guest Wi-Fi). Use the phone's hotspot instead: iPhone: Settings > Personal Hotspot > Allow Others to Join; Android: Settings > Network > Hotspot. Join it with the laptop, then **restart `serve`** - it prints the new address (and makes a new certificate, so accept the warning again). The phone opens the link while being the hotspot itself; that works.
3. **The certificate warning (once per certificate).** The certificate is made by your laptop, not by a public authority, so the phone warns. It is safe to continue for this address:
   - **iPhone (Safari):** "This Connection Is Not Private" > **Show Details** > **visit this website** > **Visit Website** (confirm if asked). Then allow the camera when asked. Use Safari; if the camera stays black, Settings > Safari > Camera > Ask or Allow.
   - **Android (Chrome):** "Your connection is not private" > **Advanced** > **Proceed to 192.168.x.x (unsafe)**. Then **Allow** the camera.
4. **Windows firewall.** The first time `serve` runs, Windows asks whether Python may communicate on networks: tick **Private networks** and click **Allow access**. The network itself must be marked Private: Settings > Network & internet > Wi-Fi > your network > Network profile type > **Private** (do the same for the phone's hotspot). If you clicked Cancel earlier: Control Panel > Windows Defender Firewall > **Allow an app or feature through Windows Defender Firewall** > Change settings > tick **Private** next to Python (python.exe; add it with "Allow another app" if missing) > OK. On a Mac, click **Allow** when asked about incoming connections.

**Still nothing?** Check the address matches what `serve` printed now (IPs change between networks), that nothing else uses port 8443 (`--port 9443`), and try the hotspot. Frames are processed in memory on the laptop and never saved. If the phone is silent on /track: check the ring/silent switch (iPhone) and the media volume.

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

## Profiles (the sign-up, on this laptop)

```
python ascent.py profile --climber lena --goal train --level medium --height 165 --language de
python ascent.py profile --climber max --goal play --minor --height 150
python ascent.py profile --climber laura --goal rehab --therapist "Dr. Berger" --rehab-level easy --sessions-per-week 2
```

Goal **train** shows skills, **play** shows levels, **rehab** shows sessions against the therapist's goal. Height and level are used by `recommend`. Profiles are private by default; under-18s can't be public and need `--parental-consent` for friends. `profile` alone lists everyone; `profile --climber max --delete --yes` deletes everything stored about Max.

## Route list with filters, and the safety card

```
python ascent.py routes --wall panel --train sloper --grade 5a-6a
python ascent.py routes --wall panel --climber lena --new --within-reach
python ascent.py safety --language de
```

`routes` shows each route with grade, skills, who made it and how many people climbed it. Filters: `--train`, `--grade`, `--holds 4-6`, `--made-by generated|built`, `--by max`; with `--climber`: your result, `--new` (not sent yet) and `--within-reach`. The first time a climber opens a wall with `--climber`, the safety card appears once. `list` is unchanged.

## Progress and what to climb next

```
python ascent.py progress --climber lena
python ascent.py recommend --climber lena --wall panel --make 3
```

`progress` shows climbs, sends and, depending on the goal, skills (train), a level (play) or sessions per week against the therapist's goal (rehab), plus milestones. Choose the view with `--goal`, or set it once in the climber's profile. `recommend` says what to train next and why ("You rarely climb pinches"); `--make 3` generates three such routes. Add `--by lena` to `generate` or `build` to record who set a route.

## Challenges

```
python ascent.py challenge --climber max --to lena --wall panel --route r3 --message "your turn"
python ascent.py challenge --climber lena
```

The challenge is done as soon as Lena logs that route as **sent or tried** (with `log` or `track --climber lena`). Then both get the "Team player" milestone. No deadline; `--decline c1` is always fine. Under-18s can't be sent a route with a move past their reach. Works between profiles on this laptop; sending to someone else's phone needs the server.

## Re-scanning after a reset

Running `scan --wall panel` again makes version 2. Version 1, with its photo and routes, moves into `walls/panel/archive_v1`. Nothing is deleted.
