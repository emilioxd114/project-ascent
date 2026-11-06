// "Record my try": hand tracking on the laptop, sounds on the phone.
"use strict";
(() => {
  const $ = id => document.getElementById("track-" + id);
  const video = $("video"), canvas = $("canvas");
  let sid = null, running = false, lastAnswerAt = 0, wake = null, audio = null, soundOn = true, t0 = 0, safetyShown = false;

  // The same four tones as the laptop's 'track' command, made with Web Audio.
  const TONES = { good: [[880, 0.09], [1320, 0.12]], order: [[520, 0.12], [520, 0.12]],
                  off: [[220, 0.35]], top: [[660, 0.1], [880, 0.1], [1320, 0.25]] };
  function play(kind) {
    if (!soundOn || !audio || !TONES[kind]) return;
    let t = audio.currentTime + 0.01;
    for (const [f, d] of TONES[kind]) {
      const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = f; o.type = "sine";
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.5, t + 0.01);
      g.gain.setValueAtTime(0.5, t + d - 0.01);
      g.gain.linearRampToValueAtTime(0, t + d);
      o.connect(g).connect(audio.destination);
      o.start(t); o.stop(t + d + 0.02);
      t += d + 0.03;
    }
  }

  let flashUntil = 0;
  function flash(text, good) {
    $("flash").textContent = text;
    $("flash").style.color = good ? "var(--green)" : "var(--amber)";
    flashUntil = performance.now() + 1500;
  }

  function showAnswer(a) {
    const st = $("state");
    if (a.state === "locked") {
      st.textContent = a.next < a.of ? `Locked - next: hold ${a.next + 1} of ${a.of}` : "Top reached";
      st.className = "state locked";
    } else { st.textContent = a.message; st.className = "state warn"; }
    const d = Ascent.drawRings(canvas, video, a);   // draws nothing unless locked
    if (d && a.rings) {
      a.rings.slice(0, a.next).forEach(r => {          // a green dot on each hold reached in order
        const [x, y] = d.map(r.x, r.y);
        d.ctx.fillStyle = Ascent.COLORS.start;
        d.ctx.beginPath(); d.ctx.arc(x, y, 7, 0, 2 * Math.PI); d.ctx.fill();
      });
      (a.hands || []).forEach(h => {
        const [x, y] = d.map(h.x, h.y);
        d.ctx.lineWidth = 2; d.ctx.strokeStyle = Ascent.COLORS.white;
        d.ctx.beginPath(); d.ctx.arc(x, y, 9, 0, 2 * Math.PI); d.ctx.stroke();
      });
    }
    for (const e of a.events || []) { play(e.sound); flash(e.message, e.sound === "good" || e.sound === "top"); }
    if (performance.now() > flashUntil) $("flash").textContent = "";
    lastAnswerAt = performance.now();
  }

  setInterval(() => { if (running && performance.now() - lastAnswerAt > 600) Ascent.fitCanvas(canvas); }, 200);

  async function loop() {
    while (running) {
      const start = performance.now();
      const blob = await Ascent.grabFrame(video);
      if (blob && running) {
        try {
          const t = ((start - t0) / 1000).toFixed(3);    // when this frame was taken
          showAnswer(await Ascent.api("/api/frame", blob, { sid, t }));
        } catch (e) {
          $("state").textContent = e.message; $("state").className = "state warn";
          Ascent.fitCanvas(canvas);
          if (/Session ended/.test(e.message)) { stop(); break; }
          await Ascent.sleep(500);
        }
      }
      await Ascent.sleep(Math.max(0, 125 - (performance.now() - start)));
    }
  }

  function stop() {
    running = false;
    Ascent.stopCamera(video);
    Ascent.fitCanvas(canvas);
    if (wake) { wake.release().catch(() => {}); wake = null; }
    $("summary").classList.add("hidden");
    $("cam").classList.add("hidden");
    $("setup").classList.remove("hidden");
    $("start").textContent = "Start camera and sound";
    Ascent.fullscreen(false);
  }

  $("start").onclick = async () => {
    $("error").textContent = "";
    if (!$("route").value) { $("error").textContent = "Choose a route (make one on 'See a route')."; return; }
    // Sound must be switched on by a tap (iPhone rule), so it starts here.
    try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); await audio.resume(); play("good"); }
    catch (e) { audio = null; }
    $("start").disabled = true;
    try {
      const info = await Ascent.api("/api/track/start", {
        wall: $("wall").value, route: $("route").value, climber: $("climber").value.trim() });
      sid = info.sid;
      if (info.safety && !safetyShown) {
        // First time on this wall: the safety card, once.
        $("safety").textContent = info.safety.join("\n");
        $("safety").classList.remove("hidden");
        safetyShown = true;
        $("start").textContent = "I've read it - start";
        $("start").disabled = false;
        return;
      }
      $("detail").textContent = `${info.route}  ${info.grade} (estimated)  ${info.holds} holds` +
        (info.climber ? `  - saving for ${info.climber}` : "");
      $("setup").classList.add("hidden");
      $("cam").classList.remove("hidden");
      Ascent.fullscreen(true);
      await Ascent.startCamera(video);
      wake = await Ascent.keepAwake();
      t0 = performance.now();
      running = true;
      loop();
    } catch (e) {
      stop();
      $("error").textContent = e.message;
    }
    $("start").disabled = false;
  };

  $("sound").onclick = () => { soundOn = !soundOn; $("sound").textContent = soundOn ? "Sound on" : "Sound off"; };
  $("again").onclick = async () => {
    try { await Ascent.api("/api/track/reset", {}, { sid }); $("summary").classList.add("hidden"); flash("Go again", true); }
    catch (e) { flash(e.message, false); }
  };
  $("finish").onclick = async () => {
    try {
      const s = await Ascent.api("/api/track/finish", {}, { sid });
      let text = `Reached ${s.reached} of ${s.of} holds in order.`;
      if (s.skipped.length) text += ` Skipped: ${s.skipped.length}.`;
      if (s.off_route.length) text += ` Off-route holds: ${s.off_route.length}.`;
      text += `\nThe camera's guess: ${s.result}. You know better - it is only a suggestion.`;
      if (s.logged) text += `\nSaved in ${s.climber}'s logbook. Wrong? On the laptop: python ascent.py log ` +
                            `--climber ${s.climber} --undo`;
      (s.challenges || []).forEach(c => { text += "\n" + c + " - Team player!"; });
      $("summary").textContent = text;
      $("summary").classList.remove("hidden");
      if (s.result === "sent") play("top");
    } catch (e) { flash(e.message, false); }
  };
  $("stop").onclick = stop;

  Ascent.views.track = {
    enter() { Ascent.fillWalls($("wall"), $("route"), { needRoute: true }).catch(e => { $("error").textContent = e.message; }); },
    leave() { if (running) stop(); },
  };
})();
