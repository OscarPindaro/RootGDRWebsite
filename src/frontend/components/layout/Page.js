/* Behaviour for the page shell: the phone rail is a modal drawer.
 *
 * On a phone the rail slides in over the page. While it is open the rest of
 * the shell is `inert`, the body cannot scroll, Tab is contained inside the
 * drawer, and Escape or the scrim closes it and returns focus to the control
 * that opened it. A native <dialog> cannot host the rail (it is a landmark,
 * not a dialog), so the containment is enforced here rather than by
 * showModal(). Ordinary navigation keeps native Tab order; the rail is not an
 * ARIA composite widget. common.Menu keeps its own APG arrow model.
 */
(function () {
  "use strict";

  var FOCUSABLE = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    '[tabindex]:not([tabindex="-1"])',
  ].join(",");

  function rail() {
    return document.getElementById("rail");
  }

  function scrim() {
    return document.getElementById("scrim");
  }

  function toggle() {
    return document.getElementById("drawer-toggle");
  }

  function isOpen() {
    var element = rail();
    return Boolean(element && element.classList.contains("is-open"));
  }

  /* Everything in the shell except the drawer and its scrim goes inert. */
  function background() {
    var shell = document.querySelector(".shell");
    if (!shell) return [];
    return Array.prototype.filter.call(shell.children, function (child) {
      return child.id !== "rail" && child.id !== "scrim";
    });
  }

  function focusables(root) {
    return Array.prototype.filter.call(
      root.querySelectorAll(FOCUSABLE),
      function (element) {
        return element.offsetParent !== null;
      }
    );
  }

  var opener = null;

  function setOpen(open, restoreFocus) {
    var drawer = rail();
    var shade = scrim();
    var trigger = toggle();
    if (!drawer || !shade || open === isOpen()) return;

    drawer.classList.toggle("is-open", open);
    shade.classList.toggle("is-open", open);
    if (trigger) trigger.setAttribute("aria-expanded", String(open));
    background().forEach(function (element) {
      if (open) element.setAttribute("inert", "");
      else element.removeAttribute("inert");
    });
    document.body.classList.toggle("drawer-open", open);

    if (open) {
      var first = focusables(drawer)[0];
      if (first) first.focus();
    } else if (restoreFocus) {
      var back = opener && document.contains(opener) ? opener : trigger;
      if (back) back.focus();
    }
    if (!open) opener = null;
  }

  document.addEventListener("click", function (event) {
    if (!(event.target instanceof Element)) return;

    var trigger = event.target.closest("#drawer-toggle");
    if (trigger) {
      opener = trigger;
      setOpen(!isOpen(), false);
      return;
    }

    if (event.target.id === "scrim") {
      setOpen(false, true);
      return;
    }

    /* The palette is another modal surface: closing the drawer first lets it
       take focus instead of landing inside an inert background. */
    if (isOpen() && event.target.closest("[data-open-palette]")) {
      setOpen(false, false);
      return;
    }

    /* A selected navigation link closes the drawer but does not restore focus
       to the opener: the browser is about to navigate, and moving focus back
       first would flash the opener's focus ring before the new page paints. */
    if (isOpen() && event.target.closest("#rail a[href]")) {
      setOpen(false, false);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (!isOpen()) return;

    if (event.key === "Escape") {
      /* An open Menu handles Escape itself (its own popover, its own focus
         return); do not also close the drawer behind it. */
      if (event.defaultPrevented) return;
      if (document.querySelector("[data-menu]:popover-open")) return;
      event.preventDefault();
      setOpen(false, true);
      return;
    }

    /* Alt+Space and Ctrl/Cmd+K open the palette; close the drawer so the
       palette does not open inside an inert background. */
    if (
      (event.altKey && event.code === "Space") ||
      ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")
    ) {
      setOpen(false, false);
      return;
    }

    if (event.key !== "Tab") return;
    var drawer = rail();
    var items = focusables(drawer);
    if (!items.length) return;
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    } else if (!drawer.contains(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });
})();
