// Walk the knight between map points. Points are links, so the map also works without JS.
(() => {
  const map = document.querySelector("[data-map]");
  if (!map) return;
  const nodes = [...map.querySelectorAll("[data-node]")];
  const knight = map.querySelector(".map-knight");
  const panels = [...document.querySelectorAll("[data-panel]")];
  const [w, h] = map.dataset.size.split("x").map(Number);
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const MS_PER_PIXEL = 22; // in the art's native pixels
  let at = Math.max(0, nodes.findIndex((n) => n.dataset.node === map.dataset.at));
  let target = at;
  let walking = false;

  const point = (i) => ({ x: Number(nodes[i].dataset.x), y: Number(nodes[i].dataset.y) });
  const place = (i) => {
    const p = point(i);
    knight.style.left = `${p.x}%`;
    knight.style.top = `${p.y}%`;
  };
  const show = (i) => {
    const id = nodes[i].dataset.node;
    panels.forEach((p) => (p.hidden = p.dataset.panel !== id));
    nodes.forEach((n, k) => {
      n.classList.toggle("here", k === i);
      n.setAttribute("aria-current", k === i ? "location" : "false");
    });
    document.cookie = `hollow_at_${map.dataset.map}=${id}; path=/; max-age=31536000; samesite=lax`;
  };

  async function walk() {
    if (walking) return;
    walking = true;
    knight.classList.add("walking");
    while (at !== target) {
      const next = at + (target > at ? 1 : -1);
      const a = point(at);
      const b = point(next);
      knight.classList.toggle("facing-left", b.x < a.x);
      const dist = Math.hypot(((b.x - a.x) / 100) * w, ((b.y - a.y) / 100) * h);
      if (!still) {
        const step = knight.animate(
          [{ left: `${a.x}%`, top: `${a.y}%` }, { left: `${b.x}%`, top: `${b.y}%` }],
          { duration: dist * MS_PER_PIXEL, easing: "linear" },
        );
        place(next);
        await step.finished;
      } else {
        place(next);
      }
      at = next;
    }
    knight.classList.remove("walking");
    walking = false;
    show(at);
  }

  const go = (i) => {
    target = Math.min(nodes.length - 1, Math.max(0, i));
    if (target === at && !walking) show(at);
    walk();
  };

  const open = () => {
    const action = document.querySelector(`[data-panel="${nodes[at].dataset.node}"] [data-action]`);
    if (action) action.click();
  };

  // Clicking a place walks there; clicking the place you stand on opens it.
  nodes.forEach((n, i) =>
    n.addEventListener("click", (e) => {
      e.preventDefault();
      if (i === at && !walking) open();
      else go(i);
    }),
  );
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select")) return;
    if (["ArrowRight", "ArrowUp", "d", "w"].includes(e.key)) go(target + 1);
    else if (["ArrowLeft", "ArrowDown", "a", "s"].includes(e.key)) go(target - 1);
    else if (e.key === "Enter" && !e.target.closest("a, button")) open();
    else return;
    e.preventDefault();
    nodes[target].focus({ preventScroll: true }); // Enter on the focused place then opens it
  });

  place(at);
  show(at);
})();
