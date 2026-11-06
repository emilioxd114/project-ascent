// "Climb": the whole flow on the phone, nothing typed, nothing measured.
//   photo -> the laptop finds the wall and the holds -> "Looks good" -> a route for a skill, drawn on the
//   photo -> "Use this route" -> phone down, live rings, sticker on the fingertip, sounds.
// The laptop does the vision work (the same code as scan --auto, generate and track --touch sticker).
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
  let wallName = null, wallPhoto = null, route = null, skill = "reach", savedRoute = null;
  // climbing
  let sid = null, running = false, lastAnswerAt = 0, wake = null, t0 = 0, tap = null, flashUntil = 0, learned = false;

  function show(id) {
    ["s-start", "s-holds", "s-route", "s-climb"].forEach(s => $(s).classList.toggle("hidden", s !== id));
    view.classList.toggle("hidden", !(id === "s-holds" || id === "s-route"));
  }
  function status(text) { $("status").textContent = text || ""; $("status").classList.toggle("hidden", !text); }
  function fail(msg) { status(""); $("error").textContent = msg; }
  function clearError() { $("error").textContent = ""; }

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
    holds.forEach(h => holdRing(h.px[0], h.px[1], 11 * k, k, Ascent.COLORS.white, ""));
  }
  function drawRoute() {
    if (!wallPhoto || !view.clientWidth) return;
    drawPhoto(wallPhoto);
    if (!route) return;
    const k = view.width / view.clientWidth, pts = route.holds_px, n = pts.length;
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
        (taps.length < 4 ? `Tap the ${NAMES[taps.length]} corner.` : "");
      $("holds-ok").disabled = true;
      $("holds-undo").disabled = !taps.length;
    } else {
      const by = { markers: "the printed markers", outline: "the board's outline", taps: "your taps" }[how] || "";
      msg.textContent = `Wall found from ${by}, ${holds.length} holds found.` +
        (holds.length ? " Looks good? Or fix it: tap a ring to remove it, tap a missed hold to add it."
                      : " Tap each hold, or take a new photo in better light.");
      $("holds-ok").disabled = !holds.length;
      $("holds-undo").disabled = !holds.length;
    }
    drawHolds();
  }
  view.addEventListener("click", e => {
    const r = view.getBoundingClientRect();
    const x = (e.clientX - r.left) * view.width / r.width, y = (e.clientY - r.top) * view.height / r.height;
    if (step !== "holds") return;
    const k = view.width / view.clientWidth;
    if (corners.length !== 4) {                              // the last fallback: 4 corner taps
      taps.push([x, y]);
      if (taps.length === 4) findWall(taps); else holdStep();
      return;
    }
    const near = holds.findIndex(h => Math.hypot(h.px[0] - x, h.px[1] - y) < 14 * k);
    if (near >= 0) holds.splice(near, 1); else holds.push({ px: [x, y], type: null });
    holdStep();
  });
  $("holds-undo").onclick = () => { if (corners.length !== 4) taps.pop(); else holds.pop(); holdStep(); };
  $("retake").onclick = () => { photo = null; clearError(); $("new").onclick(); };

  $("holds-ok").onclick = async () => {
    const name = ($("name").value.trim() || "wall");
    $("holds-ok").disabled = true;
    status("Saving the wall on the laptop...");
    try {
      const r = await Ascent.api("/api/scan", {
        wall: name, image: dataUrl, markers: how === "markers", corners: how === "markers" ? [] : corners,
        width: parseFloat($("width").value) || null, height: null,
        holds: holds.map(h => ({ px: h.px, type: h.type || null, colour: h.colour || null })) });
      status("");
      wallName = r.wall; wallPhoto = photo;
      routeStep(`Wall '${r.wall}' saved (version ${r.version}, ${r.holds} holds). Pick what you want to train.`);
    } catch (e) { fail(e.message); $("holds-ok").disabled = false; }
  };

  // ------------------------------------------------------------------ 3. a route for a skill
  async function useExistingWall(name) {
    clearError();
    status("Loading the wall's photo...");
    try {
      const res = await fetch(Ascent.url("/api/wall/photo", { wall: name }), { credentials: "same-origin" });
      if (!res.ok) throw new Error("The laptop has no photo of this wall.");
      const img = await createImageBitmap(await res.blob());
      view.width = img.width; view.height = img.height;
      wallName = name; wallPhoto = img;
      status("");
      routeStep("Pick what you want to train.");
    } catch (e) { fail(e.message); }
  }
  function routeStep(msg) {
    step = "route"; show("s-route");
    route = null; savedRoute = null;
    $("route-msg").textContent = msg;
    $("make").classList.remove("hidden"); $("another").classList.add("hidden"); $("keep").classList.add("hidden");
    drawRoute();
    view.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  document.querySelectorAll("#flow-skills button").forEach(b => {
    b.onclick = () => {
      skill = b.dataset.skill;
      document.querySelectorAll("#flow-skills button").forEach(x => x.classList.toggle("on", x === b));
      if (route) makeRoute();
    };
  });
  async function makeRoute() {
    clearError();
    $("make").disabled = $("another").disabled = true;
    status("Making a " + skill + " route...");
    try {
      route = await Ascent.api("/api/route/make", { wall: wallName, skill });
      status("");
      $("route-msg").textContent = `${route.holds.length} holds, grade ${route.grade} (estimated)` +
        (route.short ? " - fewer holds than asked, that is all that fits." : "") +
        (route.warnings.length && !/not measured/.test(route.warnings[0]) ? " ! " + route.warnings[0] : "");
      $("make").classList.add("hidden"); $("another").classList.remove("hidden"); $("keep").classList.remove("hidden");
      drawRoute();
    } catch (e) { fail(e.message); }
    $("make").disabled = $("another").disabled = false;
  }
  $("make").onclick = makeRoute;
  $("another").onclick = makeRoute;
  $("keep").onclick = async () => {
    $("keep").disabled = true;
    try {
      savedRoute = await Ascent.api("/api/route/save", { wall: wallName, holds: route.holds, skill });
      step = "climb"; show("s-climb");
      $("climb-title").textContent = `Route ${savedRoute.route} is ready`;
      $("climb-text").textContent = `${savedRoute.holds} holds, grade ${savedRoute.grade} (estimated), ` +
        `${skill}. Start is green, finish is red.`;
    } catch (e) { fail(e.message); }
    $("keep").disabled = false;
  };
  $("route-back").onclick = () => { step = "start"; show("s-start"); };
  $("climb-back").onclick = () => routeStep("Pick what you want to train.");
  $("restart").onclick = () => { step = "start"; show("s-start"); clearError(); };

  // ------------------------------------------------------------------ 4. phone down, climb with sounds
  function flash(text, good) {
    $("flash").textContent = text;
    $("flash").style.color = good ? "var(--green)" : "var(--amber)";
    flashUntil = performance.now() + 1500;
  }
  function showAnswer(a) {
    const st = $("state");
    if (a.state === "locked") {
      st.textContent = a.next < a.of ? `Locked - go for hold ${a.next + 1} of ${a.of}` : "Top reached";
      st.className = "state locked";
    } else { st.textContent = a.message; st.className = "state warn"; }
    $("detail").textContent = learned ? "Sticker colour learned." : "Tap the sticker on the screen once.";
    const d = Ascent.drawRings(canvas, video, a);            // draws nothing unless locked
    if (d && a.rings) {
      a.rings.slice(0, a.next).forEach(r => {
        const [x, y] = d.map(r.x, r.y);
        d.ctx.fillStyle = Ascent.COLORS.start; d.ctx.beginPath(); d.ctx.arc(x, y, 7, 0, 2 * Math.PI); d.ctx.fill();
      });
      (a.hands || []).forEach(h => {
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
    if (!running || e.target.closest("button")) return;
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
        wall: wallName, route: savedRoute.route, touch: "sticker", sticker: $("sticker").value });
      sid = info.sid; learned = false; tap = null;
      $("cam").classList.remove("hidden");
      $("bar-photo").classList.add("hidden"); $("bar-climb").classList.remove("hidden");
      $("state").textContent = "Starting..."; $("state").className = "state warn";
      $("detail").textContent = `${info.route}  ${info.grade} (estimated)  ${info.holds} holds`;
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
