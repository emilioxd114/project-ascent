// "Climb": the whole flow on the phone, nothing typed, nothing measured.
//   photo -> the laptop finds the wall and the holds -> "Looks good" -> a route for a skill, drawn on the
//   photo (or tapped in by hand, or edited) -> "Use this route" -> phone down, live rings, sounds.
// The laptop does the vision work (the same code as scan --auto, generate, build and track).
"use strict";
(() => {
  const $ = id => document.getElementById("flow-" + id);
  const view = $("view"), ctx = view.getContext("2d"), video = $("video"), canvas = $("canvas");
  const sounds = Ascent.makeSounds();
  const NAMES = ["top-left", "top-right", "bottom-right", "bottom-left"];
  let step = "start", walls = [];
  // the scan
  let photo = null, dataUrl = null, found = null, corners = [], holds = [], taps = [], how = null;
  // the wall and the route
  let wallName = null, wallPhoto = null, wallHolds = [], route = null, routeHow = "generated", skill = "reach";
  let savedRoute = null;
  // climbing
  let sid = null, running = false, lastAnswerAt = 0, wake = null, t0 = 0, tap = null, flashUntil = 0;
  let learned = false, touch = "sticker";

  function show(id) {
    ["s-start", "s-holds", "s-route", "s-climb"].forEach(s => $(s).classList.toggle("hidden", s !== id));
    view.classList.toggle("hidden", !(id === "s-holds" || id === "s-route"));
  }
  function status(text) { $("status").textContent = text || ""; $("status").classList.toggle("hidden", !text); }
  function fail(msg) { status(""); $("error").textContent = msg; }
  function clearError() { $("error").textContent = ""; }
  const holdById = id => wallHolds.find(h => h.id === id);

  // ------------------------------------------------------------------ drawing on the photo
  function drawPhoto(img) {
    ctx.drawImage(img, 0, 0, view.width, view.height);
  }
  function holdRing(x, y, r, k, color, label) {
    ctx.lineWidth = 6 * k; ctx.strokeStyle = Ascent.COLORS.dark;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.lineWidth = 3 * k; ctx.strokeStyle = color;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
    if (label) {
      ctx.font = `bold ${13 * k}px system-ui`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.lineWidth = 4 * k; ctx.strokeStyle = Ascent.COLORS.dark; ctx.strokeText(label, x, y);
      ctx.fillStyle = Ascent.COLORS.white; ctx.fillText(label, x, y);
    }
  }
  function drawHolds() {
    if (!photo || !view.clientWidth) return;
    drawPhoto(photo);
    const k = view.width / view.clientWidth;             // photo pixels per screen pixel
    const poly = corners.length === 4 ? corners : taps;
    if (poly.length) {
      ctx.lineWidth = 2.5 * k; ctx.strokeStyle = Ascent.COLORS.amber;
      ctx.beginPath();
      poly.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (poly.length === 4) ctx.closePath();
      ctx.stroke();
      if (corners.length !== 4) taps.forEach(([x, y], i) => {
        ctx.fillStyle = Ascent.COLORS.amber; ctx.beginPath(); ctx.arc(x, y, 9 * k, 0, 2 * Math.PI); ctx.fill();
        ctx.fillStyle = Ascent.COLORS.dark; ctx.font = `bold ${12 * k}px system-ui`;
        ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(i + 1), x, y);
      });
    }
    holds.forEach(h => holdRing(h.px[0], h.px[1], 12 * k, k, Ascent.COLORS.white, ""));
  }
  function drawRoute() {
    if (!wallPhoto || !view.clientWidth) return;
    drawPhoto(wallPhoto);
    const k = view.width / view.clientWidth;
    const on = new Set(route ? route.holds : []);
    ctx.globalAlpha = 0.55;                                 // every hold of the wall, faint: tap one to add it
    wallHolds.forEach(h => { if (!on.has(h.id)) holdRing(h.px[0], h.px[1], 9 * k, 0.7 * k, Ascent.COLORS.white, ""); });
    ctx.globalAlpha = 1;
    if (!route || !route.holds.length) return;
    const pts = route.holds_px, n = pts.length;
    ctx.globalAlpha = 0.5; ctx.lineWidth = 2.5 * k; ctx.strokeStyle = Ascent.COLORS.white;
    ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke();
    ctx.globalAlpha = 1;
    pts.forEach(([x, y], i) => holdRing(x, y, 14 * k, k,
      Ascent.COLORS[i === 0 ? "start" : i === n - 1 ? "finish" : "middle"], String(i + 1)));
  }
  window.addEventListener("resize", () => { if (step === "holds") drawHolds(); if (step === "route") drawRoute(); });

  // ------------------------------------------------------------------ 1. the photo, inside the page
  $("new").onclick = async () => {
    clearError();
    $("cam").classList.remove("hidden");
    $("bar-photo").classList.remove("hidden"); $("bar-climb").classList.add("hidden");
    $("state").textContent = "Fit the whole wall in the frame"; $("state").className = "state";
    $("detail").textContent = "Hold steady, then tap Capture.";
    video.style.objectFit = "contain";                      // the photo is the whole frame: show all of it
    Ascent.fullscreen(true);
    try { await Ascent.startCamera(video, 1920, 1080); }
    catch (e) { closeCam(); fail(e.message); }
  };
  function closeCam() {
    Ascent.stopCamera(video);
    Ascent.fitCanvas(canvas);
    $("cam").classList.add("hidden");
    Ascent.fullscreen(false);
  }
  $("cancel").onclick = closeCam;
  $("shutter").onclick = async () => {
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return;
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    c.getContext("2d").drawImage(video, 0, 0, w, h);
    closeCam();
    await usePicture(c, w, h);
  };
  async function usePicture(src, w, h) {
    const s = Math.min(1, 1600 / Math.max(w, h));
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
    c.getContext("2d").drawImage(src, 0, 0, c.width, c.height);
    view.width = c.width; view.height = c.height;
    dataUrl = c.toDataURL("image/jpeg", 0.9);
    photo = c; corners = []; holds = []; taps = []; how = null;
    step = "holds"; show("s-holds");
    await findWall();
  }

  // ------------------------------------------------------------------ 2. the laptop finds wall and holds
  async function findWall(cornerTaps) {
    status("Looking for the wall and the holds...");
    $("holds-ok").disabled = true;
    try {
      found = await Ascent.api("/api/scan/auto", { image: dataUrl, corners: cornerTaps || [] });
    } catch (e) { return fail(e.message); }
    status("");
    how = found.how;
    if (found.corners) { corners = found.corners; holds = found.holds; taps = []; }
    holdStep();
    view.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  function holdStep() {
    step = "holds"; show("s-holds");
    const msg = $("holds-msg");
    if (corners.length !== 4) {
      msg.textContent = (found && found.message ? found.message + " " : "") +
        (taps.length < 4 ? `Tap the ${NAMES[taps.length]} corner of the board.` : "");
      $("holds-ok").disabled = true;
      $("holds-undo").disabled = !taps.length;
    } else {
      const by = { markers: "the printed markers", outline: "the board's outline", taps: "your taps" }[how];
      msg.textContent = (found ? `Wall found from ${by}, ${holds.length} holds found.`
                               : `Wall '${wallName}' as saved, ${holds.length} holds.`) +
        (holds.length ? " Every hold should have a white ring. Fix it: tap a ring to remove it, tap a missed" +
                        " hold to add it. Then Looks good."
                      : " Tap each hold, or take a new photo in better light.");
      $("holds-ok").disabled = !holds.length;
      $("holds-undo").disabled = !holds.length;
    }
    drawHolds();
  }
  view.addEventListener("click", e => {
    const r = view.getBoundingClientRect();
    const x = (e.clientX - r.left) * view.width / r.width, y = (e.clientY - r.top) * view.height / r.height;
    const k = view.width / view.clientWidth;
    if (step === "route") return routeTap(x, y, k);
    if (step !== "holds") return;
    if (corners.length !== 4) {                              // the last fallback: 4 corner taps
      taps.push([x, y]);
      if (taps.length === 4) findWall(taps); else holdStep();
      return;
    }
    const near = holds.findIndex(h => Math.hypot(h.px[0] - x, h.px[1] - y) < 22 * k);   // a fingertip is wide
    if (near >= 0) holds.splice(near, 1); else holds.push({ px: [x, y], type: null });
    holdStep();
  });
  $("holds-undo").onclick = () => { if (corners.length !== 4) taps.pop(); else holds.pop(); holdStep(); };
  $("retake").onclick = () => { photo = null; clearError(); $("new").onclick(); };

  $("holds-ok").onclick = async () => {
    const name = found ? ($("name").value.trim() || "wall") : wallName;   // a fixed wall keeps its name
    $("holds-ok").disabled = true;
    status("Saving the wall on the laptop...");
    try {
      const r = await Ascent.api("/api/scan", {
        wall: name, image: dataUrl, markers: how === "markers", corners: how === "markers" ? [] : corners,
        width: parseFloat($("width").value) || null, height: null,
        holds: holds.map(h => ({ px: h.px, type: h.type || null, colour: h.colour || null })) });
      wallName = r.wall; wallPhoto = photo;
      await loadWallHolds();
      status("");
      routeStep(`Wall '${r.wall}' saved (version ${r.version}, ${r.holds} holds). Pick what you want to train.`);
    } catch (e) { fail(e.message); $("holds-ok").disabled = false; }
  };
  async function loadWallHolds() {
    wallHolds = (await Ascent.getJSON("/api/wall/holds?wall=" + encodeURIComponent(wallName))).holds;
  }

  // ------------------------------------------------------------------ 3. a route: for a skill, or by hand
  async function useExistingWall(name) {
    clearError();
    status("Loading the wall's photo...");
    try {
      const res = await fetch(Ascent.url("/api/wall/photo", { wall: name }), { credentials: "same-origin" });
      if (!res.ok) throw new Error("The laptop has no photo of this wall.");
      const img = await createImageBitmap(await res.blob());
      view.width = img.width; view.height = img.height;
      wallName = name; wallPhoto = img;
      await loadWallHolds();
      status("");
      routeStep("Pick what you want to train, or build your own route.");
    } catch (e) { fail(e.message); }
  }
  function routeStep(msg) {
    step = "route"; show("s-route");
    route = null; savedRoute = null; routeHow = "generated";
    $("route-msg").textContent = msg;
    routeButtons();
    drawRoute();
    view.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  function routeButtons() {
    const made = route && routeHow === "generated";
    $("make").classList.toggle("hidden", !!made);
    $("another").classList.toggle("hidden", !made);
    $("keep").classList.toggle("hidden", !(route && route.holds.length >= 2));
  }
  function routeMsg(text) {
    const warn = route ? route.warnings.filter(w => !/not measured/.test(w)) : [];
    $("route-msg").textContent = text + (warn.length ? " ! " + warn[0] : "") +
      " Tap a ring to take that hold out, tap another hold to add it.";
    routeButtons();
  }
  document.querySelectorAll("#flow-skills button").forEach(b => {
    b.onclick = () => {
      skill = b.dataset.skill;
      document.querySelectorAll("#flow-skills button").forEach(x => x.classList.toggle("on", x === b));
      if (route && routeHow === "generated") makeRoute();
    };
  });
  async function makeRoute() {
    clearError();
    $("make").disabled = $("another").disabled = true;
    status("Making a " + skill + " route...");
    try {
      route = await Ascent.api("/api/route/make", { wall: wallName, skill });
      routeHow = "generated";
      status("");
      routeMsg(`${route.holds.length} holds, grade ${route.grade} (estimated), ${skill}.` +
        (route.short ? " Fewer holds than asked - that is all that fits." : ""));
      drawRoute();
    } catch (e) { fail(e.message); }
    $("make").disabled = $("another").disabled = false;
  }
  $("make").onclick = makeRoute;
  $("another").onclick = makeRoute;
  // Build my own: tap the holds in climbing order. A tap on a generated route edits it the same way.
  $("build").onclick = () => { clearError(); routeHow = "built"; editRoute([]); };
  function routeTap(x, y, k) {
    if (!wallHolds.length) return;
    let near = null, best = 22 * k;
    wallHolds.forEach(h => { const d = Math.hypot(h.px[0] - x, h.px[1] - y); if (d < best) { best = d; near = h; } });
    if (!near) return;
    const ids = route ? route.holds.slice() : [];
    const i = ids.indexOf(near.id);
    if (i >= 0) ids.splice(i, 1); else ids.push(near.id);
    routeHow = "built";
    editRoute(ids);
  }
  async function editRoute(ids) {
    clearError();
    if (ids.length < 2) {
      route = ids.length ? { holds: ids, holds_px: ids.map(i => holdById(i).px), grade: "?", warnings: [] } : null;
      $("route-msg").textContent = ids.length ? "1 hold. Tap the next hold of your route."
        : "Your own route: tap the holds in climbing order, from the bottom up.";
      routeButtons();
      drawRoute();
      return;
    }
    status("Checking the route...");
    try {
      route = await Ascent.api("/api/route/check", { wall: wallName, holds: ids });
      status("");
      routeMsg(`${route.holds.length} holds, grade ${route.grade} (estimated), built by hand.`);
      drawRoute();
    } catch (e) { fail(e.message); }
  }
  $("keep").onclick = async () => {
    $("keep").disabled = true;
    try {
      savedRoute = await Ascent.api("/api/route/save", { wall: wallName, holds: route.holds, skill, how: routeHow });
      step = "climb"; show("s-climb");
      $("climb-title").textContent = `Route ${savedRoute.route} is ready`;
      $("climb-text").textContent = `${savedRoute.holds} holds, grade ${savedRoute.grade} (estimated), ` +
        `${routeHow === "built" ? "built by hand" : skill}. Start is green, finish is red.`;
    } catch (e) { fail(e.message); }
    $("keep").disabled = false;
  };
  // Fix the holds: the saved wall's photo, corners and holds back on the screen; Looks good saves a new version
  $("fix").onclick = async () => {
    clearError();
    status("Loading the wall...");
    try {
      const info = await Ascent.getJSON("/api/wall/holds?wall=" + encodeURIComponent(wallName));
      const c = document.createElement("canvas"); c.width = info.w; c.height = info.h;
      c.getContext("2d").drawImage(wallPhoto, 0, 0, info.w, info.h);
      photo = c; dataUrl = c.toDataURL("image/jpeg", 0.92);
      view.width = info.w; view.height = info.h;
      corners = info.corners; taps = []; found = null;
      holds = info.holds.map(h => ({ px: h.px, type: h.type || null, colour: h.colour || null }));
      how = info.mode === "markers" ? "markers" : null;    // null: a saved scan, re-saved under its own name
      status("");
      holdStep();
      view.scrollIntoView({ block: "start", behavior: "smooth" });
    } catch (e) { fail(e.message); }
  };
  $("route-back").onclick = () => { step = "start"; show("s-start"); };
  $("climb-back").onclick = () => routeStep("Pick what you want to train, or build your own route.");
  $("restart").onclick = () => { step = "start"; show("s-start"); clearError(); };

  // ------------------------------------------------------------------ 4. phone down, climb with sounds
  function flash(text, good) {
    $("flash").textContent = text;
    $("flash").style.color = good ? "var(--green)" : "var(--amber)";
    flashUntil = performance.now() + 1500;
  }
  function touchHint() {
    if (touch === "sticker") return learned ? "Sticker colour learned." : "Tap the sticker on the screen once.";
    if (touch === "hands") return "The laptop tracks your hands - no sticker needed.";
    return "The laptop tracks your body.";
  }
  function showAnswer(a) {
    const st = $("state");
    if (a.state === "locked") {
      st.textContent = a.next < a.of ? `Locked - go for hold ${a.next + 1} of ${a.of}` : "Top reached";
      st.className = "state locked";
    } else { st.textContent = a.message; st.className = "state warn"; }
    $("detail").textContent = touchHint();
    const d = Ascent.drawRings(canvas, video, a);            // draws nothing unless locked
    if (d && a.rings) {
      a.rings.slice(0, a.next).forEach(r => {
        const [x, y] = d.map(r.x, r.y);
        d.ctx.fillStyle = Ascent.COLORS.start; d.ctx.beginPath(); d.ctx.arc(x, y, 7, 0, 2 * Math.PI); d.ctx.fill();
      });
      (a.hands || []).forEach(h => {                         // where the laptop sees a hand (or the sticker)
        const [x, y] = d.map(h.x, h.y);
        d.ctx.lineWidth = 3; d.ctx.strokeStyle = Ascent.COLORS.amber;
        d.ctx.beginPath(); d.ctx.arc(x, y, 11, 0, 2 * Math.PI); d.ctx.stroke();
      });
    }
    if (a.learned === true) { learned = true; flash("Sticker colour learned", true); sounds.play("good"); }
    else if (a.learned === false) flash("Tap the sticker itself - a bright colour", false);
    for (const e of a.events || []) { sounds.play(e.sound); flash(e.message, e.sound === "good" || e.sound === "top"); }
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
          const params = { sid, t: ((start - t0) / 1000).toFixed(3) };
          if (tap) { params.tapx = tap[0].toFixed(0); params.tapy = tap[1].toFixed(0); tap = null; }
          showAnswer(await Ascent.api("/api/frame", blob, params));
        } catch (e) {
          $("state").textContent = e.message; $("state").className = "state warn";
          Ascent.fitCanvas(canvas);
          if (/Session ended/.test(e.message)) { stopClimb(); break; }
          await Ascent.sleep(500);
        }
      }
      await Ascent.sleep(Math.max(0, 125 - (performance.now() - start)));
    }
  }
  // A tap on the live view = "this is the sticker": its place in the sent frame goes with the next frame.
  $("cam").addEventListener("pointerdown", e => {
    if (!running || touch !== "sticker" || e.target.closest("button")) return;
    const r = canvas.getBoundingClientRect();
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return;
    const s = Math.max(r.width / vw, r.height / vh);
    const ox = (r.width - vw * s) / 2, oy = (r.height - vh * s) / 2;
    const f = Math.min(1, 800 / Math.max(vw, vh));          // the frame the laptop gets is at most 800 px
    tap = [((e.clientX - r.left - ox) / s) * f, ((e.clientY - r.top - oy) / s) * f];
  });

  function stopClimb() {
    running = false;
    if (wake) { wake.release().catch(() => {}); wake = null; }
    closeCam();
    $("summary").classList.add("hidden");
    $("start").disabled = false;
  }
  $("start").onclick = async () => {
    clearError();
    await sounds.unlock();                                   // inside the tap, as iPhones require
    sounds.play("good");
    $("start").disabled = true;
    try {
      const info = await Ascent.api("/api/track/start", {
        wall: wallName, route: savedRoute.route, touch: $("touch").value, sticker: $("sticker").value });
      sid = info.sid; learned = false; tap = null; touch = info.touch;
      $("cam").classList.remove("hidden");
      $("bar-photo").classList.add("hidden"); $("bar-climb").classList.remove("hidden");
      $("state").textContent = "Starting..."; $("state").className = "state warn";
      $("detail").textContent = `${info.route}  ${info.grade} (estimated)  ${info.holds} holds. ` + touchHint();
      video.style.objectFit = "cover";                        // live view fills the screen, as the rings expect
      Ascent.fullscreen(true);
      await Ascent.startCamera(video);
      wake = await Ascent.keepAwake();
      t0 = performance.now();
      running = true;
      loop();
    } catch (e) { stopClimb(); fail(e.message); }
  };
  $("sound").onclick = () => { $("sound").textContent = sounds.toggle() ? "Sound on" : "Sound off"; };
  $("again").onclick = async () => {
    try { await Ascent.api("/api/track/reset", {}, { sid }); $("summary").classList.add("hidden"); flash("Go again", true); }
    catch (e) { flash(e.message, false); }
  };
  $("done").onclick = async () => {
    try {
      const s = await Ascent.api("/api/track/finish", {}, { sid });
      let text = `Reached ${s.reached} of ${s.of} holds in order.`;
      if (s.skipped.length) text += ` Skipped: ${s.skipped.length}.`;
      if (s.off_route.length) text += ` Off-route holds: ${s.off_route.length}.`;
      text += `\nThe camera's guess: ${s.result}. You know better - it is only a suggestion.\nTry again, or Stop.`;
      $("summary").textContent = text;
      $("summary").classList.remove("hidden");
      if (s.result === "sent") sounds.play("top");
    } catch (e) { flash(e.message, false); }
  };
  $("stop").onclick = stopClimb;

  // ------------------------------------------------------------------ the start page
  async function loadWalls() {
    try {
      walls = (await Ascent.getJSON("/api/walls")).walls;
      $("wall").innerHTML = "";
      walls.forEach(w => $("wall").add(new Option(`${w.name}  (v${w.version}, ${w.holds} holds)`, w.name)));
      if (wallName && walls.some(w => w.name === wallName)) $("wall").value = wallName;
      $("have").classList.toggle("hidden", !walls.length);
    } catch (e) { fail(e.message); }
  }
  $("use-wall").onclick = () => { if ($("wall").value) useExistingWall($("wall").value); };

  Ascent.views.climb = {
    enter() { loadWalls(); if (step === "start") show("s-start"); else if (step === "holds") drawHolds(); else if (step === "route") drawRoute(); },
    leave() { if (running) stopClimb(); else closeCam(); },
  };
})();
