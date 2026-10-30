// Sound effects. The server marks what just happened with data-sfx="name name" on the panel it
// sends back; when HTMX swaps that panel in, its sounds play in order. Markers already on the
// page when it loads stay silent, so a reload never replays a boss falling. Other scripts can
// call window.hollowSound(name) (the map's footsteps). Names with _<n> variants (strike_1,
// strike_2, ...) play one at random. The toggle in the header mutes everything, remembered in
// this browser. Without JavaScript there is simply no sound.
(() => {
  const data = document.getElementById("sounds");
  if (!data) return;
  const files = JSON.parse(data.textContent);
  const KEY = "hollow_sound";
  const GAP = 0.12; // seconds between sounds of one cue, so "strike felled" lands as two beats
  let ctx = null;
  let master = null;
  const buffers = new Map();

  const read = () => {
    try { return localStorage.getItem(KEY) !== "off"; } catch { return true; }
  };
  let on = read();

  const audio = () => {
    if (!ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;
      ctx = new Ctx();
      master = ctx.createGain();
      master.gain.value = 0.8;
      master.connect(ctx.destination);
    }
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    return ctx;
  };

  const pick = (name) => {
    if (files[name]) return name;
    const variants = Object.keys(files).filter((k) => k.startsWith(`${name}_`));
    return variants.length ? variants[Math.floor(Math.random() * variants.length)] : null;
  };

  const load = (name) => {
    if (!buffers.has(name)) {
      buffers.set(name, fetch(files[name])
        .then((r) => r.arrayBuffer())
        .then((b) => new Promise((ok, fail) => ctx.decodeAudioData(b, ok, fail)))
        .catch(() => null));
    }
    return buffers.get(name);
  };

  async function play(cue) {
    if (!on || !audio()) return;
    const names = cue.split(/\s+/).map(pick).filter(Boolean);
    const loaded = await Promise.all(names.map(load));
    let at = ctx.currentTime + 0.01;
    for (const buffer of loaded) {
      if (!buffer) continue;
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(master);
      src.start(at);
      at += Math.min(buffer.duration, GAP * 2) + GAP;
    }
  }
  window.hollowSound = play;

  // Browsers only allow sound after the first click or key press; unlock then, and warm up
  // the short sounds a lesson needs at once.
  const unlock = () => {
    if (!on || !audio()) return;
    ["right", "wrong", "step_1", "strike_1", "hurt"].filter((n) => files[n]).forEach(load);
  };
  ["pointerdown", "keydown"].forEach((e) => document.addEventListener(e, unlock, { once: true, capture: true }));

  const quiet = (root) => root.querySelectorAll("[data-sfx]").forEach((el) => { el.dataset.sfxDone = "1"; });
  quiet(document);
  document.addEventListener("htmx:afterSettle", () => {
    document.querySelectorAll("[data-sfx]:not([data-sfx-done])").forEach((el) => {
      el.dataset.sfxDone = "1";
      play(el.dataset.sfx);
    });
  });

  // The header toggle. It is hidden in the markup: without JavaScript it would do nothing.
  const toggle = document.querySelector("[data-sound-toggle]");
  if (toggle) {
    const draw = () => {
      toggle.setAttribute("aria-pressed", String(on));
      toggle.title = on ? "Sound on" : "Sound off";
    };
    toggle.hidden = false;
    draw();
    toggle.addEventListener("click", () => {
      on = !on;
      try { localStorage.setItem(KEY, on ? "on" : "off"); } catch { /* private window */ }
      draw();
      if (on) play("right");
    });
  }
})();
