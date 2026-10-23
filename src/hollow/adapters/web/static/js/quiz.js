// Number keys pick a quiz option. Registered once; works after HTMX swaps the quiz in.
document.addEventListener("keydown", (e) => {
  if (e.altKey || e.ctrlKey || e.metaKey || e.target.closest("input, textarea, select")) return;
  const n = Number(e.key);
  if (!Number.isInteger(n) || n < 1) return;
  const form = document.querySelector("[data-choices]");
  const option = form && form.querySelectorAll("button.option")[n - 1];
  if (option) {
    e.preventDefault();
    option.click();
  }
});

// When a quiz swaps in below a lesson, bring it into view.
document.addEventListener("htmx:afterSwap", (e) => {
  const lesson = document.querySelector(".arch-lesson");
  if (lesson && e.detail.target && e.detail.target.id === "lesson") {
    document.getElementById("lesson").scrollIntoView({ block: "start", behavior: "smooth" });
  }
});
