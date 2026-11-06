// "Scan a wall": photo -> 4 corners -> size -> holds and types -> save (same save as the laptop's scan).
"use strict";
(() => {
  const $ = id => document.getElementById("scan-" + id);
  const view = $("view"), ctx = view.getContext("2d"), video = $("video");
  const TYPES = ["jug", "crimp", "sloper", "pinch", "pocket"];
  const NAMES = ["top-left", "top-right", "bottom-right", "bottom-left"];
  let photo = null, dataUrl = null, step = "photo", corners = [], holds = [], sel = -1, walls = [], markersFound = false;

  function show(id) {
    ["s-photo", "s-corners", "s-size", "s-holds", "s-done"].forEach(s => $(s).classList.toggle("hidden", s !== id));
    view.classList.toggle("hidden", !photo || id === "s-done" || id === "s-photo");
  }
  function status(text) { $("status").textContent = text || ""; $("status").classList.toggle("hidden", !text); }
  function fail(msg) { status(""); $("error").textContent = msg; }

  // Same order as the laptop: top-left, top-right, bottom-right, bottom-left.
  function orderCorners(p) {
    const s = p.map(([x, y]) => x + y), d = p.map(([x, y]) => y - x);
    const at = (arr, f) => p[arr.indexOf(f(...arr))];
    return [at(s, Math.min), at(d, Math.min), at(s, Math.max), at(d, Math.max)];
  }

  function draw() {
    if (!photo || !view.clientWidth) return;
    ctx.drawImage(photo, 0, 0, view.width, view.height);
    const k = view.width / view.clientWidth;            // photo pixels per screen pixel
    if (corners.length) {
      ctx.lineWidth = 2.5 * k; ctx.strokeStyle = Ascent.COLORS.amber;
      ctx.beginPath();
      const poly = corners.length === 4 ? orderCorners(corners) : corners;
      poly.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (corners.length === 4) ctx.closePath();
      ctx.stroke();
      corners.forEach(([x, y], i) => {
        ctx.fillStyle = Ascent.COLORS.amber;
        ctx.beginPath(); ctx.arc(x, y, 9 * k, 0, 2 * Math.PI); ctx.fill();
        ctx.fillStyle = Ascent.COLORS.dark; ctx.font = `bold ${12 * k}px system-ui`;
        ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(i + 1), x, y);
      });
    }
    holds.forEach((h, i) => {
      const [x, y] = h.px, r = 10 * k;
      ctx.lineWidth = 6 * k; ctx.strokeStyle = Ascent.COLORS.dark;
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
      ctx.lineWidth = 3 * k; ctx.strokeStyle = i === sel ? Ascent.COLORS.amber : Ascent.COLORS.white;
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
      if (h.type) {
        ctx.font = `bold ${12 * k}px system-ui`; ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.lineWidth = 4 * k; ctx.strokeStyle = Ascent.COLORS.dark; ctx.strokeText(h.type, x + r + 4 * k, y);
        ctx.fillStyle = Ascent.COLORS.white; ctx.fillText(h.type, x + r + 4 * k, y);
      }
    });
  }

  function cornerStep() {
    step = "corners"; show("s-corners");
    $("corner-msg").textContent = markersFound ? "Markers found - their centres are the corners." :
      corners.length < 4 ? `Tap the ${NAMES[corners.length]} corner of the climbing area (fixed points, never a hold).`
                         : "All 4 corners. Next, or Undo to fix one.";
    $("corner-next").disabled = corners.length !== 4;
    $("corner-undo").disabled = markersFound || !corners.length;
    draw();
    view.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  function holdStep() {
    step = "holds"; show("s-holds");
    const typed = holds.filter(h => h.type).length;
    $("hold-msg").textContent = `${holds.length} holds, ${typed} tagged. Tap each hold, then its type. ` +
                                "Tap a hold again to select it. Small holds: turn the phone sideways, pinch to zoom.";
    $("save").disabled = !holds.length;
    document.querySelectorAll("#scan-types button").forEach(b =>
      b.classList.toggle("on", sel >= 0 && !!holds[sel] && (holds[sel].type || "none") === b.dataset.t));
    draw();
  }

  TYPES.concat(["none"]).forEach(t => {
    const b = document.createElement("button");
    b.textContent = t; b.dataset.t = t;
    b.onclick = () => { if (sel >= 0) { holds[sel].type = t === "none" ? null : t; holdStep(); } };
    $("types").appendChild(b);
  });

  view.addEventListener("click", e => {
    const r = view.getBoundingClientRect();
    const x = (e.clientX - r.left) * view.width / r.width, y = (e.clientY - r.top) * view.height / r.height;
    if (step === "corners" && !markersFound && corners.length < 4) { corners.push([x, y]); cornerStep(); }
    else if (step === "holds") {
      const k = view.width / view.clientWidth;
      const near = holds.findIndex(h => Math.hypot(h.px[0] - x, h.px[1] - y) < 10 * k);
      if (near >= 0) sel = near; else { holds.push({ px: [x, y], type: null }); sel = holds.length - 1; }
      holdStep();
    }
  });

  // Any picture source (camera frame, decoded file) -> upright canvas of at most 1600 px -> the corners step.
  async function usePicture(src, w, h) {
    const s = Math.min(1, 1600 / Math.max(w, h));
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
    c.getContext("2d").drawImage(src, 0, 0, c.width, c.height);
    view.width = c.width; view.height = c.height;
    dataUrl = c.toDataURL("image/jpeg", 0.9);
    photo = c; corners = []; holds = []; sel = -1; markersFound = false;
    if ($("markers").checked) {
      status("Looking for the 4 markers...");
      const m = await Ascent.api("/api/scan/markers", { image: dataUrl });
      if (!m.corners) {
        photo = null; show("s-photo");
        return fail(`Found ${m.found} of 4 markers. Make sure all four are visible and flat, then take the photo again.`);
      }
      corners = m.corners; markersFound = true;
    }
    status("");
    cornerStep();
  }

  // ---- photo from the camera, inside the page (no switch to the camera app, which can reload the page)
  $("open").onclick = async () => {
    $("error").textContent = "";
    if (!$("name").value.trim()) return fail("Give the wall a name first.");
    $("cam").classList.remove("hidden");
    Ascent.fullscreen(true);
    try { await Ascent.startCamera(video, 1920, 1080); }
    catch (e) { closeCam(); fail(e.message + "  You can also use 'Choose a photo'."); }
  };
  function closeCam() {
    Ascent.stopCamera(video);
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
    try { await usePicture(c, w, h); } catch (e) { fail("The photo could not be used: " + e.message); }
  };

  // ---- photo from the gallery (or the camera app, if the phone offers it)
  $("choose").onclick = () => {
    $("error").textContent = "";
    if (!$("name").value.trim()) return fail("Give the wall a name first.");
    $("file").value = "";
    $("file").click();
  };
  function decodeWithImg(file) {
    return new Promise((res, rej) => {
      const i = new Image();
      i.onload = () => res(i);
      i.onerror = () => rej(new Error("This photo format can't be read here. Use 'Take photo', or a JPEG."));
      i.src = URL.createObjectURL(file);
    });
  }
  $("file").onchange = async e => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    status("Loading photo...");
    try {
      let img;
      try {
        // the browser turns the photo upright; give up after 5 s and try the plain way
        img = await Promise.race([createImageBitmap(file, { imageOrientation: "from-image" }),
                                  new Promise((_, rej) => setTimeout(() => rej(new Error("slow")), 5000))]);
      } catch (err) { img = await decodeWithImg(file); }
      await usePicture(img, img.width, img.height);
    } catch (err) { fail(err.message); }
  };

  $("retake").onclick = () => { photo = null; status(""); step = "photo"; show("s-photo"); };
  $("corner-undo").onclick = () => { corners.pop(); cornerStep(); };
  $("corner-next").onclick = () => {
    step = "size"; show("s-size");
    view.classList.remove("hidden");
    const est = () => {
      const [tl, tr, , bl] = orderCorners(corners);
      const w = parseFloat($("w").value);
      const ratio = Math.hypot(bl[0] - tl[0], bl[1] - tl[1]) / Math.hypot(tr[0] - tl[0], tr[1] - tl[1]);
      $("h").placeholder = "about " + Math.round((w > 0 ? w : 300) * ratio);
    };
    $("w").oninput = est; est();
    draw();
  };
  $("size-back").onclick = () => { if (markersFound) { step = "photo"; show("s-photo"); } else cornerStep(); };
  $("size-next").onclick = () => {
    const w = $("w").value, h = $("h").value;
    if ((w && !(parseFloat(w) > 0)) || (h && !(parseFloat(h) > 0))) return fail("Sizes are in cm, more than 0.");
    $("error").textContent = "";
    holdStep();
  };
  $("hold-undo").onclick = () => { holds.pop(); sel = holds.length - 1; holdStep(); };

  $("save").onclick = async () => {
    const name = $("name").value.trim();
    const old = walls.find(w => w.name === name);
    if (old && !confirm(`'${name}' exists (version ${old.version}). Saving makes version ${old.version + 1}; ` +
                        "the old version and its routes are archived, nothing is deleted.")) return;
    $("save").disabled = true;
    status("Saving on the laptop...");
    try {
      const r = await Ascent.api("/api/scan", {
        wall: name, image: dataUrl, markers: markersFound, corners: markersFound ? [] : corners,
        width: parseFloat($("w").value) || null, height: parseFloat($("h").value) || null,
        holds: holds.map(h => ({ px: h.px, type: h.type })) });
      status("");
      $("done-title").textContent = `Saved '${r.wall}', version ${r.version}`;
      $("done-text").textContent = `${r.holds} holds, ${r.typed} tagged. ${Math.round(r.size_cm.w)} x ` +
        `${Math.round(r.size_cm.h)} cm` + (r.size_cm.assumed ? " (assumed - reach checks approximate)." : ".");
      $("to-live").onclick = () => Ascent.openTab("live", { wall: r.wall });
      step = "done"; show("s-done");
      loadWalls();
    } catch (e) { fail(e.message); $("save").disabled = false; }
  };
  $("again").onclick = () => { photo = null; $("error").textContent = ""; step = "photo"; show("s-photo"); };

  function checkName() {
    const old = walls.find(w => w.name === $("name").value.trim());
    $("exists").textContent = old ? `Exists (version ${old.version}). A new scan becomes version ${old.version + 1}.` : "";
  }
  $("name").oninput = checkName;
  function loadWalls() { Ascent.getJSON("/api/walls").then(d => { walls = d.walls; checkName(); }).catch(e => fail(e.message)); }
  window.addEventListener("resize", draw);

  Ascent.views.scan = {
    enter() { loadWalls(); if (step === "photo") show("s-photo"); else draw(); },
    leave() { closeCam(); },
  };
})();
