# Retrospettiva sull'esperienza di sviluppo — terzo giro

Decisioni, problemi osservati e strumenti desiderati dopo la terza iterazione.
Questo documento deve essere sufficiente per trasformare ogni proposta in ticket
senza dover ricostruire il contesto dalla cronologia della sessione.

Non è un'autorizzazione a implementare tutto insieme. L'ordine in fondo divide il
lavoro in ticket indipendenti, ciascuno con test e commit propri.

## 1. Contesto della terza iterazione

Il giro ha introdotto o consolidato:

- editing in-place con CodeMirror, autosave, recovery locale e optimistic locking;
- creazione draft-first per i sei tipi di contenuto;
- image editor con storico delle revisioni;
- button group M3 Expressive;
- confronti app/prototipo desktop e telefono;
- replay UI/backend;
- nuovi comandi `harness doctor`, `smoke`, `logs` ed E2E fresh;
- hook preventivi per JinjaX, route e payload htmx.

La verifica finale ha richiesto test unit, integration, E2E, migrazioni,
screenshot e confronti visuali. I problemi di developer experience qui descritti
sono quelli che hanno prodotto lavoro ripetitivo o rischiato falsi risultati.

### File da leggere prima di lavorare sui ticket

- `AGENTS.md`
- `src/harness/cli.py`
- `src/harness/commands/test.py`
- `src/harness/test/{config,environment,compose,runner,browser}.py`
- `tests/e2e/conftest.py`
- `src/backend/replay/`
- `src/harness/replay.py`
- `src/harness/commands/compare.py`
- `src/harness/test/compare.py`
- `seed/prototype_map.yaml`
- `docs/features-request/prototype_map.md`
- `src/frontend/components/layout/BlankPage.jinja`
- `src/frontend/components/pages/showcase/Showcase.jinja`
- `src/frontend/static/css/main.css`

## 2. Decisioni già prese

### 2.1 La CLI è l'interfaccia primaria

Usare `uv run harness ...` invece di estendere l'MCP del test harness.

Motivi osservati:

- la CLI usa esplicitamente il checkout e il cwd correnti;
- i comandi e il loro output sono riproducibili da agente e persona;
- errori, help e stato sono visibili senza un ulteriore livello di protocollo;
- durante il giro l'MCP disponibile puntava a un altro worktree, mentre la CLI
  locale funzionava correttamente;
- testare una funzione CLI significa testare anche il percorso realmente usato
  fuori dall'agente.

Regola per i prossimi strumenti:

1. implementare una funzione Python testabile;
2. esporla nella CLI;
3. documentarla in `AGENTS.md` e nel relativo feature document;
4. aggiungere un wrapper MCP solo se emerge un caso concreto che la CLI non può
   coprire.

Non serve eliminare subito l'MCP esistente. Non deve però essere il requisito per
eseguire o verificare il progetto.

### 2.2 `harness screenshot` resta semplice

Il comando copre:

- una route;
- desktop e telefono;
- al massimo una semplice azione preparatoria (`click` oppure `hover`);
- un elemento atteso visibile;
- raccolta degli errori console.

Non deve diventare un linguaggio di automazione. Editor, dialoghi, drag-and-drop,
conflitti, recovery e workflow multi-step vanno testati con Playwright dedicato.

### 2.3 Gli scenari dichiarativi sono rinviati

Un formato YAML per sequenze browser è possibile, ma oggi duplicherebbe una
parte di Playwright, introdurrebbe un parser e renderebbe più difficile il debug.

Rivalutare soltanto se si verificano entrambe queste condizioni:

- almeno tre test ripetono la stessa preparazione multi-step;
- estrarre fixture/helper Python non riduce abbastanza la duplicazione.

Prima opzione: fixture e helper Playwright normali. Lo scenario dichiarativo è
l'ultima opzione, non la prima.

## 3. Database integration ed E2E separati

### 3.1 Problema osservato

Integration ed E2E usavano lo stesso database `backend_test`. Durante la verifica
è stato lanciato in parallelo:

- `harness test integration`;
- `harness test e2e --fresh`.

`--fresh` ha ricreato lo schema mentre gli integration test lo stavano usando.
Il risultato è stato un grande numero di errori apparentemente applicativi, ma
causati esclusivamente dal reset concorrente. Eseguendo gli stessi integration
test dopo l'E2E, tutti sono passati.

Il problema non richiede due container PostgreSQL. Richiede due database nello
stesso container.

### 3.2 Stato attuale

- `test.env` imposta `DATABASE__DB=backend_test` e
  `MIGRATOR__DB=backend_test`.
- `src/harness/test/config.py` genera una configurazione local e una docker.
- `src/harness/test/compose*.yml` avvia un solo PostgreSQL.
- `harness test integration` importa il backend direttamente e usa la config
  local attiva.
- l'E2E usa il backend containerizzato e la config docker attiva.
- `harness test e2e --fresh` ricrea l'ambiente test e i suoi upload.

### 3.3 Comportamento desiderato

Nello stesso PostgreSQL:

- `backend_integration_test`: usato solo dai test integration;
- `backend_e2e_test`: usato solo dal backend Docker e dai test E2E.

Nomi configurabili, ma deterministici e chiaramente marcati `_test`.

`harness test e2e --fresh` può distruggere soltanto
`backend_e2e_test` e gli upload E2E. Non deve fermare, ricreare o migrare il
database integration.

### 3.4 Proposta di implementazione

#### Configurazione

Aggiungere a `test.env` valori non segreti:

```dotenv
TEST_INTEGRATION_DB=backend_integration_test
TEST_E2E_DB=backend_e2e_test
```

Non affidarsi a un unico `DATABASE__DB` nel file condiviso, perché le variabili
d'ambiente hanno precedenza sullo YAML generato. Il harness deve generare sotto
la propria directory di stato due env/config effettivi:

- integration/local: `DATABASE__DB` e `MIGRATOR__DB` puntano al DB integration;
- E2E/docker: puntano al DB E2E.

Estendere `ConfigState` in `src/harness/test/state.py` con nomi espliciti, non con
una lista anonima. Per esempio:

```python
integration_config: Path
integration_env: Path
e2e_config: Path
e2e_env: Path
```

La forma finale può differire, ma deve essere impossibile confondere i due target.

#### Creazione dei database

Dopo che PostgreSQL è ready, il harness deve assicurare idempotentemente che
entrambi i database esistano. Questo controllo deve funzionare anche con un
volume creato prima dell'introduzione del secondo database: non basta modificare
solo gli script `docker-entrypoint-initdb.d`, che girano esclusivamente su un
volume vuoto.

Usare il superuser Postgres già confinato nel container per:

1. controllare l'esistenza dei due database;
2. crearli quando mancano;
3. applicare owner e grant coerenti con il modello `migrator_user`/`app_user`;
4. eseguire Alembic separatamente su entrambi.

Non stampare password o env completi.

#### Runner

- `harness test integration` deve esportare env/config integration.
- `harness test e2e` continua a guidare il backend Docker, configurato sul DB
  E2E.
- `harness env up --mode local` prepara il DB integration.
- `harness env up --mode docker` prepara entrambi, ma il servizio app usa E2E.
- `harness doctor` mostra readiness e conteggio connessioni per entrambi.
- `harness logs` non cambia.

#### Fresh

`harness test e2e --fresh`:

- verifica esplicitamente il nome del DB E2E;
- rifiuta nomi non terminanti in `_test`;
- resetta solo quel database/schema e il relativo storage upload;
- riesegue le migrazioni E2E;
- riavvia/health-checka soltanto il backend E2E se necessario;
- non modifica la configurazione o le connessioni integration.

### 3.5 Test richiesti

Unit:

- config generation produce due nomi e due env distinti;
- guard fresh rifiuta work/show/integration;
- comandi compose/psql contengono il database corretto;
- env del runner integration ed E2E non si sovrappongono.

Integration del harness:

1. avvia un solo Postgres;
2. crea una tabella/riga nel DB integration;
3. crea una tabella/riga nel DB E2E;
4. esegue fresh E2E;
5. prova che la riga integration esiste ancora;
6. prova che la riga E2E precedente non esiste più.

Concorrenza:

```bash
uv run harness test integration &
uv run harness test e2e --fresh &
wait
```

Entrambi devono passare più volte senza race.

### 3.6 Criteri di accettazione

- un solo container PostgreSQL;
- due database isolati;
- integration ed E2E eseguibili in parallelo;
- fresh E2E non interrompe integration;
- nessun accesso al database scratch/showcase;
- configurazione test originale ripristinata dopo teardown;
- documentazione aggiornata in `AGENTS.md` e `harness-tooling.md`.

## 4. Runner rapido JinjaX + JavaScript

### 4.1 Problema osservato

Button group, autosave editor e image editor hanno logica principalmente locale:

- eventi tastiera;
- focus e dialog;
- timer di debounce e hard deadline;
- localStorage;
- richieste `fetch` e risposte 409/423/offline;
- htmx lifecycle;
- drag-and-drop;
- CSS/JS colocati caricati da JinjaX.

Per verificarla oggi si usano test Playwright E2E o pagine HTML costruite a mano.
Gli E2E danno fiducia alta, ma richiedono Docker, migrazioni, login, seed e più
secondi per caso. Le pagine costruite a mano rischiano di non corrispondere al
markup JinjaX reale.

### 4.2 Obiettivo

Aggiungere un livello di test frontend tra unit Python ed E2E completo:

- usa il componente JinjaX reale;
- usa CSS e JS colocati reali;
- gira in Chromium;
- non usa database, backend Docker o autenticazione reale;
- controlla tempo, rete e storage;
- fallisce su errori console.

### 4.3 Architettura proposta

Preferire l'infrastruttura Playwright Python già installata, evitando per ora
Vitest/Jest/jsdom e una seconda toolchain JavaScript.

Creare un modulo simile a:

```text
src/harness/frontend/
├── renderer.py
├── server.py
├── session.py
└── state.py
```

E fixture sotto `tests/frontend/`.

#### Renderer

API indicativa:

```python
session.mount(
    "common.ButtonGroup",
    props=ButtonGroupFixture(...),
    content="...",
)
```

Requisiti:

- props tipizzate, non dizionari anonimi per dati di dominio;
- rendering tramite il vero `backend.jinja.get_catalog`;
- pagina shell minima con `catalog.render_assets()`;
- caricamento di `main.css`, CSS/JS del componente e dipendenze JinjaX;
- htmx/json-enc locali quando richiesti;
- nessun CDN obbligatorio;
- markup restituito disponibile per assert Python.

#### Server effimero

Servire su porta allocata dinamicamente:

- HTML renderizzato;
- `/static/` reale del repository;
- `/static/components/` reale;
- endpoint finti configurabili dai test.

Il server deve chiudersi sempre nel teardown e non scrivere nella repository.

#### Browser session

Helper indicativi:

```python
component.click(test_id="document-edit")
component.press("Control+Enter")
component.expect_text("Salvato")
component.expect_focus("image-history-close")
component.route_json("PATCH", "/api/...", status=409, body={...})
component.go_offline()
```

Usare Playwright Clock (`page.clock`) se disponibile nella versione installata
per avanzare 1 s/5 s senza sleep reali. In alternativa isolare la clock dietro
un adapter sostituibile.

Lo storage deve essere un browser context nuovo per test, con helper per
precaricare/ispezionare localStorage.

#### htmx

I test devono poter emettere `htmx:afterSwap`, `beforeRequest` e sostituire un
fragmento, per verificare che i mount siano idempotenti dopo swap.

### 4.4 Primo set di componenti da coprire

`common.ButtonGroup`:

- single optional/required, multi;
- frecce/Home/End/Space;
- disabled;
- width compensation;
- reduced motion.

`editorial.DocEdit`/`DocSummary`:

- debounce 1 s, max 5 s, soglia caratteri;
- queue sequenziale;
- local recovery;
- 409/423/offline;
- preview e Escape;
- nessun bundle in readonly.

`editorial.ImageEditor`:

- tastiera e focus;
- drop upload;
- storico, restore, clear/delete;
- focus return e Escape;
- errori API italiani.

### 4.5 Comando CLI

Aggiungere, per esempio:

```bash
uv run harness test frontend
```

Il nome può cambiare, ma deve essere distinto da E2E e non richiedere
`harness env up`.

Marker pytest dedicato: `frontend` o `component`, documentato in `pyproject.toml`.

### 4.6 Criteri di accettazione

- nessun Docker/Postgres;
- mount del vero componente, non HTML duplicato;
- JS e CSS colocati caricati automaticamente;
- timer virtuali, rete e localStorage controllabili;
- console/page errors fanno fallire il test;
- test eseguibili singolarmente per node id;
- durata dell'intera suite iniziale nell'ordine dei secondi, non dei minuti;
- gli E2E restano per i workflow completi e non vengono eliminati indiscriminatamente.

## 5. Asserzioni browser → API

### 5.1 Stato

`BrowserSession.expect_api(...)` verifica già risposte e payload tramite lo stesso
browser context autenticato. Nei test attuali l'azione UI e l'asserzione API
sono però due passaggi scritti separatamente.

### 5.2 Direzione da conservare

Valutare un helper che associ esplicitamente:

- azione browser;
- attesa di navigazione/swap;
- risorsa API risultante;
- campi persistiti attesi.

L'interfaccia non è decisa. Non implementare un DSL generale in questo ticket.
Prima raccogliere tre casi reali ripetuti e progettare l'API su quelli.

Vincoli:

- deve restare leggibile nel test;
- non deve inferire silenziosamente quale risorsa controllare;
- deve produrre errori che mostrino azione, endpoint, status e differenza dati;
- deve supportare ID creati durante l'azione;
- non deve sostituire integration test quando serve verificare stato non esposto
  dall'API.

Criterio per aprire il ticket: duplicazione concreta in almeno tre journey.

## 6. Confronto visuale strutturale

### 6.1 Stato attuale

`harness compare`:

- mappa route app → pagina prototipo con `seed/prototype_map.yaml`;
- cattura desktop e Pixel 7;
- calcola un pixel diff in Chromium;
- produce un report HTML;
- tratta la percentuale come segnale, non come gate.

La percentuale è sensibile a dati, font rendering e testo. Non descrive la causa
della differenza.

### 6.2 Obiettivo

Aggiungere al report una sezione DOM/geometry, mantenendo il pixel diff.

### 6.3 Elementi da misurare

Per ogni viewport:

- `documentElement.scrollWidth/clientWidth`;
- rail/drawer, main, container;
- masthead e azioni;
- quick strip;
- docbar;
- document head, face, identity, summary, body;
- dialog aperti quando lo scenario li prevede;
- elementi esplicitamente marcati con un attributo stabile, per esempio
  `data-compare="document-face"`.

Per elemento:

```json
{
  "selector": "[data-compare=document-face]",
  "rect": {"x": 0, "y": 0, "width": 240, "height": 300},
  "display": "grid",
  "fontFamily": "...",
  "fontSize": "...",
  "lineHeight": "...",
  "gap": "...",
  "padding": "...",
  "borderWidth": "...",
  "overflowX": "..."
}
```

### 6.4 Mapping

Non tentare di confrontare automaticamente ogni nodo. Usare una piccola lista
di landmark semantici condivisi oppure una mappa esplicita app/prototipo.

Possibili estensioni di `seed/prototype_map.yaml`:

```yaml
routes:
  /worlds/{world_id}/characters/{character_id}:
    prototype: personaggio.html
    landmarks:
      identity:
        app: "[data-compare=document-identity]"
        prototype: ".document__id"
      face:
        app: "[data-compare=document-face]"
        prototype: ".document__face"
```

Mantenere i modelli Pydantic per questa configurazione.

### 6.5 Report

Esempi di diagnostica utile:

- `face.width: app 320px, prototype 240px (+80px)`;
- `identity.y differs by 310px: app is below face`;
- `page overflow: scrollWidth 411 > clientWidth 390`;
- `touch target below 44px: document-lock 36×32`;
- `font family differs on title`;
- `landmark missing in app/prototype`.

Tolleranze configurabili per posizione/dimensione, ma niente gate globale al
primo giro. Il report deve permettere di distinguere differenze dati da errori
strutturali.

### 6.6 Test e accettazione

- fixture HTML sintetiche con differenze note;
- estrazione deterministica delle metriche;
- report segnala overflow, landmark mancante e geometria divergente;
- app e prototipo identici producono zero differenze strutturali;
- il vecchio pixel diff continua a funzionare;
- nessun selettore basato sulla copy italiana;
- desktop e telefono inclusi nello stesso report.

## 7. Artefatti e cleanup

### 7.1 Problema osservato

Durante i test sono stati creati:

- screenshot e report sotto `harness-artifacts/`;
- replay;
- upload locali sotto `data/`;
- report temporanei sotto `/tmp`;
- file che, prima di aggiornare `.gitignore`, apparivano come untracked.

`data/` e `harness-artifacts/` sono ora ignorati, ma ogni comando decide ancora
in autonomia directory, naming e retention.

### 7.2 Layout proposto

Centralizzare in un modulo, per esempio `src/harness/artifacts.py`:

```text
harness-artifacts/
└── <run-id>/
    ├── manifest.json
    ├── screenshots/
    ├── compare/
    ├── replay/
    ├── uploads/
    └── logs/
```

`run-id`: timestamp UTC leggibile + suffisso casuale, oppure ID passato dal
chiamante. Vietare path traversal e nomi arbitrari fuori root.

Manifest Pydantic:

- id e comando;
- data inizio/fine;
- worktree/revision Git, senza env segreti;
- stato `running/passed/failed/interrupted`;
- file prodotti;
- eventuale parent run;
- retention/pinned.

### 7.3 API del modulo

- `create_run(kind, metadata)`;
- `run.path_for(ArtifactKind.SCREENSHOT, name)`;
- `run.mark_passed()/mark_failed()`;
- `list_runs(...)`;
- `cleanup(policy, dry_run=True)`.

Screenshot, compare e replay devono usare questa API invece di costruire path
indipendenti.

Gli upload test devono usare storage confinato alla run o un volume E2E
identificabile, non `data/` nella root quando il test non lo richiede.

### 7.4 CLI

```bash
uv run harness artifacts list
uv run harness artifacts show <run-id>
uv run harness artifacts clean --older-than 7d --keep-latest 5 --dry-run
uv run harness artifacts clean --kind screenshot --older-than 2d
```

La cancellazione è distruttiva:

- default `--dry-run`;
- richiede flag esplicito per applicare;
- non cancella run `running`, pinned o l'ultima failure salvo override esplicito;
- stampa esattamente directory e dimensione da eliminare;
- non segue symlink fuori root.

### 7.5 Criteri di accettazione

- nessun artefatto non ignorato dopo tutte le suite;
- ogni comando restituisce/mostra il proprio run-id;
- failure e interrupt lasciano un manifest leggibile;
- cleanup selettivo e testato contro path traversal/symlink;
- nessuna cancellazione implicita durante una diagnosi fallita;
- AGENTS documenta dove trovare i risultati.

## 8. Material 3: processo realmente usato

### 8.1 Difficoltà

La pagina M3 dei button group richiede JavaScript e non offre una specifica
completa e versionata in Markdown. Il testo indicava configurazioni e alcuni
valori, ma non bastava per implementare una matrice verificabile.

Le ricerche non ufficiali sono state usate soltanto per trovare nomi/path dei
token, non come contratto finale.

### 8.2 Fonti ufficiali consultate

Semantica e linee guida:

- <https://m3.material.io/components/button-groups/specs>
- <https://m3.material.io/components/button-groups/guidelines>

Documentazione Material Components Android:

- <https://github.com/material-components/material-components-android/blob/master/docs/components/ButtonGroup.md>

Token e stili generati:

- `material-components/material-components-android`
- `lib/java/com/google/android/material/button/res/values/tokens.xml`
- `lib/java/com/google/android/material/button/res/values/styles.xml`

Comportamento Compose:

- repository `androidx/androidx`;
- `compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/ButtonGroup.kt`.

Quando si ripete il processo, registrare commit SHA/tag, non soltanto `master` o
`androidx-main`.

### 8.3 Procedura seguita

1. Leggere overview/guidelines per separare standard e connected, selezione,
   shape e comportamento dei vicini.
2. Cercare i nomi completi dei token mostrati nella pagina M3.
3. Verificare i valori nel file XML generato ufficiale.
4. Verificare nel sorgente Compose come i token entrano nel layout e
   nell'interazione.
5. Confrontare documentazione Android e sorgente quando un valore sembra
   ambiguo.
6. Trascrivere i valori in token CSS del progetto.
7. Aggiungere test che asseriscano i valori e il comportamento, non soltanto lo
   screenshot.
8. Documentare esplicitamente ogni adattamento web.

Valori usati nel terzo giro:

| Token/comportamento | XS | S | M | L | XL |
|---|---:|---:|---:|---:|---:|
| altezza button | 32 | 40 | 56 | 96 | 136 |
| padding orizzontale | 12 | 16 | 24 | 48 | 64 |
| icona | 20 | 20 | 24 | 32 | 40 |
| gap standard group | 18 | 12 | 8 | 8 | 8 |

Altri valori:

- connected gap: 2dp;
- espansione del button premuto: 15%;
- compensazione sui vicini diretti nello standard group;
- connected group: shape morph senza ridistribuzione della larghezza;
- stiffness conservata nel progetto: 1400;
- damping conservato nel progetto: 0.9.

I dp sono mappati a CSS px. Questo è appropriato per la scala logica del web,
non una promessa di identità fisica fra browser e Android.

La stiffness/damping Android non ha una primitiva CSS portabile equivalente.
Il progetto conserva i token ma usa una transizione web documentata. Non
chiamarla “esatta” nei documenti o test.

### 8.4 Automazione proposta

Aggiungere un inventario versionato, per esempio:

```text
src/frontend/design-tokens/material3/button-groups.yaml
```

Campi minimi per token:

```yaml
name: md.comp.button-group.standard.xsmall.between-space
value: 18
unit: dp
source:
  repository: https://github.com/...
  revision: <sha>
  path: .../tokens.xml
  selector: m3_comp_...
retrieved_at: 2026-09-21
mapping:
  css: --button-group-gap-xs
  adaptation: dp-to-css-px
```

Comando CLI:

```bash
uv run harness material sync --component button-groups --revision <sha>
uv run harness material check
```

Requisiti:

- `sync` è il solo comando che usa la rete;
- `check` e pre-commit lavorano sui file committed, senza rete;
- output deterministico;
- aggiornamento mostra diff di sorgente e valori;
- token non trovati fanno fallire, non mantengono silenziosamente il vecchio
  valore;
- override/adattamenti web vivono in una sezione separata e motivata;
- generare CSS o un frammento importato e un test di corrispondenza;
- non aggiungere una dipendenza runtime frontend.

### 8.5 Criteri di accettazione

- ogni token M3 ha provenienza e revisione;
- aggiornamento ripetibile;
- CSS e inventario non divergono;
- nessuna fonte terza usata come autorità;
- adattamenti web espliciti;
- showcase e test comportamentali continuano a coprire la matrice.

## 9. Backlog ordinato in ticket

### T1 — Database test separati

Ambito: sezione 3 completa.

Done quando integration ed E2E fresh passano realmente in parallelo nello stesso
container PostgreSQL.

### T2 — Runner JinjaX + JavaScript

Ambito: infrastruttura minima e migrazione dei test di ButtonGroup come primo
vertical slice. Non migrare subito tutti gli E2E.

Done quando il componente reale viene renderizzato e testato con timer/rete
controllabili senza Docker.

### T3 — Artefatti centralizzati

Ambito: manifest, run directory e migrazione iniziale di screenshot/compare.
Replay e upload possono essere sottoticket successivi.

Done quando una suite completa non lascia file fuori dalle directory gestite.

### T4 — Confronto strutturale

Ambito: landmark, estrazione metriche, report; mantenere pixel diff.

Done quando almeno overview e character detail spiegano le differenze di layout
in termini strutturali su desktop e telefono.

### T5 — Provenienza token M3

Prima commit dell'inventario manuale con SHA; poi estrattore/sync in sottoticket.

Done quando `material check` verifica offline inventario, CSS e test.

### T6 — Helper browser → API

Aprire solo dopo aver raccolto tre duplicazioni reali. Prima produrre una breve
API proposal e approvarla.

### T7 — Valutazione scenari dichiarativi

Nessuna implementazione finché fixture/helper Playwright non risultano
insufficienti. Il possibile output del ticket è anche “non costruire”.

## 10. Definition of done per questi strumenti

Ogni ticket:

- non dipende dall'MCP;
- espone una CLI con `--help` utile;
- ha funzioni interne testabili senza shell reale dove possibile;
- funziona con Docker e Podman quando usa Compose;
- non stampa segreti;
- non modifica scratch/showcase durante test;
- preserva stato e artefatti su failure;
- documenta comandi e limiti;
- passa unit, integration rilevanti e pre-commit;
- viene completato e committato prima del ticket successivo.
