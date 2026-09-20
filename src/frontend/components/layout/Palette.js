/* Command palette: Alt+Space or Cmd/Ctrl+K, results from the database. */
(function () {
  "use strict";

  var wrap = document.getElementById("palette");
  if (!wrap) return;
  var input = wrap.querySelector(".palette__input");
  var list = wrap.querySelector(".palette__list");
  var worldId = wrap.dataset.worldId || "";
  var results = [];
  var cursor = 0;
  var controller = null;

  function esc(value) {
    return String(value).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function paint() {
    list.innerHTML = "";
    if (!results.length) {
      var empty = document.createElement("div");
      empty.className = "palette__empty";
      empty.textContent = "Nessun risultato.";
      list.appendChild(empty);
      return;
    }
    results.forEach(function (item, index) {
      var a = document.createElement("a");
      a.className = "palette__item" + (index === cursor ? " is-active" : "");
      a.href = item.href;
      a.innerHTML =
        '<span class="palette__kind">' + esc(item.kind) + "</span>" +
        '<span class="palette__name">' + esc(item.name) + "</span>" +
        '<span class="palette__hint">↵</span>';
      a.addEventListener("mouseenter", function () {
        cursor = index;
        paint();
      });
      list.appendChild(a);
    });
  }

  function search(query) {
    if (controller) controller.abort();
    controller = new AbortController();
    var url = "/api/palette?q=" + encodeURIComponent(query);
    if (worldId) url += "&world_id=" + encodeURIComponent(worldId);
    fetch(url, { headers: { Accept: "application/json" }, signal: controller.signal })
      .then(function (response) {
        return response.ok ? response.json() : { data: [] };
      })
      .then(function (payload) {
        results = payload.data || [];
        cursor = 0;
        paint();
      })
      .catch(function () {});
  }

  function open() {
    wrap.classList.add("is-open");
    input.value = "";
    search("");
    input.focus();
  }

  function close() {
    wrap.classList.remove("is-open");
  }

  input.addEventListener("input", function () {
    search(input.value);
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      cursor = Math.min(cursor + 1, results.length - 1);
      paint();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      cursor = Math.max(cursor - 1, 0);
      paint();
    } else if (event.key === "Enter" && results[cursor]) {
      event.preventDefault();
      window.location.href = results[cursor].href;
    } else if (event.key === "Escape") {
      close();
    }
  });

  wrap.addEventListener("click", function (event) {
    if (event.target === wrap) close();
  });

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-open-palette]")) {
      event.preventDefault();
      open();
    }
  });

  document.addEventListener("keydown", function (event) {
    var hotkey =
      (event.altKey && event.code === "Space") ||
      (event.metaKey && event.key.toLowerCase() === "k") ||
      (event.ctrlKey && event.key.toLowerCase() === "k");
    if (hotkey) {
      event.preventDefault();
      wrap.classList.contains("is-open") ? close() : open();
    } else if (event.key === "Escape" && wrap.classList.contains("is-open")) {
      close();
    }
  });
})();
