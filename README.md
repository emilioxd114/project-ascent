# Project Ascent

Prototype for **ArtRock** at the Tirol Hackathon 2026: a camera draws climbing routes onto a real wall, live, without LED systems or projectors.

- **Scan** a wall once: photo, 4 corners, real size, tap and tag the holds.
- **Generate** routes by rules (no AI), always within the climber's reach, filtered by what you want to train.
- **Climb**: numbered rings stay on the real holds as the camera moves. If the wall can't be matched, the app says which way to move instead of guessing.

```
pip install -r requirements.txt
python ascent.py selftest
```

How to run everything: [START_HERE.md](START_HERE.md). Pitch demo script: [DEMO.md](DEMO.md). Context for Claude Code: [CLAUDE.md](CLAUDE.md). Fallback markers to print at 100%: [print/aruco_markers_A4.pdf](print/aruco_markers_A4.pdf).

Scanned walls are saved in `walls/` and committed, so every laptop on the team can use the same scan.
