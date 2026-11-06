# 05 · Design

The phone screens live on a Design canvas in Claude: **Project Ascent — scan and overlay**, https://claude.ai/artifact/6YLvHb998gsZ7uGR7NVkBB (private to Emilio until shared). Phone frames are 390×844.

## The flow

**Top row — every visit:**

1. **Pick a wall** — walls at your gym, each with version, number of routes and who scanned it. "Wall not listed? Scan it."
2. **Choose a route** — tabs Routes / Generate / Build; filter by what to train (reach, slopers, crimps, footwork, traverse) and grade; each route shows grade, skills, who set it and how many climbed it.
2b. **Generate one** — choose skills, grade, number of moves, your height; preview on the wall with a guardrail warning ("Move 4 → 5 is 14 cm past your reach — Swap 5"); Shuffle or Climb it.
3. **Climb it** — the route drawn on the live camera, "Locked", legend, "Record my try" and "Got it".

**Bottom row — the exceptions:**

- Under step 1, **first time at a wall:** A frame the wall (live checks: whole wall in frame, holding steady, enough light) → B tap fixed points → C name, scale, save (with the reset explanation). Then back to step 2.
- Under step 3, **when the camera can't lock:** "Move closer" (or "Step back"); after repeated failures, "Has this wall been reset?" with "Scan a new version" / "Try again".

## Design decisions

- **Dark, camera-first interface.** The route colours are the only colour in the design, so they stand out on the camera feed.
- **Route colours follow the LED-board convention:** green start, blue middle, red finish.
- **Numbers, not just highlights** — the concept paper asks for ascending numbering.
- **Rings around holds, not dots on them.** A ring a few centimetres off still reads correctly; a dot looks broken.
- **Every ring has a white halo and a dark edge.** The test panel has black, yellow, blue, red and orange holds; a plain blue ring on a blue hold disappears.
- **Never guess.** If the app isn't sure, it draws nothing and says which way to move. There are two failure directions — too far (points too small) and too close (points out of frame) — and the message must match.
- **The app never decides a reset on its own.** It asks after repeated failed matches.
- **"Got it — put the phone down."** The overlay screen is for memorising, then putting the phone away.
- **Colour is never the only signal.** Numbers carry the order (1 = start, last = finish), which also covers colour-blind climbers (green vs red).

## Known gaps in the design (from the design review)

1. **Hold tapping is missing from the canvas.** The scan flow captures reference points but has no screen where holds are tapped and tagged by type. The prototype has it; the canvas doesn't yet.
2. **The Build tab has no screen.**
3. **"Tap fixed points" should be "tap the four corners".** The prototype uses the corners of the climbing area plus a measured size; tracking uses the whole photo, not individual bolts or edges.
4. **Sloper/crimp filters need hold types**, which only exist if holds are tagged during the scan.
5. **"Record my try" needs a placement step** — the phone must be 3–4 m back with the whole wall in frame.
6. **The scale field asks for a tape measure.** Make it skippable ("Skip — no reach check").
7. **Generated grades must read "≈6a (estimated)".**
8. **Audio feedback has no screen anywhere.** The prototype's `track` window is a starting point: "Next: hold N of M", a green dot on each hold reached, a short message with every sound.
9. **Dependencies on other groups:** height (profile, Group 3), "41 climbed" (logbook, Group 2), "You are here" (GPS). Each needs a demo fallback.

## Other artifacts

- **DSGVO + AI Act checklist** (preparation document): https://claude.ai/artifact/M4ZEAW9FAUAErhn4rtNFZD
- **Competitive landscape:** https://claude.ai/artifact/L8vz87bzwF1cDcTbsZ7RSy
- **How 9 people build this in 14 hours** (team organisation): https://claude.ai/artifact/BVPXbfKxorkFKcjztcjiok

All private to Emilio until he shares them.
