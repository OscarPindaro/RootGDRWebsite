/* Command palette: Alt+Space or Cmd/Ctrl+K over a native <dialog>.
 *
 * The dialog reuses common.Dialog.js for the focus trap (native showModal()),
 * Escape, and focus return to the opener that was actually clicked. This file
 * owns only the search: debounce, abort, ordering, the active descendant and
 * the initial/loading/results/empty/offline/unauthorized/error states.
 */
(function () {
  "use strict";

  var dialog = document.getElementById("palette");
  if (!dialog) return;
  var input = dialog.querySelector(".palette__input");
  var list = dialog.querySelector(".palette__list");
  var state = dialog.querySelector("[data-palette-state]");
  var message = dialog.querySelector("[data-palette-message]");
  var retry = dialog.querySelector("[data-palette-retry]");
  var status = dialog.querySelector("[data-palette-status]");
  var worldId = dialog.dataset.worldId || "";

  var DEBOUNCE_MS = 150;
  var MESSAGES = {
    loading: "Caricamento…",
    empty: "Nessun risultato.",
    offline: "Sei offline. Controlla la connessione e riprova.",
    unauthorized: "Sessione scaduta. Ricarica la pagina per continuare.",
    error: "Non è stato possibile cercare. Riprova."
  };

  var results = [];
  var options = [];
  var active = -1;
  var controller = null;
  var sequence = 0;
  var debounceTimer = null;

  function announce(text) {
    status.textContent = text;
  }

  /* A text field or the editor owns Ctrl/Cmd+K and Alt+Space: opening the
     palette there would break typing or shadow an editor command. */
  function editable(element) {
    if (!element) return false;
    if (element.isContentEditable) return true;
    var tag = element.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  }

  /* A hotkey has no clicked trigger: return focus to the search control the
     current breakpoint shows (the rail on desktop, the topbar on a phone). */
  function visibleOpener() {
    var openers = document.querySelectorAll("[data-open-palette]");
    for (var i = 0; i < openers.length; i += 1) {
      if (openers[i].offsetParent !== null) return openers[i];
    }
    return null;
  }

  function clearActive() {
    active = -1;
    input.removeAttribute("aria-activedescendant");
  }

  function setActive(index) {
    if (!options.length) {
      clearActive();
      return;
    }
    active = (index + options.length) % options.length;
    options.forEach(function (option, i) {
      var isActive = i === active;
      option.classList.toggle("is-active", isActive);
      option.setAttribute("aria-selected", String(isActive));
    });
    input.setAttribute("aria-activedescendant", options[active].id);
    options[active].scrollIntoView({ block: "nearest" });
  }

  /* Result names come from user content: build nodes and set text, never HTML. */
  function optionNode(item, index) {
    var option = document.createElement("li");
    option.className = "palette__item";
    option.id = "palette-option-" + index;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");

    var kind = document.createElement("span");
    kind.className = "palette__kind";
    kind.textContent = item.kind;

    var name = document.createElement("span");
    name.className = "palette__name";
    name.textContent = item.name;

    var hint = document.createElement("span");
    hint.className = "palette__hint";
    hint.textContent = "↵";
    hint.setAttribute("aria-hidden", "true");

    option.appendChild(kind);
    option.appendChild(name);
    option.appendChild(hint);
    option.addEventListener("mouseenter", function () { setActive(index); });
    option.addEventListener("click", function () { follow(item); });
    return option;
  }

  function showList(items) {
    results = items;
    options = [];
    list.textContent = "";
    items.forEach(function (item, index) {
      var option = optionNode(item, index);
      list.appendChild(option);
      options.push(option);
    });
    list.hidden = false;
    state.hidden = true;
    input.setAttribute("aria-expanded", "true");
    setActive(0);
    announce(items.length === 1 ? "1 risultato" : items.length + " risultati");
  }

  function showState(kind) {
    results = [];
    options = [];
    list.textContent = "";
    list.hidden = true;
    clearActive();
    input.setAttribute("aria-expanded", "false");
    state.hidden = false;
    message.textContent = MESSAGES[kind];
    retry.hidden = kind !== "offline" && kind !== "error";
    announce(MESSAGES[kind]);
  }

  function follow(item) {
    if (item && item.href) window.location.assign(item.href);
  }

  function endpoint(query) {
    var url = "/api/palette?q=" + encodeURIComponent(query);
    if (worldId) url += "&world_id=" + encodeURIComponent(worldId);
    return url;
  }

  function run(query) {
    var current = (sequence += 1);
    if (controller) controller.abort();
    controller = new AbortController();
    // Do not even attempt the request offline: the failure is known up front.
    if (navigator.onLine === false) {
      showState("offline");
      return;
    }
    showState("loading");
    fetch(endpoint(query), {
      headers: { Accept: "application/json" },
      signal: controller.signal
    })
      .then(function (response) {
        if (current !== sequence) return null;
        if (response.status === 401) {
          showState("unauthorized");
          return null;
        }
        if (!response.ok) {
          showState("error");
          return null;
        }
        return response.json().then(function (payload) {
          if (current !== sequence) return;
          var items = (payload && payload.data) || [];
          if (items.length) showList(items);
          else showState("empty");
        });
      })
      .catch(function (error) {
        if (error && error.name === "AbortError") return;
        if (current !== sequence) return;
        showState(navigator.onLine === false ? "offline" : "error");
      });
  }

  function search(query) {
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(function () { run(query); }, DEBOUNCE_MS);
  }

  function open(opener) {
    window.clearTimeout(debounceTimer);
    if (controller) controller.abort();
    sequence += 1;
    input.value = "";
    window.rootGdrDialog.open(dialog, opener || visibleOpener());
    run("");
  }

  function close() {
    window.clearTimeout(debounceTimer);
    if (controller) controller.abort();
    window.rootGdrDialog.close(dialog);
  }

  input.addEventListener("input", function () { search(input.value); });

  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive(active + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(active - 1);
    } else if (event.key === "Home" && options.length) {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End" && options.length) {
      event.preventDefault();
      setActive(options.length - 1);
    } else if (event.key === "Enter" && active >= 0 && results[active]) {
      event.preventDefault();
      follow(results[active]);
    }
  });

  retry.addEventListener("click", function () {
    input.focus();
    run(input.value);
  });

  /* The native backdrop is part of the <dialog> box: a click on it closes. */
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) close();
  });

  /* showModal() owns the focus trap; some browsers let Tab drop focus onto the
     inert document root. Restore the query field so the palette stays the one
     active surface. This is a guard, not a second Tab trap. */
  dialog.addEventListener("focusout", function (event) {
    if (!dialog.open) return;
    if (event.relatedTarget && dialog.contains(event.relatedTarget)) return;
    if (event.relatedTarget === null || event.relatedTarget === document.body) {
      input.focus();
    }
  });

  document.addEventListener("click", function (event) {
    if (!(event.target instanceof Element)) return;
    var trigger = event.target.closest("[data-open-palette]");
    if (!trigger) return;
    event.preventDefault();
    open(trigger);
  });

  document.addEventListener("keydown", function (event) {
    var hotkey =
      (event.altKey && event.code === "Space") ||
      ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k");
    if (!hotkey) return;
    // While open the query field owns the keyboard; Escape closes the dialog.
    if (dialog.open) {
      event.preventDefault();
      return;
    }
    // A text field or the editor owns these shortcuts; a stale focus left on
    // the palette's own (now hidden) input must not block reopening it.
    if (editable(document.activeElement) && !dialog.contains(document.activeElement)) {
      return;
    }
    event.preventDefault();
    open(visibleOpener());
  });
})();
