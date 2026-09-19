/* ============================================================
   entities.js — registro dei contenuti del mondo.
   Serve alle reference nel Markdown: @[Nome] diventa un link con
   il colore del contenuto citato (docs/features/desired_features.md,
   "@ mentions and cross-links").
   Nel prodotto reale questo indice lo costruisce il server a partire
   dai contenuti del mondo; qui è scritto a mano perché il prototipo
   non ha backend.
   Sintassi:
     @[Rugginosa]            nome semplice
     @[luogo:Roccianera]     con tipo, quando il nome è ambiguo
   ============================================================ */
(function () {
  "use strict";

  /* [tipo, nome, tinta, pagina] */
  var LIST = [
    /* personaggi dei giocatori */
    ["personaggio", "Rugginosa", "--p1", "personaggio.html"],
    ["personaggio", "Barone Talpa", "--p8", "personaggio.html"],
    ["personaggio", "Foglia di Ferro", "--p5", "personaggio.html"],
    ["personaggio", "Corvinus", "--p10", "personaggio.html"],
    ["personaggio", "Mastro Tasso", "--p3", "personaggio.html"],
    ["personaggio", "Sibilla", "--p6", "personaggio.html"],

    /* NPC */
    ["npc", "La Marchesa", "--p8", "npc.html"],
    ["npc", "Lord Aquila", "--p2", "npc.html"],
    ["npc", "Il Corriere", "--p3", "npc.html"],
    ["npc", "Vecchio Cinghiale", "--p12", "npc.html"],
    ["npc", "La Sacerdotessa", "--p6", "npc.html"],
    ["npc", "Capitano Riccio", "--p4", "npc.html"],
    ["npc", "Il Vagabondo Grigio", "--p9", "npc.html"],
    ["npc", "Madre Civetta", "--p7", "npc.html"],

    /* radure */
    ["luogo", "Radura della Grande Quercia", "--p1", "luogo.html"],
    ["luogo", "Il Guado Spezzato", "--p8", "luogo.html"],
    ["luogo", "Muschioverde", "--p3", "luogo.html"],
    ["luogo", "Roccianera", "--p9", "luogo.html"],
    ["luogo", "Torre dell'Aquila", "--p2", "luogo.html"],
    ["luogo", "Il Mercato Galleggiante", "--p10", "luogo.html"],
    ["luogo", "Bosco dei Sussurri", "--p5", "luogo.html"],
    ["luogo", "La Palude di Giunco", "--p6", "luogo.html"],
    ["luogo", "Collina del Tasso", "--p12", "luogo.html"],
    ["luogo", "Il Cerchio di Pietre", "--p7", "luogo.html"],
    ["luogo", "Radura del Canto d'Inverno", "--p4", "luogo.html"],
    ["luogo", "Rovine di Forteverde", "--p11", "luogo.html"],

    /* sessioni */
    ["sessione", "Il risveglio della Marchesa", "--p1", "sessione.html"],
    ["sessione", "Il pedaggio del Guado", "--p3", "sessione.html"],
    ["sessione", "Le tre pietre", "--p4", "sessione.html"],
    ["sessione", "La caduta di Torre dell'Aquila", "--p2", "sessione.html"],
    ["sessione", "Il processo di Sibilla", "--p6", "sessione.html"],
    ["sessione", "Il patto del Guado", "--p5", "sessione.html"],
    ["sessione", "Il mercato che non galleggia", "--p7", "sessione.html"],
    ["sessione", "L'inverno dei corvi", "--p8", "sessione.html"],

    /* storie */
    ["storia", "La Marchesa entra nel bosco", "--p1", "storia.html"],
    ["storia", "L'inverno dei corvi (arco)", "--p8", "storia.html"],

    /* pagine statiche */
    ["pagina", "Le regole della Casa", "--p3", "pagina.html"],
    ["pagina", "Le fazioni di Boscochiaro", "--p8", "pagina.html"],
    ["pagina", "Calendario e stagioni", "--p5", "pagina.html"],
    ["pagina", "Storia del Bosco", "--p10", "pagina.html"]
  ];

  var byKey = {};

  LIST.forEach(function (row) {
    var entry = {
      kind: row[0],
      name: row[1],
      color: row[2],
      /* la tinta come nome di token: è quello che finisce nel markup */
      tint: String(row[2]).replace(/^--/, ""),
      href: row[3]
    };
    /* il nome semplice risolve alla prima occorrenza; il tipo disambigua */
    if (!byKey[entry.name]) byKey[entry.name] = entry;
    byKey[entry.kind + ":" + entry.name] = entry;
  });

  function find(key) {
    return byKey[String(key).trim()] || null;
  }

  /* corrispondenza fuzzy: le lettere della query devono comparire in ordine.
     Premia le lettere consecutive e quelle che iniziano una parola, così
     "@lm" trova "La Marchesa" prima di "Muschioverde". */
  function score(query, text) {
    var q = query.toLowerCase();
    var t = text.toLowerCase();
    var qi = 0;
    var total = 0;
    var previous = -2;
    for (var i = 0; i < t.length && qi < q.length; i++) {
      if (t.charAt(i) !== q.charAt(qi)) continue;
      total += (i === previous + 1) ? 3 : 1;
      if (i === 0 || /[\s\-'’]/.test(t.charAt(i - 1))) total += 2;
      previous = i;
      qi++;
    }
    return qi === q.length ? total - t.length * 0.01 : -1;
  }

  /* elenco per il menu dei suggerimenti, senza nomi ripetuti */
  function search(query) {
    var q = String(query || "").trim();
    var seen = {};
    var out = [];
    LIST.forEach(function (row) {
      var entry = byKey[row[1]];
      if (entry !== byKey[row[0] + ":" + row[1]]) return;   /* solo il primo di ogni nome */
      if (seen[entry.name]) return;
      var s = q ? score(q, entry.name) : 0;
      if (s < 0) return;
      seen[entry.name] = true;
      out.push({ entry: entry, score: s });
    });
    out.sort(function (a, b) {
      return b.score - a.score || a.entry.name.localeCompare(b.entry.name);
    });
    return out.slice(0, 8).map(function (r) { return r.entry; });
  }

  window.ENTITIES = { find: find, search: search, score: score, all: LIST };
})();
