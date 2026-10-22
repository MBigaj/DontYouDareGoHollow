// Phase timers: when the bar runs out, the answer as typed so far is submitted.
(() => {
  let frame = 0;
  const arm = () => {
    cancelAnimationFrame(frame);
    const timer = document.querySelector("#fight .timer");
    const form = document.querySelector("[data-fight-form]");
    if (!timer || !form) return;
    const total = Number(timer.dataset.seconds) * 1000;
    const bar = timer.querySelector("span");
    const start = performance.now();
    const tick = (now) => {
      const left = Math.max(0, 1 - (now - start) / total);
      bar.style.width = `${left * 100}%`;
      timer.classList.toggle("low", left < 0.25);
      if (left > 0) frame = requestAnimationFrame(tick);
      else form.requestSubmit();
    };
    frame = requestAnimationFrame(tick);
  };
  document.addEventListener("htmx:afterSettle", arm);
  document.addEventListener("DOMContentLoaded", arm);
  if (document.readyState !== "loading") arm();
})();
