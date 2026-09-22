(function () {
  if (window.__circeusMark) return;
  window.__circeusMark = true;

  // The server decides which presentation is active; this only reflects an
  // already-persisted choice. Both SVGs are in the markup, so switching is a
  // class flip and no mark has to be re-fetched.
  function apply(style) {
    if (style !== "icons" && style !== "shapes") return;
    document.querySelectorAll("[data-mark-style]").forEach(function (mark) {
      mark.setAttribute("data-mark-style", style);
      mark.classList.toggle("mark--icons", style === "icons");
      mark.classList.toggle("mark--shapes", style === "shapes");
    });
  }

  // SettingsStatus echoes the resolved style in the successful htmx response;
  // a failed request never swaps, so the marks stay on the server's value.
  document.body.addEventListener("htmx:afterSwap", function (event) {
    var source = event.target.querySelector("[data-symbol-style]");
    if (source) apply(source.getAttribute("data-symbol-style"));
  });
})();
