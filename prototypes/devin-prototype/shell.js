/* ============================================================
   shell.js — inietta rail e topbar in ogni pagina.
   Un prototipo statico multipagina: la shell è unica, il
   contenuto è reale in ogni file. Ogni pagina dichiara il
   proprio contesto su <body data-page data-world>.
   ============================================================ */
(function () {
  "use strict";

  var PAGES = [
    { id: "mondo", label: "Panoramica", href: "mondo.html" },
    { id: "personaggi", label: "Personaggi", href: "personaggi.html",
      countUnite: 14, countSeparate: 6 },
    { id: "npc", label: "NPC", href: "npc.html", count: 8, nav: "npc" },
    { id: "luoghi", label: "Luoghi", href: "luoghi.html", count: 12 },
    { id: "sessioni", label: "Sessioni", href: "sessioni.html", count: 8 },
    { id: "storie", label: "Storie", href: "storie.html", count: 3 },
    { id: "pagine", label: "Pagine", href: "pagine.html", count: 4 }
  ];

  var STATIC_PAGES = [
    { label: "Le regole della Casa", href: "pagina.html" },
    { label: "Le fazioni di Boscochiaro", href: "pagina.html" },
    { label: "Calendario e stagioni", href: "pagina.html" },
    { label: "Storia del Bosco", href: "pagina.html" }
  ];

  /* una pagina di dettaglio mantiene attiva la voce del suo elenco */
  var PARENT = {
    personaggio: "personaggi",
    luogo: "luoghi",
    sessione: "sessioni",
    storia: "storie",
    pagina: "pagine"
  };

  /* Pannello preferenze: esiste SOLO nel prototipo.
     In produzione questi controlli non stanno nel rail e i valori non
     vengono da localStorage: sono preferenze dell'utente, salvate sul
     record utente e modificabili in una pagina impostazioni. Servono
     qui per confrontare le varianti senza ricostruire il prototipo.
     Vedi docs/features/frontend.md. */
  var PREFS = [
    {
      id: "simboli",
      label: "Simboli",
      options: [["icone", "Icone"], ["forme", "Forme"]],
      current: function () { return window.MARKS.mode(); },
      set: function (value) { window.MARKS.setMode(value); }
    },
    {
      id: "accenti",
      label: "Accenti",
      options: [["pieno", "Pieno"], ["gradiente", "Gradiente"]],
      current: function () { return window.MARKS.accent(); },
      set: function (value) { window.MARKS.setAccent(value); }
    },
    {
      id: "viste",
      label: "Viste",
      options: [["unite", "Unite"], ["separate", "Separate"]],
      current: function () { return window.MARKS.views(); },
      set: function (value) { window.MARKS.setViews(value); }
    },
    {
      id: "editor",
      label: "Editor",
      options: [["modulo", "Modulo"], ["documento", "Documento"]],
      current: function () { return window.MARKS.editor(); },
      set: function (value) { window.MARKS.setEditor(value); }
    }
  ];

  var WORLD = {
    name: "Le Cronache di Boscochiaro",
    role: "Master",
    slug: "boscochiaro"
  };

  var USER = { name: "Oscar", mail: "oscar@boscochiaro.it" };

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  function currentId() {
    var raw = document.body.dataset.page || "mondi";
    return PARENT[raw] || raw;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function buildRail() {
    var rail = document.getElementById("rail");
    if (!rail) return;

    /* il contenuto vive in un wrapper sticky: la colonna scura copre tutta
       l'altezza del documento, il contenuto resta fermo mentre si scorre */
    var inner = el("div", "rail__inner");
    rail.appendChild(inner);
    rail = inner;

    var inWorld = document.body.dataset.world === "boscochiaro";
    var active = currentId();

    if (!inWorld) {
      rail.appendChild(el("div", "rail__top",
        '<a class="rail__back" href="index.html">Boscochiaro · Archivio</a>'));

      var idBox = el("div", "rail__identity",
        '<span class="rail__mark" aria-hidden="true"></span>' +
        '<div><a class="rail__world" href="index.html">I tuoi mondi</a>' +
        '<div class="rail__role">3 mondi accessibili</div></div>');
      rail.appendChild(idBox);

      var nav = el("nav", "rail__nav");
      nav.setAttribute("aria-label", "Navigazione principale");
      [
        { id: "mondi", label: "Tutti i mondi", href: "index.html" },
        { id: "attivita", label: "Attività recente", href: "mondo.html" },
        { id: "profilo", label: "Profilo", href: "#" }
      ].forEach(function (item) {
        var a = el("a", "navitem",
          '<span class="navitem__mark mark" data-mark="' + item.id + '"></span>' +
          '<span class="navitem__text">' + esc(item.label) + "</span>");
        a.href = item.href;
        if (item.id === active) a.setAttribute("aria-current", "page");
        nav.appendChild(a);
      });
      rail.appendChild(nav);
    } else {
      rail.appendChild(el("div", "rail__top",
        '<a class="rail__back" href="index.html">← Tutti i mondi</a>'));

      rail.appendChild(el("div", "rail__identity",
        '<span class="rail__mark" aria-hidden="true"></span>' +
        '<div><a class="rail__world" href="mondo.html">' + esc(WORLD.name) + "</a>" +
        '<div class="rail__role">' + esc(WORLD.role) + " · Boscochiaro</div></div>"));

      var nav2 = el("nav", "rail__nav");
      nav2.setAttribute("aria-label", "Navigazione del mondo");
      PAGES.forEach(function (p) {
        var count = "";
        if (p.countUnite != null) {
          count = '<span class="navitem__count only-unite">' + p.countUnite + "</span>" +
            '<span class="navitem__count only-separate">' + p.countSeparate + "</span>";
        } else if (p.count != null) {
          count = '<span class="navitem__count">' + p.count + "</span>";
        }
        var a = el("a", "navitem",
          '<span class="navitem__mark mark" data-mark="' + p.id + '"></span>' +
          '<span class="navitem__text">' + esc(p.label) + "</span>" + count);
        a.href = p.href;
        if (p.nav) a.setAttribute("data-nav", p.nav);
        if (p.id === active) a.setAttribute("aria-current", "page");
        nav2.appendChild(a);
      });
      rail.appendChild(nav2);

      rail.appendChild(el("div", "rail__label", "Pagine statiche"));
      var nav3 = el("nav", "rail__nav");
      nav3.setAttribute("aria-label", "Pagine statiche");
      STATIC_PAGES.forEach(function (p) {
        var a = el("a", "navitem",
          '<span class="navitem__mark navitem__mark--sub mark" data-mark="pagina"></span>' +
          '<span class="navitem__text">' + esc(p.label) + "</span>");
        a.href = p.href;
        if (active === "pagine" && p.label === "Le regole della Casa") {
          a.setAttribute("aria-current", "page");
        }
        nav3.appendChild(a);
      });
      rail.appendChild(nav3);
    }

    var foot = el("div", "rail__foot");

    /* controlli temporanei: da rimuovere quando esisterà la pagina
       impostazioni utente (docs/features/frontend.md) */
    var prefs = el("div", "prefs");
    var prefsToggle = el("button", "prefs__toggle",
      "<span>Preferenze</span><span aria-hidden=\"true\">▾</span>");
    prefsToggle.type = "button";
    prefsToggle.setAttribute("aria-expanded", "false");
    var prefsRows = el("div", "prefs__rows");

    PREFS.forEach(function (pref) {
      var wrap = el("div", "markswitch");
      wrap.appendChild(el("span", "markswitch__label", pref.label));
      var segmented = el("div", "segmented");
      segmented.setAttribute("role", "group");
      segmented.setAttribute("aria-label", pref.label);
      pref.options.forEach(function (pair) {
        var b = el("button", "segmented__btn", pair[1]);
        b.type = "button";
        b.setAttribute("data-pref", pref.id);
        b.setAttribute("data-pref-value", pair[0]);
        segmented.appendChild(b);
      });
      wrap.appendChild(segmented);
      prefsRows.appendChild(wrap);
    });

    prefsToggle.addEventListener("click", function () {
      var open = prefs.classList.toggle("is-open");
      prefsToggle.setAttribute("aria-expanded", String(open));
    });
    prefs.appendChild(prefsToggle);
    prefs.appendChild(prefsRows);
    foot.appendChild(prefs);

    var search = el("button", "btn btn--ghost btn--sm",
      '<span class="mono">Cerca</span><span class="mono muted">Alt+Spazio</span>');
    search.type = "button";
    search.setAttribute("data-open-palette", "");
    foot.appendChild(search);

    /* porta d'ingresso al confronto dei motori di scrittura */
    var engines = el("a", "btn btn--ghost btn--sm",
      '<span class="mono">Motori di scrittura</span><span aria-hidden="true">→</span>');
    engines.href = "editor.html";
    foot.appendChild(engines);

    var compare = el("a", "btn btn--ghost btn--sm",
      '<span class="mono">Editor contro server</span><span aria-hidden="true">→</span>');
    compare.href = "render-compare.html";
    foot.appendChild(compare);

    var user = el("a", "rail__user",
      '<span class="rail__avatar">' + esc(USER.name.charAt(0)) + "</span>" +
      '<span><span class="rail__user-name">' + esc(USER.name) + "</span><br>" +
      '<span class="rail__user-mail">' + esc(USER.mail) + "</span></span>");
    user.href = "#";
    foot.appendChild(user);
    rail.appendChild(foot);
  }

  function buildTopbar() {
    var bar = document.getElementById("topbar");
    if (!bar) return;
    var inWorld = document.body.dataset.world === "boscochiaro";

    var toggle = el("button", "btn btn--icon", "☰");
    toggle.type = "button";
    toggle.setAttribute("aria-label", "Apri la navigazione");
    toggle.setAttribute("aria-expanded", "false");
    toggle.id = "drawer-toggle";
    bar.appendChild(toggle);

    bar.appendChild(el("span", "topbar__title",
      inWorld ? esc(WORLD.name) : "Boscochiaro · Archivio"));

    var search = el("button", "btn btn--sm", "Cerca");
    search.type = "button";
    search.style.marginLeft = "auto";
    search.setAttribute("data-open-palette", "");
    bar.appendChild(search);
  }

  function wireDrawer() {
    var rail = document.getElementById("rail");
    var toggle = document.getElementById("drawer-toggle");
    var scrim = document.getElementById("scrim");
    if (!rail || !toggle || !scrim) return;

    function setOpen(open) {
      rail.classList.toggle("is-open", open);
      scrim.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
    }

    toggle.addEventListener("click", function () {
      setOpen(!rail.classList.contains("is-open"));
    });
    scrim.addEventListener("click", function () { setOpen(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setOpen(false);
    });
  }

  /* ---------- command palette ---------- */
  var PALETTE_ITEMS = PAGES.map(function (p) {
    return { kind: "Sezione", name: p.label, href: p.href };
  }).concat(
    STATIC_PAGES.map(function (p) {
      return { kind: "Pagina", name: p.label, href: p.href };
    }),
    [
      { kind: "Personaggio", name: "Rugginosa, la Senza Tana", href: "personaggio.html" },
      { kind: "Personaggio", name: "Barone Talpa", href: "personaggio.html" },
      { kind: "NPC", name: "La Marchesa", href: "npc.html" },
      { kind: "NPC", name: "Madre Civetta", href: "npc.html" },
      { kind: "Luogo", name: "Radura della Grande Quercia", href: "luogo.html" },
      { kind: "Sessione", name: "08 · L'inverno dei corvi", href: "sessione.html" },
      { kind: "Storia", name: "La caduta di Torre dell'Aquila", href: "storia.html" },
      { kind: "Luogo", name: "Il Cerchio di Pietre", href: "luogo.html" },
      { kind: "Azione", name: "Nuovo personaggio", href: "nuovo-personaggio.html" },
      { kind: "Prova", name: "Motori di scrittura", href: "editor.html" },
      { kind: "Prova", name: "Editor contro server", href: "render-compare.html" },
      { kind: "Azione", name: "Torna a tutti i mondi", href: "index.html" }
    ]
  );

  function buildPalette() {
    var wrap = el("div", "palette");
    wrap.id = "palette";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-label", "Cerca nell'archivio");

    var box = el("div", "palette__box");
    var input = el("input", "palette__input");
    input.type = "text";
    input.placeholder = "Cerca sezioni, personaggi, luoghi…";
    input.setAttribute("aria-label", "Cerca");
    box.appendChild(input);

    var list = el("div", "palette__list");
    box.appendChild(list);
    wrap.appendChild(box);
    document.body.appendChild(wrap);

    var results = [];
    var cursor = 0;

    function render(q) {
      var query = q.trim().toLowerCase();
      results = PALETTE_ITEMS.filter(function (it) {
        return !query || it.name.toLowerCase().indexOf(query) !== -1 ||
          it.kind.toLowerCase().indexOf(query) !== -1;
      }).slice(0, 9);
      cursor = 0;
      list.innerHTML = "";
      if (!results.length) {
        list.appendChild(el("div", "palette__empty", "Nessun risultato."));
        return;
      }
      results.forEach(function (it, i) {
        var a = el("a", "palette__item" + (i === 0 ? " is-active" : ""),
          '<span class="palette__kind">' + esc(it.kind) + "</span>" +
          '<span class="palette__name">' + esc(it.name) + "</span>" +
          '<span class="palette__hint">↵</span>');
        a.href = it.href;
        a.addEventListener("mouseenter", function () { setCursor(i); });
        list.appendChild(a);
      });
    }

    function setCursor(i) {
      cursor = (i + results.length) % results.length;
      Array.prototype.forEach.call(list.children, function (node, idx) {
        node.classList.toggle("is-active", idx === cursor);
      });
    }

    function open() {
      render("");
      input.value = "";
      wrap.classList.add("is-open");
      input.focus();
    }
    function close() { wrap.classList.remove("is-open"); }

    input.addEventListener("input", function () { render(input.value); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); setCursor(cursor + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setCursor(cursor - 1); }
      else if (e.key === "Enter" && results[cursor]) {
        e.preventDefault();
        window.location.href = results[cursor].href;
      }
    });
    wrap.addEventListener("click", function (e) { if (e.target === wrap) close(); });

    document.addEventListener("keydown", function (e) {
      var hotkey = (e.altKey && e.code === "Space") || (e.metaKey && e.key.toLowerCase() === "k");
      if (hotkey) { e.preventDefault(); wrap.classList.contains("is-open") ? close() : open(); }
      else if (e.key === "Escape" && wrap.classList.contains("is-open")) close();
    });

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-open-palette]"),
      function (btn) { btn.addEventListener("click", open); }
    );
  }

  var prefPaints = [];

  /* le pagine possono reagire a un cambio di preferenza (per esempio
     rimisurando un campo che era nascosto) */
  function announce(id, value) {
    document.dispatchEvent(new CustomEvent("prefchange", { detail: { id: id, value: value } }));
  }

  function wirePrefs() {
    PREFS.forEach(function (pref) {
      var buttons = document.querySelectorAll('[data-pref="' + pref.id + '"]');
      function paint() {
        Array.prototype.forEach.call(buttons, function (b) {
          var on = b.getAttribute("data-pref-value") === pref.current();
          b.setAttribute("aria-pressed", String(on));
        });
      }
      Array.prototype.forEach.call(buttons, function (b) {
        b.addEventListener("click", function () {
          var value = b.getAttribute("data-pref-value");
          pref.set(value);
          paint();
          announce(pref.id, value);
        });
      });
      prefPaints.push(paint);
      paint();
    });

    /* scorciatoie dentro le pagine: cambiano una preferenza e riallineano il rail */
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-set-pref]"),
      function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-set-pref");
          var value = btn.getAttribute("data-set-value");
          PREFS.forEach(function (pref) {
            if (pref.id !== id) return;
            pref.set(value);
            prefPaints.forEach(function (paint) { paint(); });
            announce(pref.id, value);
          });
        });
      }
    );
  }

  buildRail();
  buildTopbar();
  wireDrawer();
  buildPalette();
  window.MARKS.applyAll();
  wirePrefs();
})();
