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

  /* Arrow Up/Down and Home/End move through the rail's navigation, so the
     whole sidebar is keyboard-operable without a mouse. */
  document.addEventListener("keydown", function (event) {
    var rail = document.getElementById("rail");
    if (!rail || !rail.contains(document.activeElement)) return;
    var keys = ["ArrowDown", "ArrowUp", "Home", "End"];
    if (keys.indexOf(event.key) === -1) return;
    var items = Array.prototype.slice.call(
      rail.querySelectorAll("a[href], button:not([disabled])"),
    );
    if (!items.length) return;
    var index = items.indexOf(document.activeElement);
    event.preventDefault();
    if (event.key === "Home") index = 0;
    else if (event.key === "End") index = items.length - 1;
    else if (event.key === "ArrowDown") index = (index + 1) % items.length;
    else index = (index - 1 + items.length) % items.length;
    items[index].focus();
  });
})();
