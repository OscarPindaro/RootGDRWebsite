/* Page shell: the rail becomes an off-canvas drawer on small screens.
   Event delegation keeps it working when htmx swaps content in. */
(function () {
  "use strict";

  function setOpen(open) {
    var rail = document.getElementById("rail");
    var scrim = document.getElementById("scrim");
    var toggle = document.getElementById("drawer-toggle");
    if (!rail || !scrim || !toggle) return;
    rail.classList.toggle("is-open", open);
    scrim.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (open) {
      var first = rail.querySelector("a, button");
      if (first) first.focus();
    } else {
      toggle.focus();
    }
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("#drawer-toggle");
    if (toggle) {
      var rail = document.getElementById("rail");
      setOpen(!(rail && rail.classList.contains("is-open")));
      return;
    }
    if (event.target.id === "scrim") setOpen(false);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var rail = document.getElementById("rail");
    if (rail && rail.classList.contains("is-open")) setOpen(false);
  });
})();
