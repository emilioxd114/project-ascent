// "See a route": the live overlay. Frames go to the laptop, rings come back.
"use strict";
(() => {
  const $ = id => document.getElementById("live-" + id);
  const video = $("video"), canvas = $("canvas");
  let sid = null, running = false, lastAnswerAt = 0, wake = null;

  function showInfo(info) {
    const skills = (info.train || []).join(", ") || info.made_by || "";
    $("detail").textContent = `${info.route}  ${info.grade} (estimated)  ${info.holds} holds  ${skills}` +
      (info.warnings && info.warnings.length ? "  ! " + info.warnings[0] : "") +
      (info.old_version ? "  (made on an older version of the wall)" : "");
  }

  function showAnswer(a) {
    const st = $("state");
    if (a.state === "locked") { st.textContent = "Locked"; st.className = "state locked"; }
    else { st.textContent = a.message; st.className = "state warn"; }
    Ascent.drawRings(canvas, video, a);        // draws nothing unless locked
    lastAnswerAt = performance.now();
  }

  // Never leave old rings on screen: no fresh answer for 0.6 s means nothing is drawn.
  setInterval(() => { if (running && performance.now() - lastAnswerAt > 600) Ascent.fitCanvas(canvas); }, 200);

  async function loop() {
    while (running) {
      const t0 = performance.now();
      const blob = await Ascent.grabFrame(video);
      if (blob && running) {
        try {
          showAnswer(await Ascent.api("/api/frame", blob, { sid }));
        } catch (e) {
          $("state").textContent = e.message; $("state").className = "state warn";
          Ascent.fitCanvas(canvas);
          if (/Session ended/.test(e.message)) { stop(); break; }
          await Ascent.sleep(500);
        }
      }
      await Ascent.sleep(Math.max(0, 125 - (performance.now() - t0)));   // at most 8 frames a second
    }
  }

  function stop() {
    running = false;
    Ascent.stopCamera(video);
    Ascent.fitCanvas(canvas);
    if (wake) { wake.release().catch(() => {}); wake = null; }
    $("cam").classList.add("hidden");
    $("setup").classList.remove("hidden");
    Ascent.fullscreen(false);
  }

  $("start").onclick = async () => {
    $("error").textContent = "";
    if (!$("wall").value) { $("error").textContent = "Scan a wall first (tab 'Scan a wall')."; return; }
    $("start").disabled = true;
    try {
      const info = await Ascent.api("/api/live/start", {
        wall: $("wall").value, route: $("route").value, train: $("train").value,
        level: $("level").value, moves: $("moves").value, height: $("height").value });
      sid = info.sid;
      showInfo(info);
      $("setup").classList.add("hidden");
      $("cam").classList.remove("hidden");
      Ascent.fullscreen(true);
      await Ascent.startCamera(video);
      wake = await Ascent.keepAwake();
      running = true;
      loop();
    } catch (e) {
      stop();
      $("error").textContent = e.message;
    }
    $("start").disabled = false;
  };

  async function routeButton(path, btn) {
    btn.disabled = true;
    try { showInfo(await Ascent.api(path, {}, { sid })); Ascent.fitCanvas(canvas); }
    catch (e) { $("detail").textContent = e.message; }
    btn.disabled = false;
  }
  $("new").onclick = () => routeButton("/api/route/new", $("new"));
  $("next").onclick = () => routeButton("/api/route/next", $("next"));
  $("stop").onclick = () => { stop(); Ascent.fillWalls($("wall"), $("route")).catch(e => { $("error").textContent = e.message; }); };

  Ascent.views.live = {
    enter(p) { Ascent.fillWalls($("wall"), $("route"), { wall: p.wall }).catch(e => { $("error").textContent = e.message; }); },
    leave() { if (running) stop(); },
  };
})();
