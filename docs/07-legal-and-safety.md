# 07 · Legal and safety

Hackathon-depth notes, not legal advice. Anything that goes to production needs a lawyer.

## Data protection (GDPR / DSGVO)

The eight questions to ask of any feature:

1. Is there personal data here? (Video of a person always is.)
2. What is the legal basis — and why not consent? (Consent is revocable, and between employer and employee presumed not free.)
3. What was the data originally collected for? (*Zweckbindung* — no silent reuse.)
4. What is the minimum we need?
5. Does the machine alone decide something that affects a person? (Art. 22)
6. Can we delete one person from everything, including indexes and backups?
7. Who sees what, and can we prove it?
8. Where does the data live, and who else processes it? (Every external service needs a processing agreement.)

**What this means for Project Ascent**

- **Climbing videos show people** — the climber and bystanders. Process on the device, store derived coordinates rather than raw video, and film only consenting people in demos. Demo recordings are excluded from git for this reason (`.gitignore`).
- **Minors (Max):** parental consent; private by default; no public leaderboards with real names; care with any social features.
- **Rehab (Laura):** health data is the strictest category. Keep it separate, minimal, and under the therapist's control.
- **Wall photos** may contain people in the background; crop or blur before sharing.
- **Visibility settings** (private / friends / public) must exist before any sharing feature ships.

## EU AI Act

- The Digital Omnibus (Regulation (EU) 2026/1744, in force 27 July 2026) moved **high-risk obligations to 2 Dec 2027**. Art. 50 **transparency** obligations have applied since 2 Aug 2026; Art. 4 **AI literacy** also applies.
- **Emotion recognition in the workplace and in education is prohibited.** Never analyse a climber's mood or tone.
- The route generator is rules-based and explainable — it is not an AI system in the risky sense.
- A partnered movement-analysis feature must tell users that AI is involved (Art. 50).

## Medical device line (Laura)

The app must be **a tool the therapist uses**, never a system that tells a patient whether a movement is safe. Judging safety or prescribing treatment on its own risks classification as a medical device under EU rules.

## Climbing safety

- **Gamification must not push people to climb harder alone.** For minors especially: no streaks that punish rest days, no leaderboard by hardest grade. Reward consistency, routes created, routes repeated by others, technique.
- **Reach guardrails** stop the generator from proposing moves beyond the climber's reach.
- **The phone placement** must never be on the landing zone of the crash pad.
- **Wrong overlays are a safety issue too.** That's why the app draws nothing when unsure.
- **Safety guidelines** (Group 1 feature): show once, the first time someone opens a wall, as a short card — not a page nobody reads.

## Data ownership

Route databases and wall maps should belong to ArtRock contractually, even if a partner builds the app. See the Kilter–Aurora case in 03-market.md.
