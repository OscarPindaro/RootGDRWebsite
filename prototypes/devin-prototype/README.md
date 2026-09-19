# Boscochiaro — prototipo editoriale (Devin)

Prototipo statico **multipagina** per l'applicazione descritta in
`docs/features/high_level_starting_description.md`. Ogni vista è un file HTML
reale, collegato agli altri da link reali: la navigazione non dipende da
JavaScript e l'URL cambia davvero.

## Avvio

```bash
cd prototypes/devin-prototype
python3 -m http.server 4174
# apri http://127.0.0.1:4174
```

## Concept

L'applicazione è trattata come un **atlante stampato**, non come una dashboard.

- Il **rail** è la costola del volume: scuro, stretto, con simboli al posto dei numeri.
- Il **contenuto** è la tavola: carta chiara, righe sottili, campiture piatte.
- La griglia è **Mondrian funzionale**: le linee dividono informazioni reali
  (masthead, sezioni, righe di registro), non decorano.
- L'elevazione non è un'ombra diffusa ma uno **scostamento secco** con ombra
  piena, usato solo su ciò che si può aprire.

Differenze deliberate rispetto agli altri prototipi del repo:

1. **Niente neobrutalismo diffuso.** Bordi forti e spostamenti sono riservati
   alle superfici cliccabili; la prosa resta calma.
2. **Serif editoriale per display e prosa.** La gerarchia nasce dalla
   tipografia, non dai box.
3. **Contenitore scelto per contenuto.** Copertine, schede, registro, articolo:
   quattro forme diverse, non una card ripetuta.
4. **Colore piatto, mai ombra colorata.** Gli accenti identificano sezioni e
   fazioni; il significato non è mai affidato al solo colore.

## Preferenze visive

In fondo al rail ci sono quattro switch; tutti restano in `localStorage` fra le
pagine. Sul telefono stanno dietro un interruttore «Preferenze», per non
allungare il drawer.

| Switch | Valori | Cosa cambia |
|---|---|---|
| **Simboli** | `Icone` / `Forme` | navigazione e quick card della panoramica |
| **Accenti** | `Pieno` / `Gradiente` | la riga d'accento sotto i titoli e le sottolineature dei link |
| **Viste** | `Unite` / `Separate` | se personaggi e NPC condividono o meno la navigazione |
| **Editor** | `Modulo` / `Documento` | come si compila la scheda di un personaggio |

## Confronto dei motori di scrittura

`editor.html` apre tre pagine che montano lo **stesso documento** (la scheda di
Roccianera) dentro la stessa impaginazione, cambiando solo il motore. Ci si
arriva dal link **Motori di scrittura** in fondo al rail, da qualunque pagina,
oppure dalla command palette.

| Pagina | Motore | Modello |
|---|---|---|
| `editor-codemirror.html` | CodeMirror 6 | la stringa Markdown |
| `editor-milkdown.html` | Milkdown | ProseMirror + Remark |
| `editor-tiptap.html` | TipTap | albero JSON |

In tutte e tre: il menu `@` con ricerca fuzzy, la pillola con l'icona del tipo,
il blocco del documento e il pannello col Markdown che verrebbe salvato. La
pagina di CodeMirror rende anche titoli, liste, citazioni, grassetto, corsivo e
codice come in Obsidian, con la sorgente che riappare sulla riga del cursore.
I motori sono caricati da CDN come moduli ES: serve la rete, ed è un espediente
per provarli senza un passo di build.

### Editor contro server

`render-compare.html` rende lo **stesso Markdown due volte** — dall'editor
(Milkdown) e dal renderer del server — e confronta le due rese parola per parola
e blocco per blocco.

L'HTML di destra non è finto: lo produce `tools/render_server_side.py` con la
stessa configurazione dell'applicazione
(`MarkdownIt("commonmark", {"html": False})`, da `src/backend/jinja.py`) più un
plugin per le reference `@[Nome]`. Si rigenera con:

```bash
uv run python prototypes/devin-prototype/tools/render_server_side.py
```

Il confine che rende possibile l'uguaglianza: il renderer emette **solo
semantica** (`href`, `data-kind`, `data-color` e il nome), l'aspetto — pillola,
icona, tinta — sta tutto in `styles.css`. L'editor emette lo stesso markup,
quindi i due non possono divergere per costruzione.

## Documenti di contenuto

Personaggi, luoghi, sessioni, storie e pagine si scrivono tutti allo stesso
modo: **un documento**, qualunque sia il tipo. Cambiano i campi, non il modo di
scriverli. Niente immagine per sessioni e storie, per ora.

### Due impaginazioni

- **Modulo** — campi etichettati, anteprima a destra. La descrizione lunga ha due
  schede, `Scrivi` e `Anteprima`: sorgente e risultato non stanno mai insieme.
- **Documento** — nessun riquadro: nome, titolo e corpo si scrivono sulla
  pagina. Il volto sta di fianco all'identità a dimensione piena. La descrizione
  si mostra **già resa** e si apre in scrittura con un **doppio clic**; il render
  resta aggiornato a ogni tasto. Il doppio clic **su una reference** non entra in
  scrittura: lì il clic segue il link, perché il primo clic naviga prima che il
  secondo possa essere interpretato. Per quel caso c'è il comando `Modifica`.

Le due condividono lo stesso stato, quindi cambiare non perde niente.

**Scrittura e resa hanno la stessa altezza**: la resa è la misura di riferimento,
il campo di scrittura prende la sua altezza e il blocco non scende mai sotto il
contenuto. Senza questo la pagina salta a ogni cambio di modalità, e il salto fa
sì che il doppio clic finisca su un elemento diverso da quello che si era
cliccato.

`Ctrl/⌘ + Invio` è un **interruttore** fra scrittura e risultato, e al ritorno il
cursore riprende **dal punto in cui era**.

In scrittura si deve capire dove si è: la **riga attiva è evidenziata** come in un
editor, il **cursore è una barra nel colore d'accento** (quello nativo è 1px e si
perde), e un **doppio clic su un carattere mette il cursore lì**. Resa e sorgente
non sono la stessa stringa, quindi la posizione si calcola: il prototipo misura
il cursore su una copia invisibile della sorgente con la stessa metrica
(`.docedit__mirror`).

### Reference

`@[Nome]` nel Markdown diventa un link al contenuto: una **pillola
rettangolare** con il testo nel colore del contenuto citato e il fondo nella
stessa tinta, chiara. Se il nome è ambiguo si aggiunge il tipo:
`@[luogo:Il Guado Spezzato]`. Un nome che non corrisponde a niente diventa un
segnaposto marcato e non cliccabile, mai un link morto silenzioso.

Scrivendo `@` compare un **menu di suggerimenti con corrispondenza fuzzy**: le
lettere della query devono comparire in ordine, ma contano di più quelle
consecutive e quelle che iniziano una parola, quindi `@lm` trova «La Marchesa»
prima di «Muschioverde». Frecce per navigare, Invio o Tab per inserire, Escape
per chiudere. Le lettere che hanno fatto match sono evidenziate nel menu.

Il registro sta in `entities.js`: nel prodotto reale lo costruisce il server dai
contenuti del mondo.

Ogni documento ha un pannello **Collegamenti** a destra: chi lo cita, raggruppato
per tipo. È l'altra metà delle reference — servono solo se la navigazione
funziona nei due sensi.

### Blocco, bozza, immagine

- **Bloccato / Sbloccato** — da sbloccato il doppio clic entra in scrittura, da
  bloccato no. Lo stato è visibile nella barra della pagina.
- **Bozza / Pubblicato** — una bozza compare fra le bozze del suo tipo, non fra i
  contenuti ufficiali. Creare un luogo è la stessa superficie di scrittura di un
  luogo esistente, più questo stato.
- **Immagine** — si cambia **sul volto stesso**: il volto è il comando. La ×
  compare solo quando c'è una foto da togliere.

### Accenti

- **Pieno** — una tinta sola: la riga è vermiglia, i link sono sottolineati in
  vermiglio.
- **Gradiente** — tre tinte in sequenza (cielo · ocra · vermiglio), come la
  barra dei link del blog di riferimento. È costruita con i token della
  palette, non con colori isolati:

```css
--accent-grad: linear-gradient(to right,
  var(--p7) 0 33.33%, var(--p3) 33.33% 66.66%, var(--p1) 66.66% 100%);
--accent-grad-swap: linear-gradient(to right,
  var(--p1) 0 33.33%, var(--p3) 33.33% 66.66%, var(--p7) 66.66% 100%);
```

All'hover di un link la prima e la terza tinta **si scambiano** (`--accent-grad-swap`),
esattamente come nel blog. Si applica a: riga sotto i titoli, link nella prosa,
link della timeline, pulsanti testuali, voce attiva dell'indice e barra di
avanzamento delle letture.

## Simboli: icone e forme

Ogni ruolo dell'interfaccia ha **due simboli equivalenti**, definiti in
`marks.js`:

- un'**icona** lineare (bussola, persona, pin, calendario, libro, documento),
  che dice *cosa fa* la voce;
- una **forma** piena (cerchio, quadrato, triangolo, rombo, esagono, pentagono),
  che dice *dove sta* nella struttura.

Lo switch `Icone` / `Forme` cambia tutti i simboli togglabili
— navigazione e quick card della panoramica — e la scelta resta in
`localStorage` fra le pagine.

| Gancio | Comportamento |
|---|---|
| `data-mark="personaggi"` | simbolo del ruolo, segue lo switch Simboli |
| `data-shape="triangolo"` | forma fissa, sempre geometrica (radure) |
| `data-pref="accenti"` | pulsante di una preferenza, stato in `aria-pressed` |
| `data-set-views="separate"` | scorciatoia in pagina che cambia la preferenza Viste |

## Palette: 12 tinte, 12 forme

Le dodici radure dell'atlante hanno ciascuna una forma e una tinta, così una
radura si riconosce in un elenco, in una timeline o in una sessione. Le tinte
sono token `--p1 … --p12`; la striscia di prova è in fondo a `luoghi.html`.

| # | Tinta | # | Tinta |
|---|---|---|---|
| p1 | vermiglio | p7 | cielo |
| p2 | arancio | p8 | cobalto |
| p3 | ocra | p9 | indaco |
| p4 | oliva | p10 | prugna |
| p5 | bosco | p11 | rosa |
| p6 | turchese | p12 | argilla |

Anche le sessioni usano la palette: ogni riga del registro ha una tinta che la
segue nelle timeline, e i tre archi narrativi hanno un colore fisso.

## Personaggi e NPC

Un mondo contiene due tipi di personaggio: quelli **dei giocatori** e gli
**NPC**, scritti dal Master. Il Master vede entrambi, quindi ci sono due
architetture possibili.

**Deciso: nella master view sono separati.** Il prototipo parte quindi in
modalità `Separate`; lo switch resta per confrontare le due architetture sullo
stesso contenuto. Vedi `docs/features/frontend.md`.

| Modello | Navigazione | Elenco |
|---|---|---|
| **Separate** (default) | due voci, «Personaggi» e «NPC» | due elenchi indipendenti |
| **Unite** | una voce «Personaggi» | sezioni PG + NPC nella stessa pagina, con filtro |

Lo switch `Viste` nel rail le rende entrambe dallo **stesso markup**: la
preferenza scrive `data-views` sull'elemento radice e il CSS mostra o nasconde
sezioni e voce di navigazione (`.only-unite` / `.only-separate`). Ogni pagina
spiega in una nota quale dei due modelli si sta guardando e offre un pulsante
per passare all'altro, così il confronto non richiede di tornare al rail.

Il prototipo modella **solo la master view**: la vista del giocatore (nessuna
voce NPC, solo i propri personaggi) non è ancora disegnata.

Gli NPC si distinguono anche sulla scheda: bordo del proprietario tratteggiato e
badge `NPC` accanto al nome, per non confonderli con i personaggi giocanti.

## Volti dei personaggi

Niente Mondrian sui personaggi: il volto è **una campitura piena e un animale**
(`.face`). Nessun upload obbligatorio, nessuna immagine rotta, un volto
riconoscibile anche a 40 pixel. La scelta avviene in `nuovo-personaggio.html`,
con anteprima dal vivo della scheda.


## Identità visiva

### Palette

| Token | Valore | Uso |
|---|---|---|
| `--paper` | `#f3efe4` | Fondo carta |
| `--surface` | `#fffdf6` | Superfici di contenuto |
| `--ink` | `#17150f` | Testo e linee strutturali |
| `--muted` | `#6d6858` | Metadata |
| `--line` | `#d6cfbc` | Divisori secondari |
| `--rail` | `#14130e` | Costola di navigazione |
| `--vermilion` | `#d1402a` | Personaggi, accento principale |
| `--cobalt` | `#2c46a8` | Sessioni, link e focus |
| `--ochre` | `#e0a327` | Storie, evidenza |
| `--forest` | `#3c7a52` | Luoghi, mondo naturale |
| `--plum` | `#7b3f8f` | Accento secondario |

Le tinte piatte arrivano dalle illustrazioni placeholder (`assets/plate-*.svg`),
composizioni geometriche che riprendono il tema Mondrian senza usare fotografie.

### Tipografia

| Ruolo | Font | Uso |
|---|---|---|
| Display / prosa | Newsreader | Titoli, articoli, citazioni |
| Interfaccia | IBM Plex Sans | Descrizioni, pulsanti, liste |
| Metadata | IBM Plex Mono | Date, numeri, conteggi, eyebrow |

Il monospace segnala catalogazione; la prosa lunga è in serif per distinguere la
lettura dall'interazione.

### Forma

- Raggio minimo (`3px`), superfici rettangolari.
- Righe da `1px`: `--line` per i divisori, `--ink` per la struttura.
- Ombra piena `6px 6px 0 var(--ink)` solo su card e copertine, con
  `translate(-3px, -3px)` all'hover.
- Focus sempre visibile (`3px` cobalto).

## Componenti

| Componente | Dove | Note |
|---|---|---|
| `.masthead` | tutte le viste | Cella titolo + cella azioni divise da una riga |
| `.cover` | mondi | Copertina con badge volume, ruolo e conteggi |
| `.quick` | panorama mondo | Campitura piena: porta a una sezione, non rappresenta contenuto |
| `.card` + `.face` | personaggi | Scheda 4:5 con campitura piena ed emoji animale |
| `.feature` | luoghi, storie | Immagine ampia + sintesi |
| `.plogo` | luoghi | Forma colorata della radura |
| `.row` | liste compatte | Riga con logo e conteggio |
| `.ledger` | sessioni, pagine | Registro con colonne allineate e tinta per riga |
| `.story` | storie | Card editoriale con banda d'atto |
| `.timeline` | attività | Eventi senza card, con punto colorato per sessione |
| `.wherenow` | panorama mondo | Scena corrente: luogo con la sua forma e tinta |
| `.prose` | dettagli, pagine | Colonna di lettura ~68ch con callout e citazioni |
| `.pager` | sessione | Precedente / successiva deterministico |
| `.form` | creazione | Modulo con selettori, schede Scrivi/Anteprima |
| `.document` / `.docfield` | tutti i contenuti | Documento: campi senza riquadro, descrizione resa in place |
| `.docbar` | dettaglio | Blocco, pubblicazione, comando di modifica |
| `.links` | dettaglio | Collegamenti: chi cita questo contenuto |
| `.mention` | prosa | Reference, nel colore del contenuto citato |

## Pagine

| File | Vista |
|---|---|
| `index.html` | I mondi dell'utente + attività globale |
| `mondo.html` | Panoramica: striscia categorie, diario (ultime 4), storia in corso, scena corrente |
| `personaggi.html` | Elenco schede: PG + NPC (unite) o solo PG (separate) |
| `npc.html` | Elenco NPC scritti dal Master |
| `personaggio.html` | Dettaglio con prosa, scheda e sessioni collegate |
| `nuovo-personaggio.html` | Creazione: due impaginazioni, Markdown dal vivo, immagine |
| `luoghi.html` / `luogo.html` | Atlante delle dodici radure, con le bozze in fondo |
| `nuovo-luogo.html` | Creazione di una radura: forma, tinta, immagine, pubblicazione |
| `sessioni.html` / `sessione.html` | Registro cronologico (dalla più recente) e dettaglio |
| `storie.html` / `storia.html` | Archi narrativi |
| `pagine.html` / `pagina.html` | Pagine di riferimento e articolo con indice |
| `editor.html` | Confronto dei tre motori di scrittura |

## Interazioni

- Link reali fra pagine; nessuno stato nascosto in URL hash.
- Switch `Icone` / `Forme`, `Pieno` / `Gradiente` e `Unite` / `Separate` nel
  rail, con preferenza persistente.
- Filtro dell'elenco unico (tutti / personaggi / NPC).
- Drawer mobile con trigger, scrim e chiusura con `Escape`.
- Command palette con `Alt+Spazio` o `Cmd/Ctrl+K`, filtro e navigazione da
  tastiera.
- Anteprima dal vivo della scheda e del Markdown mentre si scrive.
- Upload immagine nella creazione: sostituisce l'animale sulla scheda.
- Indice attivo negli articoli via `IntersectionObserver`.
- `prefers-reduced-motion` disattiva le transizioni.

## Struttura dei file

```
devin-prototype/
├── index.html … pagina.html   15 viste
├── styles.css                            sistema visivo completo
├── marks.js                              icone, forme e preferenze visive
├── entities.js                           registro dei contenuti per le reference
├── markdown.js                           renderer minimo per l'anteprima dal vivo
├── shell.js                              rail, topbar, drawer, command palette
├── app.js                                indice, editor, filtro, blocco, pubblicazione
└── assets/plate-1…8.svg, favicon.svg     illustrazioni placeholder
```

La shell (rail e topbar) è iniettata da `shell.js`: ogni pagina dichiara il
proprio contesto con `<body data-page="…" data-world="boscochiaro">`. È una
scelta di prototipo per evitare di duplicare la navigazione in tredici file; la
logica definitiva resta server-side in `src/backend/`.

## Limiti dichiarati

- Dati finti hardcoded, nessuna persistenza.
- Nessun flusso di creazione/modifica reale: i pulsanti aprono pagine segnaposto.
- Nessun test automatico; la verifica è manuale sulle dodici viste.
