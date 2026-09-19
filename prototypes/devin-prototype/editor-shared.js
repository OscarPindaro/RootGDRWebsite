/* ============================================================
   editor-shared.js — pezzi comuni alle pagine di confronto:
   ricerca fuzzy delle reference, pillola, menu dei suggerimenti
   e stato di blocco. Ogni pagina collega solo il proprio motore.
   ============================================================ */
(function () {
  "use strict";

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  /* pillola di una reference: lo stesso markup che emette il server,
     cioè solo semantica. L'aspetto è nel foglio di stile. */
  function pill(entry, label) {
    if (!entry) {
      return '<span class="mention mention--missing" title="Nessun contenuto con questo nome">@' +
        esc(label || "") + "</span>";
    }
    return '<a class="mention" href="' + entry.href + '" data-kind="' + esc(entry.kind) +
      '" data-color="' + esc(entry.tint) + '" title="' + esc(entry.kind) + '">' +
      esc(entry.name) + "</a>";
  }

  /* evidenzia le lettere che hanno fatto match, anche non consecutive */
  function highlight(name, query) {
    if (!query) return esc(name);
    var q = query.toLowerCase();
    var t = name.toLowerCase();
    var qi = 0;
    var out = "";
    for (var i = 0; i < name.length; i++) {
      if (qi < q.length && t.charAt(i) === q.charAt(qi)) {
        out += "<mark>" + esc(name.charAt(i)) + "</mark>";
        qi++;
      } else {
        out += esc(name.charAt(i));
      }
    }
    return out;
  }

  function search(query) {
    return window.ENTITIES ? window.ENTITIES.search(query) : [];
  }

  /* ---------- menu dei suggerimenti ----------
     Si posiziona in coordinate di viewport (position: fixed), così
     funziona con qualunque motore senza sapere dov'è il cursore. */
  function createPopup() {
    var el = document.createElement("div");
    el.className = "mention-menu mention-menu--floating";
    el.setAttribute("role", "listbox");
    el.hidden = true;
    document.body.appendChild(el);

    var items = [];
    var active = 0;
    var onPick = null;
    var open = false;

    function paint(query) {
      el.innerHTML = "";
      if (!items.length) {
        var none = document.createElement("div");
        none.className = "mention-menu__empty";
        none.textContent = "Nessun contenuto con questo nome";
        el.appendChild(none);
        return;
      }
      items.forEach(function (entry, index) {
        var item = document.createElement("button");
        item.type = "button";
        item.className = "mention-menu__item";
        item.setAttribute("aria-selected", String(index === active));
        item.style.setProperty("--c", "var(" + entry.color + ")");
        item.innerHTML =
          '<span class="mention-menu__dot"></span>' +
          '<span class="mention-menu__name">' + highlight(entry.name, query) + "</span>" +
          '<span class="mention-menu__kind">' + esc(entry.kind) + "</span>";
        item.addEventListener("mousedown", function (e) {
          e.preventDefault();
          pick(index);
        });
        el.appendChild(item);
      });
    }

    function place(anchor) {
      if (!anchor) return;
      var box = el.getBoundingClientRect();
      var left = Math.min(Math.max(8, anchor.left), window.innerWidth - box.width - 8);
      var top = anchor.bottom + 4;
      if (top + box.height > window.innerHeight - 8) top = Math.max(8, anchor.top - box.height - 4);
      el.style.left = left + "px";
      el.style.top = top + "px";
    }

    function pick(index) {
      var entry = items[index];
      if (entry && onPick) onPick(entry);
      close();
    }

    function show(list, query, anchor, picker) {
      items = list;
      active = 0;
      onPick = picker;
      open = true;
      paint(query);
      el.hidden = false;
      place(anchor);
    }

    function close() {
      open = false;
      el.hidden = true;
      items = [];
    }

    function move(step) {
      if (!open || !items.length) return;
      active = (active + step + items.length) % items.length;
      Array.prototype.forEach.call(el.children, function (node, index) {
        if (node.className.indexOf("mention-menu__item") < 0) return;
        node.setAttribute("aria-selected", String(index === active));
      });
    }

    return {
      show: show,
      close: close,
      move: move,
      pick: pick,
      pickActive: function () { pick(active); },
      isOpen: function () { return open; },
      count: function () { return items.length; }
    };
  }

  /* blocco del documento: vale per qualunque motore */
  function wireLock(onChange) {
    var button = document.querySelector("[data-doc-lock]");
    var doc = document.querySelector("[data-doc]");
    if (!button || !doc) return;
    function paint() {
      var locked = doc.getAttribute("data-locked") === "true";
      button.textContent = locked ? "Bloccato" : "Sbloccato";
      button.setAttribute("aria-pressed", String(locked));
      doc.classList.toggle("is-locked", locked);
    }
    button.addEventListener("click", function () {
      var locked = doc.getAttribute("data-locked") === "true";
      doc.setAttribute("data-locked", String(!locked));
      paint();
      if (onChange) onChange(!locked);
    });
    paint();
  }

  window.EditorShared = {
    pill: pill,
    search: search,
    esc: esc,
    createPopup: createPopup,
    wireLock: wireLock
  };
})();
