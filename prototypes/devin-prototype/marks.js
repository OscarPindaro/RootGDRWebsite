/* ============================================================
   marks.js — preferenze visive del prototipo.
   Due famiglie intercambiabili per gli stessi ruoli:
   - icone: disegno lineare, per leggere la funzione;
   - forme: geometria piena, per leggere la struttura.
   E due trattamenti per la riga d'accento:
   - pieno: una tinta sola;
   - gradiente: tre tinte in sequenza, che si invertono all'hover.
   E due modelli di informazione per personaggi e NPC:
   - unite: una sola voce di navigazione, sezioni e filtro;
   - separate: due voci di navigazione, due elenchi (default:
     è il modello deciso per la master view).
   Le preferenze vivono in localStorage e si applicano tramite
   [data-mark] (togglabile) e [data-shape] (fissa).

   NOTA PER L'IMPLEMENTAZIONE: lo storage in localStorage è un
   espediente del prototipo. In src/ le preferenze appartengono
   all'utente, sono salvate sul record utente e si modificano in
   una pagina impostazioni. Vedi docs/features/frontend.md.
   ============================================================ */
(function () {
  "use strict";

  var ICONS = {
    globo:
      '<circle cx="12" cy="12" r="9"/>' +
      '<ellipse cx="12" cy="12" rx="4" ry="9"/>' +
      '<line x1="3" y1="12" x2="21" y2="12"/>',
    orologio:
      '<circle cx="12" cy="12" r="9"/>' +
      '<polyline points="12,6.5 12,12 16,14.5"/>',
    persona:
      '<circle cx="12" cy="8" r="3.6"/>' +
      '<path d="M4.8 20.4a7.2 7.2 0 0 1 14.4 0"/>',
    bussola:
      '<circle cx="12" cy="12" r="9"/>' +
      '<polygon points="12,6 14.6,15 12,13.4 9.4,15"/>',
    pin:
      '<path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z"/>' +
      '<circle cx="12" cy="10" r="2.6"/>',
    calendario:
      '<rect x="3" y="5.5" width="18" height="15.5"/>' +
      '<line x1="3" y1="10.5" x2="21" y2="10.5"/>' +
      '<line x1="8" y1="3" x2="8" y2="7.5"/>' +
      '<line x1="16" y1="3" x2="16" y2="7.5"/>',
    libro:
      '<path d="M4 5.6A2.6 2.6 0 0 1 6.6 3H19.5v15.5H6.6A2.6 2.6 0 0 0 4 21z"/>' +
      '<line x1="8.5" y1="7.8" x2="15.5" y2="7.8"/>' +
      '<line x1="8.5" y1="11.4" x2="15.5" y2="11.4"/>',
    documento:
      '<path d="M6 3h8l4.5 4.5V21H6z"/>' +
      '<polyline points="14,3 14,7.5 18.5,7.5"/>' +
      '<line x1="9" y1="12.5" x2="15" y2="12.5"/>' +
      '<line x1="9" y1="16" x2="15" y2="16"/>',
    utenti:
      '<circle cx="9" cy="8.6" r="3.2"/>' +
      '<path d="M3.2 19.8a5.8 5.8 0 0 1 11.6 0"/>' +
      '<path d="M16.4 6.4a3 3 0 0 1 0 5.4"/>' +
      '<path d="M18 19.8a5.6 5.6 0 0 0-2.5-4.6"/>'
  };

  var SHAPES = {
    cerchio: '<circle cx="12" cy="12" r="9.5"/>',
    quadrato: '<rect x="2.5" y="2.5" width="19" height="19"/>',
    triangolo: '<polygon points="12,2.5 22,21.5 2,21.5"/>',
    rombo: '<polygon points="12,2 22,12 12,22 2,12"/>',
    esagono: '<polygon points="12,2 21.5,7.5 21.5,16.5 12,22 2.5,16.5 2.5,7.5"/>',
    pentagono: '<polygon points="12,2 22,9.6 18.2,21 5.8,21 2,9.6"/>',
    stella:
      '<polygon points="12,2 14.65,8.36 21.51,8.91 16.28,13.39 17.88,20.09 ' +
      '12,16.5 6.12,20.09 7.72,13.39 2.49,8.91 9.35,8.36"/>',
    croce: '<path d="M9 2h6v7h7v6h-7v7H9v-7H2V9h7z"/>',
    ottagono:
      '<polygon points="20.78,15.64 15.64,20.78 8.36,20.78 3.22,15.64 ' +
      '3.22,8.36 8.36,3.22 15.64,3.22 20.78,8.36"/>',
    semicerchio: '<path d="M2 15.5a10 10 0 0 1 20 0z"/>',
    goccia: '<path d="M12 2c0 0 7 8.2 7 13a7 7 0 0 1-14 0c0-4.8 7-13 7-13z"/>',
    anello:
      '<path fill-rule="evenodd" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 5.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z"/>'
  };

  /* ogni ruolo ha un'icona e una forma equivalenti */
  var BY_ROLE = {
    mondi: { icon: "globo", shape: "cerchio" },
    attivita: { icon: "orologio", shape: "rombo" },
    profilo: { icon: "persona", shape: "quadrato" },
    mondo: { icon: "bussola", shape: "cerchio" },
    personaggi: { icon: "persona", shape: "quadrato" },
    personaggio: { icon: "persona", shape: "quadrato" },
    npc: { icon: "utenti", shape: "ottagono" },
    luoghi: { icon: "pin", shape: "triangolo" },
    luogo: { icon: "pin", shape: "triangolo" },
    sessioni: { icon: "calendario", shape: "rombo" },
    sessione: { icon: "calendario", shape: "rombo" },
    storie: { icon: "libro", shape: "esagono" },
    storia: { icon: "libro", shape: "esagono" },
    pagine: { icon: "documento", shape: "pentagono" },
    pagina: { icon: "documento", shape: "anello" }
  };

  function iconSvg(name) {
    return '<svg class="mark__svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      (ICONS[name] || ICONS.persona) + "</svg>";
  }

  function shapeSvg(name) {
    return '<svg class="mark__svg mark__svg--shape" viewBox="0 0 24 24" fill="currentColor" ' +
      'aria-hidden="true">' + (SHAPES[name] || SHAPES.cerchio) + "</svg>";
  }

  function roleOf(key) { return BY_ROLE[key] || BY_ROLE.pagina; }

  /* ogni tipo di contenuto ha la sua icona, usata accanto alle reference */
  var KIND_ICON = {
    personaggio: "persona",
    npc: "utenti",
    luogo: "pin",
    sessione: "calendario",
    storia: "libro",
    pagina: "documento"
  };

  function icon(kind) {
    return iconSvg(KIND_ICON[kind] || "documento");
  }

  function mode() {
    return document.documentElement.dataset.marks === "forme" ? "forme" : "icone";
  }

  function render(roleKey, which) {
    var role = roleOf(roleKey);
    return (which || mode()) === "forme" ? shapeSvg(role.shape) : iconSvg(role.icon);
  }

  function applyAll() {
    var which = mode();
    Array.prototype.forEach.call(document.querySelectorAll("[data-mark]"), function (el) {
      el.innerHTML = render(el.getAttribute("data-mark"), which);
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-shape]"), function (el) {
      el.innerHTML = shapeSvg(el.getAttribute("data-shape"));
    });
  }

  /* ============================================================
     PREFERENZE — SOLO PROTOTIPO, NON REPLICARE IN src/
     In produzione queste preferenze NON vivono nel browser:
     - appartengono all'utente e sono salvate sul record utente,
       non per mondo e non per browser;
     - devono essere note al primo render server, quindi arrivano
       dal contesto utente/sessione, non da una chiamata successiva
       dopo il caricamento della pagina;
     - si modificano in una pagina impostazioni utente.
     Qui stanno in localStorage perché il prototipo non ha backend:
     è un espediente per provare le varianti, non una scelta di
     architettura. Vedi docs/features/frontend.md.
     ============================================================ */

  /* stile dei simboli: icone (default) o forme */
  function setMode(next) {
    document.documentElement.dataset.marks = next === "forme" ? "forme" : "icone";
    try { localStorage.setItem("boscochiaro.marks", document.documentElement.dataset.marks); } catch (e) {}
    applyAll();
  }

  var saved = null;
  try { saved = localStorage.getItem("boscochiaro.marks"); } catch (e) {}
  document.documentElement.dataset.marks = saved === "forme" ? "forme" : "icone";

  /* trattamento della riga d'accento: tinta piena (default) o tre tinte */
  function accent() {
    return document.documentElement.dataset.accent === "gradiente" ? "gradiente" : "pieno";
  }

  function setAccent(next) {
    document.documentElement.dataset.accent = next === "gradiente" ? "gradiente" : "pieno";
    try { localStorage.setItem("boscochiaro.accent", document.documentElement.dataset.accent); } catch (e) {}
  }

  var savedAccent = null;
  try { savedAccent = localStorage.getItem("boscochiaro.accent"); } catch (e) {}
  document.documentElement.dataset.accent = savedAccent === "gradiente" ? "gradiente" : "pieno";

  /* personaggi e NPC: elenco unico oppure due viste separate.
     Questa è una decisione di informazione, non di stile: se resta
     in localStorage nel prodotto finale significa che due utenti
     dello stesso mondo vedono strutture di navigazione diverse.
     Va quindi decisa una volta e applicata a tutto il mondo, oppure
     esposta come preferenza utente nella pagina impostazioni.
     DECISO: nella master view personaggi e NPC sono separati, quindi
     "separate" è il default. Lo switch resta solo per confrontare le
     due architetture. Vedi docs/features/frontend.md. */
  function views() {
    return document.documentElement.dataset.views === "unite" ? "unite" : "separate";
  }

  function setViews(next) {
    document.documentElement.dataset.views = next === "unite" ? "unite" : "separate";
    try { localStorage.setItem("boscochiaro.views", document.documentElement.dataset.views); } catch (e) {}
  }

  var savedViews = null;
  try { savedViews = localStorage.getItem("boscochiaro.views"); } catch (e) {}
  document.documentElement.dataset.views = savedViews === "unite" ? "unite" : "separate";

  /* impaginazione dell'editor: documento oppure campi etichettati.
     Il documento è il default: si scrive sulla pagina e si legge già reso.
     La variante a modulo resta per confronto. */
  function editor() {
    return document.documentElement.dataset.editor === "modulo" ? "modulo" : "documento";
  }

  function setEditor(next) {
    document.documentElement.dataset.editor = next === "modulo" ? "modulo" : "documento";
    try { localStorage.setItem("boscochiaro.editor", document.documentElement.dataset.editor); } catch (e) {}
  }

  var savedEditor = null;
  try { savedEditor = localStorage.getItem("boscochiaro.editor"); } catch (e) {}
  document.documentElement.dataset.editor = savedEditor === "modulo" ? "modulo" : "documento";

  window.MARKS = {
    applyAll: applyAll,
    setMode: setMode,
    mode: mode,
    accent: accent,
    setAccent: setAccent,
    views: views,
    setViews: setViews,
    editor: editor,
    setEditor: setEditor,
    render: render,
    icon: icon,
    roles: BY_ROLE,
    kinds: KIND_ICON,
    shapes: Object.keys(SHAPES)
  };
})();
