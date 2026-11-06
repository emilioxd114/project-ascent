// Project Ascent - shared code for the phone pages. Plain JavaScript, no build step.
// The laptop does the vision work; the phone shows the camera, sends small JPEG frames and draws rings.
"use strict";

const Ascent = (() => {
  const code = new URLSearchParams(location.search).get("code") || "";
  // Same colours as the laptop windows: green start, blue middle, red finish, amber warnings.
  const COLORS = { start: "rgb(74,222,128)", middle: "rgb(106,169,244)", finish: "rgb(243,115,111)",
                   amber: "rgb(245,177,61)", white: "rgb(244,243,240)", dark: "rgb(12,14,16)" };

  function url(path, params = {}) {
    const u = new URL(path, location.origin);
    if (code) u.searchParams.set("code", code);
    for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
    return u.toString();
  }

  async function api(path, body, params = {}) {
    const isBlob = body instanceof Blob;
    const res = await fetch(url(path, params), {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": isBlob ? "image/jpeg" : "application/json" },
      body: isBlob ? body : JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) throw new Error(data.error || ("The laptop answered " + res.status));
    return data;
  }

  async function getJSON(path) {
    const res = await fetch(url(path), { credentials: "same-origin" });
    if (!res.ok) throw new Error("The laptop answered " + res.status);
    return res.json();
  }

  async function startCamera(video, width = 1280, height = 720) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("This browser can't open the camera here. Open the https:// link from the laptop " +
                      "and accept the certificate warning (see START_HERE.md).");
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" }, width: { ideal: width }, height: { ideal: height } },
      });
      video.srcObject = stream;
      video.setAttribute("playsinline", "");
      video.muted = true;
      await video.play();
      return stream;
    } catch (e) {
      if (e.name === "NotAllowedError") throw new Error("Camera blocked. Allow the camera for this page in the " +
                                                        "browser settings, then reload.");
      throw new Error("Could not open the camera: " + e.message);
    }
  }

  function stopCamera(video) {
    const s = video.srcObject;
    if (s) s.getTracks().forEach(t => t.stop());
    video.srcObject = null;
  }

  // A downscaled JPEG of the current video frame. Small frames keep the Wi-Fi fast.
  const grab = document.createElement("canvas");
  function grabFrame(video, maxSide = 800, quality = 0.7) {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return Promise.resolve(null);
    const s = Math.min(1, maxSide / Math.max(vw, vh));
    grab.width = Math.round(vw * s);
    grab.height = Math.round(vh * s);
    grab.getContext("2d").drawImage(video, 0, 0, grab.width, grab.height);
    return new Promise(resolve => grab.toBlob(resolve, "image/jpeg", quality));
  }

  // The canvas lies over the video, which fills the screen (object-fit: cover).
  function fitCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return ctx;
  }

  // Frame pixels (what the laptop saw) -> screen pixels (what the phone shows).
  function frameToScreen(video, canvas, fw, fh) {
    const vw = video.videoWidth, vh = video.videoHeight;
    const cw = canvas.clientWidth, ch = canvas.clientHeight;
    const s = Math.max(cw / vw, ch / vh);
    const ox = (cw - vw * s) / 2, oy = (ch - vh * s) / 2;
    const k = (vw / fw) * s;
    return { k, map: (x, y) => [x * k + ox, y * k + oy] };
  }

  function ring(ctx, x, y, r, color, label) {
    r = Math.max(12, r);
    ctx.lineWidth = 7; ctx.strokeStyle = COLORS.dark;                         // dark outer edge
    ctx.beginPath(); ctx.arc(x, y, r + 3, 0, 2 * Math.PI); ctx.stroke();
    ctx.lineWidth = 6; ctx.strokeStyle = COLORS.white;                        // white halo: any hold colour
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.lineWidth = 3; ctx.strokeStyle = color;                               // route colour
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.font = "bold 17px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.lineWidth = 5; ctx.strokeStyle = COLORS.dark; ctx.strokeText(label, x, y);
    ctx.fillStyle = COLORS.white; ctx.fillText(label, x, y);
  }

  // Draws the route only for a locked answer. Anything else: an empty canvas.
  function drawRings(canvas, video, answer) {
    const ctx = fitCanvas(canvas);
    if (!answer || answer.state !== "locked" || !answer.rings) return null;
    const { k, map } = frameToScreen(video, canvas, answer.w, answer.h);
    const pts = answer.rings.map(r => map(r.x, r.y));
    ctx.globalAlpha = 0.35; ctx.lineWidth = 2; ctx.strokeStyle = COLORS.white;
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.stroke();
    ctx.globalAlpha = 1;
    answer.rings.forEach((r, i) => ring(ctx, pts[i][0], pts[i][1], answer.radius * k, COLORS[r.kind], String(r.n)));
    return { ctx, map, k };
  }

  async function keepAwake() {
    try { if (navigator.wakeLock) return await navigator.wakeLock.request("screen"); } catch (e) { /* fine */ }
    return null;
  }

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // Fills a wall and a route list. needRoute: no "Newest route" choice (recording needs a specific one).
  async function fillWalls(wallSel, routeSel, { wall = null, needRoute = false } = {}) {
    const { walls } = await getJSON("/api/walls");
    const keep = wall || wallSel.value;
    wallSel.innerHTML = "";
    if (!walls.length) wallSel.add(new Option("No walls yet - scan one first", ""));
    walls.forEach(w => wallSel.add(new Option(`${w.name}  (v${w.version}, ${w.routes.length} routes)`, w.name)));
    if (walls.some(w => w.name === keep)) wallSel.value = keep;
    const showRoutes = () => {
      routeSel.innerHTML = "";
      const w = walls.find(x => x.name === wallSel.value);
      const routes = (w ? w.routes : []).filter(r => !r.old_version);
      if (!needRoute) routeSel.add(new Option(routes.length ? "Newest route" : "None yet - a new one is made", ""));
      else if (!routes.length) routeSel.add(new Option("No routes yet - make one on 'See a route'", ""));
      routes.forEach(r => routeSel.add(new Option(`${r.name}  ${r.grade || "?"}  ${r.holds} holds ` +
                                                  (r.train.join(", ") || r.made_by || ""), r.name)));
    };
    wallSel.onchange = showRoutes;
    showRoutes();
    return walls;
  }

  // Full-screen camera views hide the tabs; Stop brings them back.
  function fullscreen(on) { document.body.classList.toggle("fullcam", on); }

  // Any error shows on the phone AND in the laptop's console, so it can be pasted to whoever fixes it.
  function report(msg) {
    msg = String(msg).slice(0, 500);
    const box = document.getElementById("bug");
    if (box) {
      box.textContent = "Something went wrong: " + msg + "  (tap to hide)";
      box.classList.remove("hidden");
      box.onclick = () => box.classList.add("hidden");
    }
    fetch(url("/api/log"), { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, page: location.hash, agent: navigator.userAgent }) }).catch(() => {});
  }
  window.addEventListener("error", e => report((e.message || "error") + (e.filename ? ` (${e.filename.split("/").pop()}:${e.lineno})` : "")));
  window.addEventListener("unhandledrejection", e => report(e.reason && e.reason.message ? e.reason.message : e.reason));

  return { code, COLORS, url, api, getJSON, startCamera, stopCamera, grabFrame, fitCanvas, frameToScreen,
           drawRings, ring, keepAwake, sleep, fillWalls, fullscreen, report, views: {} };
})();

