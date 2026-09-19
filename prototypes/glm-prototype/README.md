# Root GDR — Prototipo GLM

Prototipo statico **multipagina** di un archivio di campagne di gioco di ruolo.
Serve a esplorare flussi, gerarchia delle informazioni e identità visiva prima di
scrivere il codice di produzione (FastAPI + JinjaX + htmx).

- Nessun framework, nessun build step, nessuna dipendenza esterna.
- 18 file HTML autonomi, un CSS con design token, un solo file JS per la shell.
- Dati finti hardcoded: non c'è backend né persistenza.

Questo documento è la **specifica di identità visiva**. Chi vuole riprodurre o
estendere il prototipo dovrebbe seguire le regole delle sezioni "Regole" invece
di copiare valori a caso.

---

## 1. Avvio

```bash
cd prototypes/glm-prototype
python3 -m http.server 8090
# apri http://127.0.0.1:8090
```

Non serve altro. Aprire i file con `file://` funziona quasi ovunque, ma conviene
servirli via HTTP per avere percorsi e `localStorage` coerenti.

### Struttura dei file

```
glm-prototype/
├── styles.css        # design token + tutti i componenti
├── app.js            # shell condivisa, drawer, collapse, command palette
├── index.html        # login
├── mondi.html        # elenco mondi (fuori dal contesto mondo)
├── mondo.html        # panoramica del mondo
├── personaggi.html   # elenco personaggi
├── personaggio.html  # dettaglio personaggio (modifica Markdown in-place)
├── luoghi.html       # elenco luoghi
├── luogo.html        # dettaglio luogo
├── sessioni.html     # elenco sessioni
├── sessione.html     # dettaglio sessione (precedente / successiva)
├── storie.html       # elenco storie
├── storia.html       # dettaglio storia
├── pagine.html       # elenco pagine statiche
├── pagina.html       # dettaglio pagina statica
└── nuovo-*.html      # form di creazione (personaggio, luogo, sessione, storia, pagina)
```

Ogni pagina dichiara il proprio contesto sul `<body>`:

```html
<body data-page="personaggi" data-world="fronte-del-tuono" data-nav="personaggi"
      data-crumbs="I tuoi mondi::mondi.html|Fronte del Tuono::mondo.html|Personaggi">
```

- `data-page` — chiave della pagina, usata anche per le regole di stile contestuali.
- `data-world` — mondo attivo; assente sulle pagine fuori dal mondo (login, elenco mondi).
- `data-nav` — voce di sidebar da evidenziare (default: `data-page`).
- `data-crumbs` — briciole separate da `|`; ogni voce è `Etichetta::href`, l'ultima è testo semplice.

`app.js` inietta sidebar, topbar e command palette dentro `#sidebar`, `#topbar`
e un `#palette` creato al volo. **Nessuna pagina duplica la shell.**

---

## 2. Principio di design

L'app è trattata come un **archivio editoriale**, non come una dashboard.
Tre conseguenze operative:

1. Molto spazio bianco e gerarchia tipografica forte.
2. Il contenitore cambia in base al contenuto (card / lista / prosa), invece di
   applicare la card ovunque.
3. Il colore è **semantico** (ruolo, stato, azione), non decorativo.

---

## 3. Identità visiva

### 3.1 Tipografia — tre ruoli

| Ruolo | Stack | Uso |
|---|---|---|
| Serif | `"Iowan Old Style", "Palatino Linotype", Georgia, serif` | Titoli (`h1`–`h3`) e corpo dei testi lunghi |
| Sans | `"Inter", "Segoe UI", system-ui, -apple-system, sans-serif` | Interfaccia: bottoni, label, navigazione |
| Mono | `"JetBrains Mono", "SFMono-Regular", ui-monospace, Menlo, monospace` | Metadati: date, contatori, slug, posizioni, eyebrow |

**Regole**

- Il serif è riservato a titoli e prosa. Non usarlo per controlli o etichette.
- Il mono segnala "dato strutturato, non prosa". Se un'informazione è una data,
  un numero, un contatore o un identificatore, è mono.
- Il sans è il default dell'interfaccia.

Scala tipografica:

| Elemento | Dimensione | Note |
|---|---|---|
| `h1` | `2rem` | `line-height: 1.2`, `letter-spacing: -.01em` |
| `h2` | `1.35rem` | |
| `h3` | `1.08rem` | |
| Corpo UI (`body`) | `15px` / `1.55` | |
| Prosa lunga (`.prose`) | `1.05rem` / `1.7` | dentro il dettaglio, larghezza max ~820px |
| Eyebrow (`.eyebrow`) | `.68rem` mono, uppercase, `letter-spacing: .14em` | etichetta sopra i titoli |
| Meta (`.small`) | `.82rem` | |

### 3.2 Colore

Token (definiti in `:root`):

| Token | Valore | Uso |
|---|---|---|
| `--bg` | `#eef1ec` | Fondo pagina (carta/salvia) |
| `--surface` | `#ffffff` | Superfici: card, topbar, campi |
| `--surface-2` | `#f6f8f4` | Superfici secondarie: hover, barre, placeholder |
| `--line` | `#d7ddd2` | Bordi e divisori |
| `--ink` | `#17211c` | Testo principale |
| `--ink-soft` | `#5c6b62` | Testo secondario |
| `--ink-faint` | `#8b978f` | Metadati, eyebrow |
| `--moss` | `#2f6b4f` | Azione primaria, stato "Master" |
| `--moss-2` | `#dcefe2` | Fondo tenue dell'azione primaria |
| `--berry` | `#a83a4b` | Azione distruttiva, errore |
| `--ochre` | `#c78a1f` | Avviso, nota |
| `--indigo` | `#3d4bb0` | Stato "Giocatore", avatar alternativo |
| `--sidebar-bg` | `#16201c` | Sidebar |
| `--sidebar-ink` | `#e9efe9` | Testo sidebar |
| `--sidebar-mute` | `#93a29a` | Testo secondario sidebar |

**Regole**

- Un solo colore d'azione per schermata: il muschio. Il berry è riservato a
  eliminazione/errore, l'ocra all'avviso, l'indaco agli stati alternativi.
- Il colore comunica stato (pill, badge, dot), non decora. Se un elemento non ha
  un significato da veicolare, resta su `--surface` / `--line`.
- La sidebar è sempre scura: separa struttura e contenuto.
- Ogni pill di ruolo usa fondo tenue + testo saturo dello stesso colore.

### 3.3 Forma, spazio, elevazione

| Token | Valore |
|---|---|
| `--r-sm` | `8px` (controlli piccoli) |
| `--r-md` | `14px` (bottoni, chip, editor) |
| `--r-lg` | `22px` (card, pannelli) |
| `--shadow-1` | `0 1px 2px rgba(23,33,28,.06), 0 4px 14px rgba(23,33,28,.06)` |
| `--shadow-2` | `0 10px 30px rgba(23,33,28,.14)` |
| `--sidebar-w` | `268px` |

**Regole**

- Spaziatura su base 4 (`0.25rem`). Il ritmo di pagina usa `1.4rem`–`2.4rem`
  tra i blocchi.
- **Un solo livello di elevazione a riposo** (`--shadow-1`). `--shadow-2` solo
  per hover delle card e per overlay (palette, drawer).
- Le griglie usano `repeat(auto-fill, minmax(...))` così collassano da sole,
  senza breakpoint dedicati:
  - `.cols-2` → `minmax(340px, 1fr)`
  - `.cols-3` → `minmax(240px, 1fr)`
- Breakpoint solo dove servono davvero: `980px` (dettaglio a una colonna) e
  `760px` (drawer mobile).

---

## 4. Sistema di contenitori

Questa è la decisione progettuale centrale: **tre contenitori per tre tipi di
contenuto**. Non usare la card ovunque.

| Contenitore | Dove | Perché |
|---|---|---|
| **Card** (`.card` + `.card-link`) | Mondi, Personaggi, Luoghi, Storie | Oggetti che si "aprono": hanno identità visiva (copertina), titolo e sintesi. La card anticipa il dettaglio e invita al click. |
| **Lista** (`.list`) | Sessioni, Pagine | Sequenze ordinate e dense. Posizione/indice e data sono l'informazione primaria, non un'immagine. |
| **Prosa** (`.prose`) | Dettagli, pagine statiche | Contenuto da leggere, non da scansionare. |

### 4.1 Anatomia della card

```
┌──────────────────────────┐
│  .card-cover (120px)     │  ← identità: emoji/immagine su gradiente
├──────────────────────────┤
│  .card-body              │
│    pill (ruolo/stato)    │
│    h3 (titolo)           │
│    p.muted.small (sintesi)
│    .stat-row (conteggi)  │
│    .foot (data | "Apri →")
└──────────────────────────┘
```

**Regole**

- `h3` per il titolo (non `h2`): la card è un elemento, non una sezione.
- La copertina è alta `120px` nell'elenco e `aspect-ratio: 1/1` nel dettaglio.
- L'intera card è un link (`.card-link`); hover: `translateY(-2px)` + `--shadow-2`.
- Il footer separa metadato (a sinistra) e azione (a destra, in muschio).
- La variante "crea nuovo" è una card con bordo tratteggiato, sfondo
  `--surface-2`, centrata.

### 4.2 Anatomia della lista

```
[ 24 ]  Titolo                    14 mar 2026
        sottotitolo (mono/muted)
```

**Regole**

- `.idx` a larghezza fissa (`34px`) per allineare i numeri.
- La data va a destra, in mono, `white-space: nowrap`.
- Righe separate da `1px solid var(--line)`, nessun bordo esterno oltre al
  contenitore `.card`.
- Hover: fondo `--surface-2`. È una riga cliccabile, non una card.

### 4.3 Composizione del dettaglio (scheda museale)

Griglia a due colonne (`300px 1fr`):

- **Sinistra** — l'oggetto: `.detail-media` (quadrato, `aspect-ratio: 1/1`) e
  una `.meta-list` di coppie chiave/valore (Mondo, Proprietario, Creato,
  Aggiornato). La chiave è mono/maiuscola, il valore è testo normale.
- **Destra** — il racconto: `.page-head` con eyebrow, `h1`, sottotitolo e azioni,
  poi la `.prose`.

Lo stesso pattern vale per personaggio e luogo: l'utente impara una volta sola.

### 4.4 Timeline

Usata per l'attività recente: linea verticale a sinistra (`2px solid var(--line)`)
con punto colorato (`12px`) e bordo del colore di fondo. L'ultimo elemento perde
la linea. Comunica "cronologia" senza usare una tabella.

### 4.5 Editor Markdown in-place

- Il testo renderizzato (`.prose`) viene sostituito da `.editor` con Salva/Annulla.
- `.editor` è incorniciato: barra strumenti su `--surface-2` + `textarea` in mono.
- Il `textarea` è sempre presente nel DOM come fallback: se il miglioramento JS
  fallisce, resta un campo modificabile.
- Focus visibile: `outline: 2px solid var(--moss)` con offset negativo.

---

## 5. Inventario dei componenti

Tutti in `styles.css`, prefissati e riusabili:

| Componente | Classe | Varianti |
|---|---|---|
| Bottone | `.btn` | `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.btn-sm` |
| Icon button | `.icon-btn` | — |
| Card | `.card`, `.card-link`, `.card-body`, `.card-cover` | — |
| Pill / badge | `.pill` | `.master`, `.player`, `.warn` |
| Lista | `.list` | — |
| Timeline | `.timeline` | — |
| Prosa | `.prose` | — |
| Editor | `.editor`, `.editor-bar`, `.tool` | — |
| Form | `.form`, `.field` | `.field.invalid`, `.field .error`, `.hint` |
| Stato vuoto | `.empty` | — |
| Eyebrow | `.eyebrow` | — |
| Avatar | `.avatar` | — |
| Topbar | `.topbar`, `.crumbs` | — |
| Sidebar | `.sidebar`, `.nav`, `.world-chip` | `body.collapsed` |
| Drawer | `.scrim` | `body.drawer-open` |
| Command palette | `.palette`, `.palette-box`, `.palette-item` | `.show`, `.active` |
| Nota di prototipo | `.proto-note` | — |

---

## 6. Interazioni e stati

- **Sidebar collapse (desktop)** — `body.collapsed`; lo stato è persistito in
  `localStorage` (`glmproto.collapsed`). Con sidebar collassata, le etichette
  (`.hide-collapsed`) spariscono e restano le icone.
- **Drawer mobile** — `body.drawer-open` + `.scrim.show`; si chiude con scrim,
  Escape o cliccando una voce. Il trigger (`☰`) esiste solo sotto `760px`.
- **Command palette** — aperta con `Alt+Spazio` o dai pulsanti `[data-palette]`.
  Ricerca su mondi, contenuti, navigazione e azioni di creazione. Frecce per
  muoversi, Invio per attivare, Escape per chiudere. Le azioni di creazione sono
  filtrate per ruolo.
- **Focus** — sempre visibile (`outline: 2px`); mai rimosso.
- **Stato di errore** — `.field.invalid` colora bordo e messaggio in berry e
  **non scarta il testo inviato**.

---

## 7. Regole per riprodurre

Se devi rifare questa identità da zero:

1. Definisci i token di §3.2 e §3.3 in `:root`. Non introdurre colori fuori tabella.
2. Imposta i tre ruoli tipografici di §3.1 e rispettane la separazione.
3. Applica il sistema di contenitori di §4: **card per oggetti, lista per
   sequenze, prosa per lettura**. Non usare card per liste ordinate.
4. Un solo livello di elevazione a riposo; la seconda ombra solo su hover/overlay.
5. Sidebar scura, contenuto su fondo carta, superfici bianche.
6. Griglie con `auto-fill`/`minmax` invece di breakpoint dedicati.
7. Colore = significato. Pill e badge veicolano ruolo e stato.
8. Larghezza di lettura massima ~820px per la prosa.

---

## 8. Estendere il prototipo

- **Nuova pagina** — copia una pagina esistente, aggiorna `data-page` /
  `data-nav` / `data-crumbs` e il contenuto. La shell arriva da sola.
- **Nuova voce di navigazione** — aggiungila all'array `NAV` in `app.js`.
- **Nuovo contenuto ricercabile** — aggiungi una voce all'indice `INDEX` in
  `app.js` (gruppo, etichetta, href, tipo).
- **Nuovo componente** — mettilo in `styles.css` come classe riusabile, non
  come stile inline nella pagina.
