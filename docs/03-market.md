# 03 · Market and competitors

Researched on 5 Nov 2026. Prices and ratings change; re-check before using them in a pitch.

## Four groups, one empty square

| Group | Examples | How routes are shown | Knows the wall? | Watches the climber? | Cost |
| --- | --- | --- | --- | --- | --- |
| LED system boards | Kilter, Grasshopper, Tension, MoonBoard | LEDs in or around the holds | Yes, one fixed worldwide layout | No | ~$13,750 for a Grasshopper 8x10 wall + LEDs |
| Photo apps | Stōkt, Crux, Sprai, Retro Flash | Static photo on the phone | Roughly — holds marked on an image | No | Stōkt $35–100 per wall, Pro $20/month |
| Projector | Any Climb | Cast to Chromecast or Apple TV | No | No | Price of a projector |
| Video analysis | ClimbAI (ALNEVIS) | Not at all | No | Yes, in depth | Free for now |
| **Live overlay on custom walls** | **— nobody —** | **Drawn on the real wall, live** | **Yes** | **Potentially** | **A phone** |

## LED system boards

- Kilter and Grasshopper are both **LED system boards whose apps are made by Aurora Climbing**, which also makes the apps for Tension, Decoy and others. They are two walls on one software platform.
- They work because **every board in the world has the same hold layout**, so a route set in Tokyo works in Innsbruck. ArtRock builds custom walls, so this trick is not available to it — which is why fast wall mapping is the core technical problem here.
- Holds light up over Bluetooth with a colour convention climbers know. Grasshopper: green start, blue middle, red finish, magenta foot-only. Kilter: green start, cyan middle, magenta finish, yellow foot-only. This project uses green, blue and red.
- The incumbent apps are poorly rated: MoonBoard and the new Kilter app around 1.5 stars; Tension 3.6.

### The Kilter–Aurora split (March 2026)

Aurora ran the Kilter app under a verbal agreement since 2018. After a trademark cease-and-desist, Aurora shut the server down on 26 March 2026 and pulled the app; **twelve years of users' logged ascents vanished overnight**. Kilter shipped a replacement within hours, rated about 1.5 stars. A Colorado court dismissed Kilter's suit on 30 March for lack of jurisdiction; Aurora's case in British Columbia continues.

**Lesson for ArtRock:** a wall maker whose customer experience lives in someone else's software can be switched off. ArtRock should own the data layer — routes and wall maps — even if the app itself is built by a partner.

## Photo apps

Closest to this project. You photograph the wall, holds are detected or marked, and routes are drawn **on the photo**. You then look up at the real wall and translate in your head. None of them draws on the live camera view, and none watches the climb.

- **Stōkt:** 4.8 stars on iOS (about 950 ratings), 3.55 on Google Play; per-wall pricing, wall processing by the company.
- **Crux:** free for home walls, $8 per wall per month or $40 per gym per month; automatic scanning, accuracy criticised.

## Projector

**Any Climb:** routes cast to a projector through Chromecast or Apple TV. Cheap, but it has the problems the ArtRock brief names: shadows and dependence on room light.

## ClimbAI by ALNEVIS — the important one

- **ALNEVIS S.R.L.**, Bolzano, about 100 km from Innsbruck. Founder Edoardo Bianchi, computer-vision researcher at the Free University of Bozen-Bolzano.
- Published research behind it: SkillFormer (International Machine Vision Conference 2025), PATS (IEEE Sport Technology and Research Workshop 2025), ProfVLM (arXiv, Sept 2025), Gate-Shift-Pose (WACV 2025 workshops). Evaluated on EgoExo4D, which includes bouldering.
- Product: record a bouldering attempt with a phone, get a technique report in about a minute — joint angles, centre of gravity, sway, efficiency, phase splits, attempt comparison, progress score, chat. Works on Kilter, MoonBoard and spray walls. 700+ registered climbers; demoed at Rock Master 2026. Free to try.
- **What it doesn't do:** it knows nothing about the wall. No hold positions, no routes, no live overlay, no route setting.

**Consequences for this project**

1. **Don't build deep motion analysis.** A weekend version next to a research-backed product looks thin.
2. **Make the wall layer the centrepiece.** Hold maps, routes and live registration are unoccupied — and a wall manufacturer is uniquely placed to own them.
3. **Treat ClimbAI as a partner.** It owns the body, ArtRock the wall. Together they can say *"you held hold 14 for four seconds with a bent arm"*, which neither can alone.
4. It's evidence the market is real.

## Sources

- Tirol Hackathon listing: https://www.uibk.ac.at/de/events/2026/11/tirol-hackathon/
- Kilter app: https://www.appbrain.com/app/kilter-board/com.auroraclimbing.kilterboard
- Kilter board: https://kilter-grips.myshopify.com/pages/about-the-kilter-board
- Board apps compared and the Kilter–Aurora split: https://ownclimb.com/blog/board-climbing-apps-compared
- Grasshopper app: https://play.google.com/store/apps/details?id=com.auroraclimbing.grasshopperboard
- Grasshopper review: https://www.climbing.com/gear/review-grasshopper-board-climbing-training-wall/
- Grasshopper price listing: https://offerup.com/item/detail/881bff00-2c0a-37f9-afc4-246412f5ac90
- Stōkt: https://apps.apple.com/us/app/st%C5%8Dkt/id1436843282
- Any Climb: https://mwm.ai/apps/any-climb/6758150155
- ClimbAI: https://climbai.app/ · ALNEVIS: https://alnevis.com/
- ProfVLM paper: https://arxiv.org/abs/2509.26278 · SkillFormer: https://edowhite.github.io/SkillFormer
