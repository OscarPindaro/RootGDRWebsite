# Root GDR — Prototipo GPT Luna

Prototipo statico single-page per esplorare l'identità visiva e l'organizzazione
dell'archivio di campagne Root GDR. Le viste vengono cambiate in JavaScript e
identificate nell'URL tramite hash; non sono una proposta per l'architettura
server-side definitiva.

## Avvio

```bash
cd prototypes/gpt-luna-prototype
python3 -m http.server 4173
# apri http://127.0.0.1:4173
```

Le viste sono raggiungibili anche direttamente:

- `#home` — mondi dell'utente;
- `#world` — panoramica del mondo;
- `#characters` — personaggi;
- `#places` — luoghi;
- `#sessions` — sessioni;
- `#stories` — storie;
- `#lore` e `#rules` — pagine statiche.

## Principio di design

Il linguaggio visivo è **editoriale neobrutalista**, con influenze moderniste e
Mondrian. L'applicazione viene trattata come un **archivio narrativo**, non come
una dashboard amministrativa.

La base editoriale mantiene leggibili testi e gerarchie; il neobrutalismo porta
personalità attraverso bordi scuri, ombre nette e campiture di colore. Questi
elementi espressivi sono concentrati su copertine, card principali, callout e
azioni primarie, mentre le aree di lettura restano calme.

Principi:

1. **Card per identità e scoperta.**
2. **Liste per sequenze, cronologia e densità.**
3. **Prosa per la lettura.**
4. **Blocchi colorati per la navigazione.**
5. **Colore per identità e gerarchia, mai come unica informazione.**

## Identità visiva

### Palette

| Token | Valore | Uso |
|---|---|---|
| `--paper` | `#f5f1e8` | Fondo caldo simile alla carta |
| `--surface` | `#fffdf8` | Card e superfici di contenuto |
| `--ink` | `#191918` | Testo, bordi e ombre dure |
| `--muted` | `#6c685f` | Testo secondario e metadata |
| `--line` | `#d9d2c4` | Divisori secondari |
| `--nav` | `#1b1c1a` | Sidebar |
| `--coral` | `#e45745` | Accento principale e identità |
| `--yellow` | `#f2c94c` | Evidenza, note e contenuti secondari |
| `--blue` | `#3e73d9` | Contrasto e navigazione |
| `--green` | `#4f9d69` | Luoghi e mondo naturale |

L'influenza Mondrian emerge da griglie rigorose, linee scure, campiture primarie
e composizioni asimmetriche. Non ogni componente deve essere colorato: lo spazio
neutro è necessario per dare significato agli accenti.

Distinguere sempre:

- colore **editoriale**, che caratterizza una superficie;
- colore **semantico**, che comunica successo, errore o avvertimento;
- colore **identitario**, che distingue mondi e contenuti.

### Tipografia

| Ruolo | Font | Uso |
|---|---|---|
| Sans | IBM Plex Sans | Interfaccia, descrizioni e testi lunghi |
| Mono | IBM Plex Mono | Date, ruoli, conteggi, eyebrow e scorciatoie |

Il monospace segnala catalogazione e dati strutturati; non viene usato per la
prosa lunga. Titoli grandi, pesanti e ravvicinati creano la gerarchia editoriale.
I font vengono caricati da Google Fonts nel prototipo; la produzione dovrà
scegliere se servirli localmente.

### Forma, spazio ed elevazione

- Bordi scuri e visibili sugli elementi principali.
- Ombre dure, senza sfocatura: `5px 5px 0 var(--ink)`.
- Superfici prevalentemente rettangolari e con raggi minimi.
- Spaziatura ampia tra sezioni e più compatta dentro i componenti.
- Hover delle card: lieve spostamento e crescita dell'ombra.
- Focus sempre visibile e ad alto contrasto.

## Sistema di componenti

### Card dei mondi

Sono copertine editoriali e contengono immagine o placeholder, attività recente,
ruolo dell'utente, titolo, sintesi, conteggi e azione di apertura. L'intera card
è interattiva. Una variante tratteggiata rappresenta la creazione di un mondo.

### Card dei personaggi

Sono schede visuali simili a oggetti da collezione: ritratto, specie, fazione,
nome, sintesi e proprietario. In assenza di un'immagine viene mostrato un
placeholder animale coerente con la specie, non soltanto le iniziali.

### Quick card

Le card colorate della panoramica non rappresentano contenuti: sono porte verso
Personaggi, Luoghi, Sessioni e Storie. Contengono simbolo, titolo, conteggio e
freccia; il colore pieno le distingue dalle card archivistiche.

### Luoghi

Composizione ibrida: un luogo principale ha immagine ampia e sintesi, mentre gli
altri luoghi sono righe compatte. In questo modo l'atmosfera del luogo in evidenza
convive con la scansione rapida dell'archivio.

### Sessioni

Registro cronologico, non griglia di card. Ogni riga presenta numero, data,
titolo, sintesi e apertura. La forma rende evidente la sequenza temporale e si
presta alla navigazione precedente/successiva.

### Storie

Card editoriali grandi e colorate con atto, periodo, titolo e sintesi. Sono più
espressive delle sessioni perché rappresentano archi narrativi, non singole
partite.

### Pagine statiche

Layout da articolo con header, colonna di lettura limitata, sottotitoli, liste,
citazioni e callout. La decorazione viene ridotta perché il compito principale è
leggere.

### Timeline e attività

L'attività globale usa una lista compatta; nel mondo viene usata una timeline più
narrativa. Gli eventi non sono racchiusi in card separate, evitando rumore
visivo e un eccesso di bordi.

### Sidebar

La sidebar scura rappresenta la struttura stabile dell'applicazione; la superficie
chiara rappresenta il documento corrente. Contiene identità del mondo,
navigazione, pagine statiche, ricerca e profilo. Su mobile diventa un drawer con
scrim e chiusura tramite Escape.

### Pulsanti

1. **Primario:** fondo scuro, testo chiaro, ombra colorata.
2. **Secondario:** superficie trasparente e bordo scuro.
3. **Testuale:** collegamento sottolineato o accompagnato da una freccia.

Una schermata dovrebbe avere una sola azione primaria evidente.

## Mappa contenuto → contenitore

| Contenuto | Rappresentazione |
|---|---|
| Mondi | Copertine/card |
| Personaggi | Card visuali |
| Luoghi | Featured card + lista |
| Sessioni | Registro cronologico |
| Storie | Card editoriali |
| Pagine statiche | Articolo/prosa |
| Attività | Lista o timeline |
| Sezioni principali | Quick card |

La coerenza non deriva dall'usare la stessa card ovunque, ma dall'applicare gli
stessi token e la stessa gerarchia a contenitori adatti al contenuto.

## Interazioni

- Navigazione tramite `data-view` e hash URL.
- Avanti/indietro del browser tra le viste.
- Command palette con `Alt+Spazio` o `Cmd+K`.
- Drawer mobile con trigger, scrim ed Escape.
- Stato attivo sincronizzato fra vista, breadcrumb e sidebar.

## Verifica Playwright

I test coprono destinazioni della sidebar, quick card, cronologia del browser,
command palette, drawer mobile ed errori console.

```bash
npm install
npm test
```

Il prototipo statico non richiede Node per essere aperto; Node e Playwright sono
necessari soltanto per la verifica automatizzata.

## Regole per riprodurre il linguaggio

1. Partire dai token, senza introdurre colori isolati nei componenti.
2. Mantenere separati sans per prosa/UI e mono per metadata.
3. Scegliere il contenitore in base al contenuto, non per uniformità superficiale.
4. Riservare bordi forti e ombre dure agli elementi principali.
5. Mantenere la sidebar scura e i documenti su superfici chiare.
6. Limitare la larghezza della prosa a circa `720px`.
7. Non affidare stato o significato al solo colore.
8. Conservare focus, tastiera e comportamento mobile in ogni nuovo componente.
