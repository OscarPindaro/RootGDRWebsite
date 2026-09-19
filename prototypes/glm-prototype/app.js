/* ==========================================================================
   Root GDR — prototipo GLM
   Shell condivisa multipagina: inietta sidebar + topbar, gestisce drawer
   mobile, collapse desktop e command palette (Alt+Space).
   ========================================================================== */

(function () {
  "use strict";

  var body = document.body;
  var page = body.dataset.page || "mondi";
  var worldId = body.dataset.world || null;
  var activeNav = body.dataset.nav || page;

  /* ---------- dati finti condivisi ------------------------------------- */

  var WORLDS = {
    "fronte-del-tuono": { name: "Fronte del Tuono", initials: "FT", cover: "🐻", role: "master" },
    "maree-di-nacre": { name: "Le Maree di Nacre", initials: "MN", cover: "🐙", role: "player" }
  };

  var NAV = [
    { key: "mondo",      label: "Panoramica", href: "mondo.html",      icon: "◈", count: null },
    { key: "personaggi", label: "Personaggi", href: "personaggi.html", icon: "♟", count: 12 },
    { key: "luoghi",     label: "Luoghi",     href: "luoghi.html",     icon: "◇", count: 8 },
    { key: "sessioni",   label: "Sessioni",   href: "sessioni.html",   icon: "◷", count: 24 },
    { key: "storie",     label: "Storie",     href: "storie.html",     icon: "▤", count: 6 },
    { key: "pagine",     label: "Pagine",     href: "pagine.html",     icon: "☰", count: 4 }
  ];

  /* pagine statiche del mondo, ordinate per posizione di menu */
  var PAGES = [
    { title: "Il mondo di gioco", href: "pagina.html", pos: 1 },
    { title: "Regole e riferimenti", href: "pagina.html", pos: 2 },
    { title: "Fazioni", href: "pagina.html", pos: 3 },
    { title: "Cronologia", href: "pagina.html", pos: 4 }
  ];

  /* indice per la command palette (niente indice lato server nel prototipo) */
  var INDEX = [
    { group: "Mondi", label: "Fronte del Tuono", href: "mondo.html", kind: "Mondo" },
    { group: "Mondi", label: "Le Maree di Nacre", href: "mondo.html", kind: "Mondo" },
    { group: "Vai a", label: "Panoramica del mondo", href: "mondo.html", kind: "Pagina" },
    { group: "Vai a", label: "Personaggi", href: "personaggi.html", kind: "Pagina" },
    { group: "Vai a", label: "Luoghi", href: "luoghi.html", kind: "Pagina" },
    { group: "Vai a", label: "Sessioni", href: "sessioni.html", kind: "Pagina" },
    { group: "Vai a", label: "Storie", href: "storie.html", kind: "Pagina" },
    { group: "Vai a", label: "Pagine", href: "pagine.html", kind: "Pagina" },
    { group: "Contenuti", label: "Mira Vell", href: "personaggio.html", kind: "Personaggio" },
    { group: "Contenuti", label: "Bram Coda-di-Ferro", href: "personaggio.html", kind: "Personaggio" },
    { group: "Contenuti", label: "Sora Querciavecchia", href: "personaggio.html", kind: "Personaggio" },
    { group: "Contenuti", label: "Bracken", href: "luogo.html", kind: "Luogo" },
    { group: "Contenuti", label: "Passo dell'Alba", href: "luogo.html", kind: "Luogo" },
    { group: "Contenuti", label: "Sessione 24 — La strada per Bracken", href: "sessione.html", kind: "Sessione" },
    { group: "Contenuti", label: "Il patto delle quattro querce", href: "storia.html", kind: "Storia" },
    { group: "Contenuti", label: "Il mondo di gioco", href: "pagina.html", kind: "Pagina" },
    { group: "Azioni", label: "Nuovo personaggio", href: "nuovo-personaggio.html", kind: "Crea", master: true },
    { group: "Azioni", label: "Nuovo luogo", href: "nuovo-luogo.html", kind: "Crea", master: true },
    { group: "Azioni", label: "Nuova sessione", href: "nuova-sessione.html", kind: "Crea", master: true },
    { group: "Azioni", label: "Nuova storia", href: "nuova-storia.html", kind: "Crea", master: true },
    { group: "Azioni", label: "Nuova pagina", href: "nuova-pagina.html", kind: "Crea", master: true }
  ];

  var isMaster = !worldId || WORLDS[worldId].role === "master";

  /* ---------- helper ---------------------------------------------------- */

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function h(html) {
    var t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  /* ---------- sidebar --------------------------------------------------- */

  function sidebarHTML() {
    var brand =
      '<div class="brand">' +
        '<button class="brand-mark" data-goto="mondi.html" aria-label="Torna ai mondi">RG</button>' +
        '<div class="brand-copy hide-collapsed"><strong>ROOT GDR</strong><span>archivio campagne</span></div>' +
      '</div>';

    if (!worldId) {
      return brand +
        '<nav class="nav" aria-label="Navigazione">' +
          '<div class="nav-label hide-collapsed">Archivio</div>' +
          '<a href="mondi.html" class="active"><span class="ic">▦</span><span class="hide-collapsed">I tuoi mondi</span></a>' +
        '</nav>' +
        sidebarFoot("Oscar Píndaro", "Membro");
    }

    var w = WORLDS[worldId];
    var nav = NAV.map(function (n) {
      var cls = n.key === activeNav ? " active" : "";
      var count = n.count ? '<span class="count hide-collapsed">' + n.count + "</span>" : "";
      return '<a href="' + n.href + '" class="' + cls.trim() + '" title="' + esc(n.label) + '">' +
        '<span class="ic">' + n.icon + "</span>" +
        '<span class="hide-collapsed">' + esc(n.label) + "</span>" + count +
      "</a>";
    }).join("");

    return brand +
      '<a class="world-chip" href="mondo.html" title="' + esc(w.name) + '">' +
        '<span class="cover">' + w.cover + "</span>" +
        '<span class="meta hide-collapsed"><strong>' + esc(w.name) + "</strong><span>" +
          (w.role === "master" ? "Master" : "Giocatore") + "</span></span>" +
      "</a>" +
      '<nav class="nav" aria-label="Navigazione del mondo">' +
        '<a href="mondi.html" title="Tutti i mondi"><span class="ic">↩</span><span class="hide-collapsed">Tutti i mondi</span></a>' +
        '<div class="sep"></div>' +
        nav +
        '<div class="sep"></div>' +
        '<div class="nav-label hide-collapsed">Pagine</div>' +
        PAGES.slice().sort(function (a, b) { return a.pos - b.pos; }).map(function (p) {
          return '<a href="' + p.href + '" title="' + esc(p.title) + '">' +
            '<span class="ic">☷</span><span class="hide-collapsed">' + esc(p.title) + "</span></a>";
        }).join("") +
      "</nav>" +
      sidebarFoot("Oscar Píndaro", w.role === "master" ? "Master" : "Giocatore");
  }

  function sidebarFoot(name, role) {
    return '<div class="sidebar-foot">' +
      '<button class="ghost-btn" data-palette><span>⌕</span><span class="hide-collapsed">Cerca</span><kbd class="hide-collapsed">Alt+Spazio</kbd></button>' +
      '<div class="user-row">' +
        '<span class="avatar">OP</span>' +
        '<span class="who hide-collapsed"><strong>' + esc(name) + "</strong><span>" + esc(role) + "</span></span>" +
      "</div>" +
    "</div>";
  }

  /* ---------- topbar ---------------------------------------------------- */

  function topbarHTML() {
    var crumbs = body.dataset.crumbs || "";
    var crumbsHTML = crumbs
      ? crumbs.split("|").map(function (part, i, arr) {
          var isLast = i === arr.length - 1;
          return isLast
            ? '<span class="now">' + esc(part) + "</span>"
            : '<a href="' + esc(part.split("::")[1] || "#") + '">' + esc(part.split("::")[0]) + "</a><span>/</span>";
        }).join("")
      : '<span class="now">' + esc(body.dataset.title || "Root GDR") + "</span>";

    return '<button class="icon-btn" id="drawer-toggle" aria-label="Apri menu">☰</button>' +
      '<button class="icon-btn" id="collapse-toggle" aria-label="Comprimi menu">⇤</button>' +
      '<div class="crumbs">' + crumbsHTML + "</div>" +
      '<div class="spacer"></div>' +
      '<button class="search-trigger" data-palette><span>⌕</span> Cerca <kbd>Alt+Spazio</kbd></button>' +
      '<span class="avatar" title="Oscar Píndaro">OP</span>';
  }

  /* ---------- mount ----------------------------------------------------- */

  var sidebar = document.getElementById("sidebar");
  var topbar = document.getElementById("topbar");
  if (sidebar) sidebar.innerHTML = sidebarHTML();
  if (topbar) topbar.innerHTML = topbarHTML();

  /* la command palette è identica in ogni pagina: la crea la shell */
  if (!document.getElementById("palette")) {
    body.appendChild(h(
      '<div class="palette" id="palette">' +
        '<div class="palette-box">' +
          '<input type="text" placeholder="Cerca mondi, contenuti, azioni…" aria-label="Cerca">' +
          '<div class="palette-results"></div>' +
        "</div>" +
      "</div>"
    ));
  }

  /* ---------- collapse (desktop) ---------------------------------------- */

  var COLLAPSE_KEY = "glmproto.collapsed";
  if (localStorage.getItem(COLLAPSE_KEY) === "1") body.classList.add("collapsed");

  document.addEventListener("click", function (e) {
    var collapse = e.target.closest("#collapse-toggle");
    if (collapse) {
      body.classList.toggle("collapsed");
      localStorage.setItem(COLLAPSE_KEY, body.classList.contains("collapsed") ? "1" : "0");
      return;
    }
    var drawer = e.target.closest("#drawer-toggle");
    if (drawer) {
      body.classList.toggle("drawer-open");
      scrim.classList.toggle("show", body.classList.contains("drawer-open"));
      return;
    }
    var goto = e.target.closest("[data-goto]");
    if (goto) { location.href = goto.dataset.goto; return; }
    var pal = e.target.closest("[data-palette]");
    if (pal) { openPalette(); return; }
    if (e.target.closest("#scrim")) closeDrawer();
  });

  /* ---------- scrim ----------------------------------------------------- */

  var scrim = document.getElementById("scrim");
  function closeDrawer() {
    body.classList.remove("drawer-open");
    if (scrim) scrim.classList.remove("show");
  }

  /* ---------- command palette ------------------------------------------- */

  var palette = document.getElementById("palette");
  var paletteInput, paletteResults, paletteItems = [], paletteCursor = 0;

  function openPalette() {
    if (!palette) return;
    palette.classList.add("show");
    paletteInput.value = "";
    renderPalette("");
    paletteInput.focus();
  }
  function closePalette() {
    if (!palette) return;
    palette.classList.remove("show");
  }

  function renderPalette(query) {
    var q = query.trim().toLowerCase();
    var rows = INDEX.filter(function (it) {
      if (it.master && !isMaster) return false;
      return !q || it.label.toLowerCase().indexOf(q) !== -1 || it.kind.toLowerCase().indexOf(q) !== -1;
    });

    paletteItems = rows;
    paletteCursor = 0;

    if (!rows.length) {
      paletteResults.innerHTML = '<div class="palette-empty">Nessun risultato per “' + esc(query) + "”.</div>";
      return;
    }

    var html = "";
    var lastGroup = null;
    rows.forEach(function (it, i) {
      if (it.group !== lastGroup) {
        html += '<div class="palette-group">' + esc(it.group) + "</div>";
        lastGroup = it.group;
      }
      html += '<div class="palette-item' + (i === 0 ? " active" : "") + '" data-i="' + i + '">' +
        "<span>" + esc(it.label) + '</span><span class="kind">' + esc(it.kind) + "</span></div>";
    });
    paletteResults.innerHTML = html;
  }

  function moveCursor(delta) {
    if (!paletteItems.length) return;
    paletteCursor = (paletteCursor + delta + paletteItems.length) % paletteItems.length;
    Array.prototype.forEach.call(paletteResults.querySelectorAll(".palette-item"), function (el, i) {
      el.classList.toggle("active", i === paletteCursor);
    });
    var active = paletteResults.querySelector(".palette-item.active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  if (palette) {
    paletteInput = palette.querySelector("input");
    paletteResults = palette.querySelector(".palette-results");

    paletteInput.addEventListener("input", function () { renderPalette(paletteInput.value); });
    paletteInput.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveCursor(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveCursor(-1); }
      else if (e.key === "Enter") {
        e.preventDefault();
        var it = paletteItems[paletteCursor];
        if (it) location.href = it.href;
      } else if (e.key === "Escape") { closePalette(); }
    });
    palette.addEventListener("click", function (e) {
      if (e.target === palette) { closePalette(); return; }
      var item = e.target.closest(".palette-item");
      if (item) location.href = paletteItems[+item.dataset.i].href;
    });
  }

  /* ---------- scorciatoie ----------------------------------------------- */

  document.addEventListener("keydown", function (e) {
    if (e.altKey && e.code === "Space") {
      e.preventDefault();
      palette && palette.classList.contains("show") ? closePalette() : openPalette();
    } else if (e.key === "Escape") {
      closePalette();
      closeDrawer();
    }
  });

  /* ---------- editing markdown in place (pagina dettaglio) -------------- */

  document.addEventListener("click", function (e) {
    var edit = e.target.closest("[data-edit]");
    if (edit) {
      var target = document.querySelector(edit.dataset.edit);
      if (!target) return;
      var src = target.querySelector("[data-src]");
      var view = target.querySelector("[data-view]");
      src.hidden = false;
      view.hidden = true;
      edit.hidden = true;
      var cancel = document.querySelector("[data-cancel-edit]");
      if (cancel) cancel.hidden = false;
      src.querySelector("textarea").focus();
      return;
    }
    var cancel = e.target.closest("[data-cancel-edit]");
    if (cancel) {
      var box = cancel.closest("[data-editable]");
      box.querySelector("[data-src]").hidden = true;
      box.querySelector("[data-view]").hidden = false;
      cancel.hidden = true;
      document.querySelector("[data-edit]").hidden = false;
      return;
    }
  });

  /* ---------- nota prototipo -------------------------------------------- */

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-goto]").forEach(function (el) {});
  });
})();
