# 01 · Context

## The event

- **Tirol Hackathon 2026**, "Die digitale Transformation gemeinsam meistern", 5 Nov 09:00 – 6 Nov 20:00, Glashaus beim DEZ, Innsbruck.
- Organised on behalf of TIWAG with IV-Tirol and FabLab.Tirol; listed by the Career-Service of the University of Innsbruck.
- Strong emphasis on **design thinking**, using *The Design Thinking Toolbox* (Lewrick, Link, Leifer; Wiley 2020). Cycle: Understand → Observe → Point of View → Ideate → Prototype → Test.
- Twelve company challenges (CH-01 to CH-12). This project is **CH-12, Project Ascent**, for ArtRock.

## The company

**ArtRock Kletterwände Ges.m.b.H.** — Austrian manufacturer of climbing walls ("ART ROCK pure climbing"). It builds custom walls, not one standardised board, which matters for every technical decision in this project.

## The official challenge (CH-12)

> Digital climbing solutions have often required expensive LED systems or permanently installed projectors. These depend on room light and camera position and can be impaired by the shadow of the climber. The search is on for a smartphone-based prototype that recognises a climbing wall with the help of a few reference points, visualises climbing routes from different angles directly in the live camera image and enables initial approaches to motion tracking and interactive feedback.

Possible outcomes named: UX/UI prototype, AI or computer-vision concept, working proof of concept, first motion-tracking solution. Helpful skills: software development, AI/data science, computer vision, UX/UI, mobile development, mathematical modelling, motion tracking.

## The concept paper ("Smart Climbing Wall Calibration & Smartphone Motion Tracking")

**Objective:** a platform-independent prototype (iOS and Android) that shows climbing routes in the live camera feed without projectors or lighting systems, and measures and analyses movement.

**Core features asked for**

1. **User accounts and community database** — profiles; routes saved privately or shared.
2. **Photo setup and reference points** — photograph the wall or a section; manually define **3 to 4 reference points** for spatial and coordinate determination.
3. **Route editor** — select holds by clicking on the photo; **automatic ascending numbering (1, 2, 3 …)**; name and save the route.
4. **Real-time camera overlay** — reference points recognised automatically in the live feed; numbering tracked precisely on the real holds regardless of angle, distance or light.

**"The premier discipline": motion tracking and gamification**

- Full-body tracking of the climber's limbs without sensors.
- **Interactive audio feedback**: a positive signal when correctly reaching for the next hold in sequence; an alert on deviation or wrong order.
- Future: gamification, accessible sports, rehabilitation therapy.

**On-site test rig**

- A climbing wall panel with original holds in **black, yellow, blue, red and orange**.
- A **wooden mannequin** for reproducible limb-movement tests.

## What the CEO said (notes from the kick-off)

- One app that solves problems for several kinds of people, **usable anywhere**.
- Main features: database (save); photo setup — picture of an artificial **or real rock** wall → set route → live video on the phone → follow the route; **put the phone anywhere and it follows the route**; motion tracking for correct technique; user account.
- **Free app**, also for working with children, professionals, therapists, parties.
- Add-on: **smart glasses** experience.
- He wants fresh ideas from people outside climbing, not only climbers.

## What the reps clarified later

- **No gym-owner role.** Walls are added and maintained by ordinary users.
- The team debated whether walls should be added once by an owner or scanned every session because holds change. Resolution, now the project's position: **scan a wall once per version; every later session just points the camera; scan again only when the holds have changed** (see 04-product.md).

## The team

Nine people, no professional developers, working with AI-assisted coding. Work was split into three groups (see 04-product.md). Emilio Loredo (FH Kufstein, Smart Products & AI-driven Development) owns Group 1's first two features — scanning the wall and the live camera overlay — and the working prototype in this repository.
