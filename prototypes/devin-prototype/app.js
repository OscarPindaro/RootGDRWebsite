/* ============================================================
   app.js — comportamenti di pagina del prototipo.
   Indice attivo negli articoli. Nessuna logica di dominio.
   ============================================================ */
(function () {
  "use strict";

  var toc = document.querySelector("[data-toc]");
  if (toc) {
    var links = Array.prototype.slice.call(toc.querySelectorAll("a[href^='#']"));
    var targets = links
      .map(function (a) { return document.getElementById(a.getAttribute("href").slice(1)); })
      .filter(Boolean);

    if (targets.length && "IntersectionObserver" in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          links.forEach(function (a) {
            a.classList.toggle("is-current", a.getAttribute("href") === "#" + entry.target.id);
          });
        });
      }, { rootMargin: "-20% 0px -70% 0px" });
      targets.forEach(function (t) { observer.observe(t); });
    }
  }

  /* ------------------------------------------------------------
     Editor di un documento (personaggio, luogo, sessione, storia,
     pagina). Lo stesso stato alimenta due impaginazioni (modulo e
     documento) e i campi sono duplicati: qui si tengono allineati.
     Radice:     [data-doc] [data-locked]
     Campi:      [data-field="nome|titolo|sintesi|lunga"]
     Uscite:     [data-out="nome|titolo|sintesi"], [data-md-out]
     Volto:      [data-preview-face], [data-preview-emoji]
     ------------------------------------------------------------ */
  var editor = document.querySelector("[data-doc]");
  if (editor) {
    var fields = document.querySelectorAll("[data-field]");
    var outs = document.querySelectorAll("[data-out]");
    var mdSources = document.querySelectorAll("[data-md-source]");
    var mdOuts = document.querySelectorAll("[data-md-out]");
    var faces = document.querySelectorAll("[data-preview-face]");
    var emojiOuts = document.querySelectorAll("[data-preview-emoji]");
    var emojiButtons = document.querySelectorAll(".emojibtn");
    var swatches = document.querySelectorAll(".swatch");
    var imageInputs = document.querySelectorAll("[data-image-input]");
    var imageNames = document.querySelectorAll("[data-image-name]");
    var imageClears = document.querySelectorAll("[data-image-clear]");

    var emojiButton = document.querySelector("[data-emoji-picker] button[aria-pressed='true']");
    var swatchButton = document.querySelector("[data-color-picker] button[aria-pressed='true']");
    var state = {
      emoji: emojiButton ? emojiButton.getAttribute("data-emoji") : "🐈",
      color: swatchButton ? swatchButton.getAttribute("data-color") : "--p1"
    };
    var photoUrl = null;
    var liveBoxes = [];

    function each(list, fn) { Array.prototype.forEach.call(list, fn); }

    /* scrittura e resa devono avere la stessa altezza: la resa è la misura
       di riferimento, il campo di scrittura prende la sua altezza */
    function syncHeights() {
      liveBoxes.forEach(function (box) { box.sync(); });
    }

    /* come sopra, ma vale anche mentre si scrive: il blocco cresce se serve */
    function settleHeights() {
      liveBoxes.forEach(function (box) { box.settle(); });
    }

    function paintMarkdown() {
      if (!window.MiniMarkdown) return;
      each(mdSources, function (source) {
        var html = window.MiniMarkdown.render(source.value);
        each(mdOuts, function (out) {
          out.innerHTML = html.trim() ||
            '<p class="md-empty">La descrizione resa apparirà qui mentre scrivi.</p>';
        });
      });
      syncHeights();
    }

    function paintText() {
      each(fields, function (field) {
        var name = field.getAttribute("data-field");
        each(outs, function (out) {
          if (out.getAttribute("data-out") !== name) return;
          var value = field.value.trim();
          if (name === "nome") out.textContent = value || "Senza nome";
          else if (name === "titolo") out.textContent = value || "—";
          else out.textContent = value;
        });
      });
    }

    function paintFace() {
      each(faces, function (face) {
        face.style.setProperty("--c", "var(" + state.color + ")");
        face.classList.toggle("face--photo", Boolean(photoUrl));
        face.style.backgroundImage = photoUrl ? "url('" + photoUrl + "')" : "";
      });
      each(emojiOuts, function (out) {
        out.textContent = state.emoji;
        out.setAttribute("aria-label", state.emoji);
      });
      /* il comando per togliere la foto compare solo quando c'è */
      each(imageClears, function (button) { button.hidden = !photoUrl; });
      each(document.querySelectorAll("[data-face-hint]"), function (hint) {
        hint.textContent = photoUrl ? "Cambia immagine" : "Carica un'immagine";
      });
    }

    function paintPickers() {
      each(emojiButtons, function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-emoji") === state.emoji));
      });
      each(swatches, function (s) {
        s.setAttribute("aria-pressed", String(s.getAttribute("data-color") === state.color));
      });
    }

    function syncFrom(target) {
      var name = target.getAttribute("data-field");
      each(fields, function (field) {
        if (field !== target && field.getAttribute("data-field") === name) field.value = target.value;
      });
    }

    editor.addEventListener("input", function (e) {
      var target = e.target;
      if (target.hasAttribute && target.hasAttribute("data-field")) {
        syncFrom(target);
        if (target.hasAttribute("data-md-source")) {
          each(mdSources, function (s) { if (s !== target) s.value = target.value; });
          paintMarkdown();
        }
        paintText();
        if (target.classList.contains("docfield--long")) settleHeights();
      }
    });

    editor.addEventListener("click", function (e) {
      var emoji = e.target.closest(".emojibtn");
      if (emoji) {
        state.emoji = emoji.getAttribute("data-emoji");
        paintPickers();
        paintFace();
        return;
      }
      var swatch = e.target.closest(".swatch");
      if (swatch) {
        state.color = swatch.getAttribute("data-color");
        paintPickers();
        paintFace();
      }
    });

    each(imageInputs, function (input) {
      input.addEventListener("change", function () {
        var file = input.files && input.files[0];
        if (photoUrl) { URL.revokeObjectURL(photoUrl); photoUrl = null; }
        if (file) photoUrl = URL.createObjectURL(file);
        each(imageNames, function (name) {
          name.textContent = file ? file.name : "Nessun file scelto";
        });
        paintFace();
      });
    });
    each(imageClears, function (button) {
      button.addEventListener("click", function (e) {
        /* il comando sta dentro il volto, che è un label: senza questo
           il clic aprirebbe anche il selettore di file */
        e.preventDefault();
        e.stopPropagation();
        each(imageInputs, function (input) { input.value = ""; });
        if (photoUrl) { URL.revokeObjectURL(photoUrl); photoUrl = null; }
        each(imageNames, function (name) { name.textContent = "Nessun file scelto"; });
        paintFace();
      });
    });

    function autoGrow(el) {
      el.style.height = "auto";
      el.style.height = el.scrollHeight + "px";
    }

    /* il campo a documento è nascosto in modalità modulo: quando torna
       visibile va rimisurato, altrimenti resta alto zero */
    document.addEventListener("prefchange", function (e) {
      if (e.detail.id !== "editor") return;
      each(document.querySelectorAll(".docfield--long"), autoGrow);
      syncHeights();
    });

    /* schede Scrivi / Anteprima sulla descrizione lunga (versione a modulo).
       Ctrl/⌘+Invio salta all'anteprima e torna indietro, senza perdere
       il punto in cui si stava scrivendo. */
    each(document.querySelectorAll("[data-md-tabs]"), function (group) {
      var source = group.querySelector("[data-md-source]");
      var out = group.querySelector("[data-md-out]");
      var tabs = group.querySelectorAll("[data-md-tab]");
      var caret = null;

      function select(name) {
        each(tabs, function (t) {
          t.setAttribute("aria-selected", String(t.getAttribute("data-md-tab") === name));
        });
        var preview = name === "anteprima";
        if (source) source.hidden = preview;
        if (out) out.hidden = !preview;
      }

      function backToWrite() {
        select("scrivi");
        if (source) {
          source.focus();
          if (caret != null) source.setSelectionRange(caret, caret);
        }
      }

      each(tabs, function (tab) {
        tab.addEventListener("click", function () {
          var name = tab.getAttribute("data-md-tab");
          if (name === "anteprima" && source) caret = source.selectionStart;
          select(name);
          if (name === "scrivi") backToWrite();
        });
      });

      if (source) {
        source.addEventListener("keydown", function (e) {
          if (!(e.ctrlKey || e.metaKey) || e.key !== "Enter") return;
          e.preventDefault();
          caret = source.selectionStart;
          select("anteprima");
          var previewTab = group.querySelector('[data-md-tab="anteprima"]');
          if (previewTab) previewTab.focus();
        });
      }
      each(tabs, function (tab) {
        tab.addEventListener("keydown", function (e) {
          if (!(e.ctrlKey || e.metaKey) || e.key !== "Enter") return;
          e.preventDefault();
          backToWrite();
        });
      });
      if (out) {
        out.addEventListener("keydown", function (e) {
          if (!(e.ctrlKey || e.metaKey) || e.key !== "Enter") return;
          e.preventDefault();
          backToWrite();
        });
      }
    });

    /* nel documento la descrizione si mostra resa e si apre in scrittura
       con un doppio clic; il render resta aggiornato a ogni tasto.
       Ctrl/⌘+Invio è un interruttore: esce dalla scrittura e mostra il
       risultato, e premuto di nuovo rientra dal punto in cui si era.
       Se il documento è bloccato non si entra in modifica. */
    each(document.querySelectorAll("[data-md-live]"), function (box) {
      var input = box.querySelector("[data-md-source]");
      var view = box.querySelector("[data-md-out]");
      if (!input || !view) return;

      var caret = input.value.length;
      /* altezza del blocco: mai meno della resa, mai meno della sorgente.
         Cresce quando serve e non torna più indietro, così passare da
         scrittura a resa non fa saltare la pagina. */
      var blockHeight = 0;
      var caretSpot = null;

      /* riga attiva e cursore: la textarea non sa colorare né una riga né
         il cursore, quindi li disegniamo dietro e davanti al testo,
         misurando il punto del cursore su un clone invisibile con la
         stessa metrica. */
      var caretLine = document.createElement("div");
      caretLine.className = "docedit__caretline";
      var caretBar = document.createElement("div");
      caretBar.className = "docedit__caret";
      var mirror = document.createElement("div");
      mirror.className = "docedit__mirror";
      box.insertBefore(caretLine, box.firstChild);
      box.insertBefore(caretBar, box.firstChild);
      box.appendChild(mirror);

      function paintCaretLine() {
        if (input.hidden) { caretBar.style.height = "0px"; return; }
        var style = getComputedStyle(input);
        var padTop = parseFloat(style.paddingTop) || 0;
        var padLeft = parseFloat(style.paddingLeft) || 0;
        var padRight = parseFloat(style.paddingRight) || 0;
        var lineHeight = parseFloat(style.lineHeight);
        if (!lineHeight || isNaN(lineHeight)) lineHeight = (parseFloat(style.fontSize) || 18) * 1.68;
        var width = input.clientWidth - padLeft - padRight;
        if (width <= 0) return;

        var textLeft = input.offsetLeft + input.clientLeft + padLeft;
        var at = input.selectionStart || 0;
        mirror.style.left = textLeft + "px";
        mirror.style.width = width + "px";
        mirror.textContent = input.value.slice(0, at);
        var marker = document.createElement("span");
        marker.textContent = "\u200b";
        mirror.appendChild(marker);

        var top = input.offsetTop + input.clientTop + padTop + marker.offsetTop;
        caretLine.style.left = textLeft + "px";
        caretLine.style.width = width + "px";
        caretLine.style.top = top + "px";
        caretLine.style.height = lineHeight + "px";

        /* il cursore si nasconde quando c'è una selezione: quella si vede già */
        var empty = input.selectionStart === input.selectionEnd;
        var focused = document.activeElement === input;
        caretBar.style.left = (textLeft + marker.offsetLeft) + "px";
        caretBar.style.top = top + "px";
        caretBar.style.height = (empty && focused) ? lineHeight + "px" : "0px";

        /* il menu dei suggerimenti si appoggia sotto il cursore */
        caretSpot = { x: textLeft + marker.offsetLeft, y: top + lineHeight };
      }

      /* ---------- menu dei suggerimenti per @ ---------- */
      var menu = document.createElement("div");
      menu.className = "mention-menu";
      menu.hidden = true;
      menu.setAttribute("role", "listbox");
      box.appendChild(menu);
      var options = [];
      var active = 0;
      var queryStart = 0;

      function escHtml(s) {
        return String(s).replace(/[&<>"]/g, function (c) {
          return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
        });
      }

      /* evidenzia le lettere che hanno fatto match, anche non consecutive */
      function highlight(name, query) {
        if (!query) return escHtml(name);
        var q = query.toLowerCase();
        var t = name.toLowerCase();
        var qi = 0;
        var out = "";
        for (var i = 0; i < name.length; i++) {
          if (qi < q.length && t.charAt(i) === q.charAt(qi)) {
            out += "<mark>" + escHtml(name.charAt(i)) + "</mark>";
            qi++;
          } else {
            out += escHtml(name.charAt(i));
          }
        }
        return out;
      }

      /* @ seguito da lettere, senza spazi: è la query in corso */
      function queryBeforeCaret() {
        var at = input.selectionStart;
        var match = /@([\w'’\-À-ÿ]*)$/.exec(input.value.slice(0, at));
        return match ? { query: match[1], start: at - match[0].length } : null;
      }

      function closeMenu() {
        menu.hidden = true;
        options = [];
      }

      function placeMenu() {
        if (!caretSpot) return;
        var maxLeft = Math.max(0, box.clientWidth - menu.offsetWidth - 4);
        menu.style.left = Math.max(0, Math.min(caretSpot.x, maxLeft)) + "px";
        menu.style.top = (caretSpot.y + 4) + "px";
      }

      function paintMenu() {
        var found = queryBeforeCaret();
        if (!found || locked() || !window.ENTITIES) { closeMenu(); return; }
        options = window.ENTITIES.search(found.query);
        queryStart = found.start;
        active = 0;
        menu.innerHTML = "";
        if (!options.length) {
          var none = document.createElement("div");
          none.className = "mention-menu__empty";
          none.textContent = "Nessun contenuto con questo nome";
          menu.appendChild(none);
        } else {
          options.forEach(function (entry, index) {
            var item = document.createElement("button");
            item.type = "button";
            item.className = "mention-menu__item";
            item.setAttribute("aria-selected", String(index === 0));
            item.style.setProperty("--c", "var(" + entry.color + ")");
            item.innerHTML =
              '<span class="mention-menu__dot"></span>' +
              '<span class="mention-menu__name">' + highlight(entry.name, found.query) + "</span>" +
              '<span class="mention-menu__kind">' + escHtml(entry.kind) + "</span>";
            item.addEventListener("mousedown", function (e) {
              e.preventDefault();
              acceptMention(index);
            });
            menu.appendChild(item);
          });
        }
        menu.hidden = false;
        placeMenu();
      }

      function moveMenu(step) {
        if (menu.hidden || !options.length) return;
        active = (active + step + options.length) % options.length;
        Array.prototype.forEach.call(menu.children, function (node, index) {
          node.setAttribute("aria-selected", String(index === active));
        });
      }

      function acceptMention(index) {
        var entry = options[index];
        if (!entry) return;
        var at = input.selectionStart;
        var before = input.value.slice(0, queryStart);
        var inserted = "@[" + entry.name + "] ";
        input.value = before + inserted + input.value.slice(at);
        caret = before.length + inserted.length;
        input.setSelectionRange(caret, caret);
        closeMenu();
        /* il valore è cambiato: aggiorna le altre copie e la resa */
        input.dispatchEvent(new Event("input", { bubbles: true }));
        paintCaretLine();
      }

      input.addEventListener("input", paintMenu);
      input.addEventListener("click", paintMenu);
      input.addEventListener("blur", closeMenu);
      input.addEventListener("keydown", function (e) {
        if (menu.hidden || e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.key === "ArrowDown") { e.preventDefault(); moveMenu(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); moveMenu(-1); }
        else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); acceptMention(active); }
        else if (e.key === "Escape") { e.preventDefault(); closeMenu(); }
      });

      function locked() {
        var doc = box.closest("[data-doc]");
        return doc ? doc.getAttribute("data-locked") === "true" : false;
      }
      function settle() {
        var natural = 0;
        if (!input.hidden) {
          input.style.height = "auto";
          natural = input.scrollHeight;
        }
        var h = Math.max(view.offsetHeight, natural, blockHeight);
        blockHeight = h;
        if (h > 0) {
          box.style.minHeight = h + "px";
          if (!input.hidden) input.style.height = h + "px";
        }
        paintCaretLine();
      }
      function sync() { if (!view.hidden) settle(); }
      function showInput() {
        if (locked()) return;
        view.hidden = true;
        input.hidden = false;
        /* stessa altezza della resa: entrare in scrittura non sposta la
           pagina, e un doppio clic non finisce fuori posto */
        if (blockHeight > 0) input.style.height = blockHeight + "px";
        input.focus();
        input.setSelectionRange(caret, caret);
        paintCaretLine();
      }
      function showView() {
        if (input.selectionStart != null) caret = input.selectionStart;
        closeMenu();
        input.hidden = true;
        view.hidden = false;
        sync();
      }
      function toggle() {
        if (input.hidden) { showInput(); return; }
        input.blur();
        view.focus();
      }

      /* il doppio clic entra in scrittura; su una reference no, lì il clic
         segue il link (altrimenti il primo clic navigherebbe comunque).
         La parola selezionata serve a rimettere il cursore dove si è
         cliccato: la resa e la sorgente non hanno le stesse posizioni. */
      view.addEventListener("dblclick", function (e) {
        if (e.target.closest("a")) return;
        var word = String(window.getSelection ? window.getSelection() : "").trim();
        var rect = view.getBoundingClientRect();
        var ratio = rect.height > 0
          ? Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height))
          : 0;
        showInput();
        if (!word) return;
        var guess = Math.floor(input.value.length * ratio);
        var at = input.value.indexOf(word, guess);
        if (at < 0) at = input.value.lastIndexOf(word, guess);
        if (at < 0) at = input.value.indexOf(word);
        if (at < 0) return;
        caret = at;
        input.setSelectionRange(at, at + word.length);
        paintCaretLine();
      });
      input.addEventListener("blur", showView);
      input.addEventListener("keydown", function (e) {
        if (!(e.ctrlKey || e.metaKey) || e.key !== "Enter") return;
        e.preventDefault();
        toggle();
      });
      view.addEventListener("keydown", function (e) {
        if (!(e.ctrlKey || e.metaKey) || e.key !== "Enter") return;
        e.preventDefault();
        toggle();
      });
      view.hidden = false;
      input.hidden = true;

      /* la riga attiva segue il cursore, comunque lo si muova */
      ["keyup", "click", "select", "focus"].forEach(function (type) {
        input.addEventListener(type, paintCaretLine);
      });
      document.addEventListener("selectionchange", function () {
        if (document.activeElement === input) paintCaretLine();
      });

      liveBoxes.push({ sync: sync, settle: settle, showInput: showInput, showView: showView, input: input });
    });

    /* blocco del documento: da sbloccato si entra in modifica, da bloccato no */
    each(document.querySelectorAll("[data-doc-lock]"), function (button) {
      var doc = button.closest("[data-doc]");
      if (!doc) return;
      function paint() {
        var locked = doc.getAttribute("data-locked") === "true";
        button.textContent = locked ? "Bloccato" : "Sbloccato";
        button.setAttribute("aria-pressed", String(locked));
        doc.classList.toggle("is-locked", locked);
      }
      button.addEventListener("click", function () {
        var locked = doc.getAttribute("data-locked") === "true";
        doc.setAttribute("data-locked", String(!locked));
        if (locked) paint();
        else each(liveBoxes, function (b) { b.showView(); });
        paint();
      });
      paint();
    });

    /* il comando "modifica" del masthead apre la scrittura */
    each(document.querySelectorAll("[data-doc-edit]"), function (button) {
      button.addEventListener("click", function () {
        if (liveBoxes[0]) liveBoxes[0].showInput();
      });
    });

    /* stato di pubblicazione: una bozza non compare fra i contenuti ufficiali */
    each(document.querySelectorAll("[data-doc-publish]"), function (button) {
      var doc = button.closest("[data-doc]");
      if (!doc) return;
      function paint() {
        var published = doc.getAttribute("data-published") === "true";
        button.textContent = published ? "Riporta a bozza" : "Pubblica";
        each(doc.querySelectorAll("[data-publish-state]"), function (pill) {
          pill.textContent = published ? "Pubblicato" : "Bozza";
          pill.className = published ? "pill pill--plain" : "pill pill--draft";
        });
        doc.classList.toggle("is-draft", !published);
      }
      button.addEventListener("click", function () {
        var published = doc.getAttribute("data-published") === "true";
        doc.setAttribute("data-published", String(!published));
        paint();
      });
      paint();
    });

    /* forma di una radura: cambia il segno del volto */
    each(document.querySelectorAll("[data-shape-pick]"), function (button) {
      button.addEventListener("click", function () {
        var shape = button.getAttribute("data-shape-pick");
        each(document.querySelectorAll("[data-shape-pick]"), function (b) {
          b.setAttribute("aria-pressed", String(b === button));
        });
        each(document.querySelectorAll("[data-preview-shape]"), function (el) {
          el.setAttribute("data-shape", shape);
        });
        window.MARKS.applyAll();
      });
    });

    window.addEventListener("resize", syncHeights);

    /* le misure cambiano quando i font sono caricati: riallineo */
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(syncHeights);

    each(document.querySelectorAll(".docfield--long"), autoGrow);
    paintPickers();
    paintFace();
    paintText();
    paintMarkdown();
  }

  /* filtro dell'elenco unico: tutti, personaggi, NPC */
  var filterbar = document.querySelector("[data-filterbar]");
  if (filterbar) {
    var kindItems = document.querySelectorAll("[data-kind]");
    var kindSections = document.querySelectorAll("[data-kind-section]");

    filterbar.addEventListener("click", function (e) {
      var btn = e.target.closest(".filterbar__btn");
      if (!btn) return;
      var want = btn.getAttribute("data-filter");
      Array.prototype.forEach.call(filterbar.querySelectorAll(".filterbar__btn"), function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      Array.prototype.forEach.call(kindItems, function (item) {
        item.style.display = (want === "tutti" || item.getAttribute("data-kind") === want) ? "" : "none";
      });
      Array.prototype.forEach.call(kindSections, function (section) {
        var kind = section.getAttribute("data-kind-section");
        section.style.display = (want === "tutti" || kind === want) ? "" : "none";
      });
    });
  }
})();
