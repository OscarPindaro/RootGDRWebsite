/* ============================================================
   markdown.js — renderer minimo per l'anteprima dal vivo.
   Serve solo al prototipo: in produzione il Markdown lo rende il
   CommonMark renderer lato server, con HTML grezzo disabilitato
   (docs/features/starting_description.md). Questo file non è una
   proposta di implementazione, è un modo per vedere il risultato
   mentre si scrive.

   Supporta: titoli #, liste -, liste 1., citazioni >, righe
   orizzontali, grassetto, corsivo, codice inline e link.
   ============================================================ */
(function () {
  "use strict";

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  /* una reference è pura semantica: tipo, tinta, destinazione.
     Forma, icona e colori li mette il foglio di stile. */
  function mention(key) {
    var entry = window.ENTITIES && window.ENTITIES.find(key);
    if (!entry) {
      return '<span class="mention mention--missing" title="Nessun contenuto con questo nome">@' +
        key + "</span>";
    }
    return '<a class="mention" href="' + entry.href + '" data-kind="' + entry.kind +
      '" data-color="' + entry.tint + '" title="' + entry.kind + '">' + key + "</a>";
  }

  function inline(s) {
    return s
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2">$1</a>')
      .replace(/@\[([^\]]+)\]/g, function (m, key) { return mention(key); })
      .replace(/@([\w'’\-À-ÿ]+)/g, function (m, key) { return mention(key); });
  }

  function render(source) {
    var lines = escapeHtml(source || "").split(/\r?\n/);
    var out = [];
    var para = [];
    var list = null;

    function flushPara() {
      if (!para.length) return;
      out.push("<p>" + inline(para.join(" ")) + "</p>");
      para = [];
    }
    function closeList() {
      if (!list) return;
      out.push("</" + list + ">");
      list = null;
    }
    function openList(kind) {
      if (list === kind) return;
      closeList();
      list = kind;
      out.push("<" + kind + ">");
    }

    lines.forEach(function (line) {
      var text = line.trim();

      if (!text) { flushPara(); closeList(); return; }

      if (/^(-{3,}|\*{3,})$/.test(text)) {
        flushPara(); closeList();
        out.push("<hr>");
        return;
      }

      var heading = /^(#{1,4})\s+(.*)$/.exec(text);
      if (heading) {
        flushPara(); closeList();
        var level = Math.min(heading[1].length, 4);
        out.push("<h" + level + ">" + inline(heading[2]) + "</h" + level + ">");
        return;
      }

      var quote = /^&gt;\s?(.*)$/.exec(text);
      if (quote) {
        flushPara(); closeList();
        out.push("<blockquote>" + inline(quote[1]) + "</blockquote>");
        return;
      }

      var bullet = /^[-*]\s+(.*)$/.exec(text);
      if (bullet) {
        flushPara(); openList("ul");
        out.push("<li>" + inline(bullet[1]) + "</li>");
        return;
      }

      var numbered = /^\d+\.\s+(.*)$/.exec(text);
      if (numbered) {
        flushPara(); openList("ol");
        out.push("<li>" + inline(numbered[1]) + "</li>");
        return;
      }

      para.push(text);
    });

    flushPara();
    closeList();
    return out.join("\n");
  }

  window.MiniMarkdown = { render: render };
})();
