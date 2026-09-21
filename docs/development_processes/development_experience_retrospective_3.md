# Retrospettiva sull'esperienza di sviluppo — terzo giro

Decisioni e strumenti desiderati emersi dopo la terza iterazione. Questo documento conserva il feedback; le singole voci diventano ticket prima dell'implementazione.

## Decisioni

### CLI invece di MCP

La CLI `uv run harness` è l'interfaccia preferita. È più semplice da eseguire, osservare e correggere, non dipende da un server associato al worktree giusto e usa gli stessi comandi disponibili a una persona nel terminale.

Non serve estendere ulteriormente l'MCP del test harness. Le nuove funzionalità vanno aggiunte prima alla CLI.

### Screenshot semplici, Playwright per i flussi

`harness screenshot` può restare intenzionalmente semplice. Una schermata o una singola interazione sono il suo ambito; editor, dialoghi, conflitti, drag-and-drop e recovery meritano test Playwright dedicati.

Gli scenari visuali dichiarativi potrebbero essere utili, ma per ora aggiungerebbero troppa infrastruttura. L'idea resta da rivalutare se i test Playwright iniziano a ripetere molto codice di preparazione.

### Database distinti per test paralleli

Integration ed E2E non devono condividere il database. Useranno due database PostgreSQL distinti nello stesso container, per esempio `backend_integration_test` e `backend_e2e_test`.

In questo modo `harness test e2e --fresh` può ricreare il database E2E mentre gli integration test continuano a usare il proprio. Non servono due container Postgres.

## Strumenti prioritari

### Runner rapido JinjaX + JavaScript

Serve un test harness per i componenti frontend che:

- renderizzi un componente JinjaX con dati tipizzati;
- carichi automaticamente CSS e JavaScript colocati;
- fornisca htmx, localStorage, fake timer e `fetch` controllabile;
- permetta di testare tastiera, focus, autosave e stati offline;
- non richieda l'intero stack Docker.

È il miglior investimento emerso dal giro: button group, editor e image editor hanno molta logica locale che oggi viene verificata con E2E più costosi.

### Asserzioni browser → API

Tenere in considerazione un helper di più alto livello sopra `BrowserSession.expect_api`, capace di associare un'azione browser al risultato persistito atteso. L'idea sembra utile, ma l'interfaccia va progettata in un ticket dedicato.

### Confronto visuale strutturale

Integrare il pixel diff con misure del DOM:

- bounding box e allineamenti;
- gap e padding;
- font e token risolti;
- overflow della pagina e dei contenitori;
- touch target;
- presenza, ordine e stato degli elementi.

Il report dovrebbe spiegare differenze come “l'identità è sotto l'immagine” invece di fornire soltanto una percentuale. Il pixel diff rimane utile come segnale complementare.

### Gestione degli artefatti

Screenshot, report, replay, upload e file temporanei dei test devono:

- finire sempre sotto directory ignorate;
- essere separati per run o ambiente;
- avere un comando di pulizia selettivo;
- non lasciare file non tracciati nella root;
- non cancellare artefatti utili dopo un fallimento senza richiesta esplicita.

`data/` e `harness-artifacts/` sono già ignorati; il passo successivo è centralizzare creazione, retention e cleanup nel harness.

## Material 3: processo usato e da documentare

La pagina M3 dei button group richiede JavaScript e non espone una specifica completa scaricabile in Markdown. Per ottenere valori verificabili sono state incrociate fonti Google ufficiali:

1. pagine M3 `button-groups/specs` e `button-groups/guidelines` per varianti, comportamento e configurazioni;
2. documentazione `material-components-android` per anatomia, spacing, connected group e API;
3. XML di token generati in `material-components-android` per dimensioni, padding, icone e forme;
4. sorgente AndroidX Compose `ButtonGroup.kt` per espansione del 15%, compensazione dei vicini e comportamento standard/connected.

I valori dp sono stati mappati a CSS px. I token fisici della molla sono conservati, mentre la transizione CSS è dichiarata come adattamento web quando il browser non offre una primitiva portabile basata su stiffness/damping.

Da costruire:

- un inventario versionato dei token con URL, commit/versione sorgente e data di acquisizione;
- un estrattore che generi CSS e test dai token ufficiali quando possibile;
- un controllo che renda espliciti valori mancanti o adattati, senza presentarli come equivalenti esatti.

## Ordine suggerito

1. Separare i database integration ed E2E nello stesso Postgres.
2. Costruire il runner rapido JinjaX + JavaScript.
3. Centralizzare artefatti e cleanup.
4. Aggiungere il confronto visuale strutturale.
5. Documentare e poi automatizzare l'acquisizione dei token M3.
6. Valutare l'helper browser → API.
7. Rivalutare gli scenari dichiarativi solo se emerge duplicazione concreta.
