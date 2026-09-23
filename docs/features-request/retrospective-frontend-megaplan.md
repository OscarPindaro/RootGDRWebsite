# Retrospettiva — frontend megaplan (F1–F22)

Opinione mia (Devin) su come è andato il megaplan: cosa ha funzionato, cosa no,
quali harness mancano e cosa va reinstallato. Come l'altra retrospettiva, non è
un piano approvato: è materiale di discussione.

Numeri finali: 22 ticket, 23 commit, `main.css` da 2262 a 591 righe, unit 452 /
frontend 285 / integration 115 / e2e 64 con **0 fallimenti** (erano 3 all'inizio).

---

## 1. Cosa ha funzionato

**L'ordine dei ticket era la cosa più importante del piano.** F1 ha creato il
seam *prima* di migrare qualsiasi cosa: la guardia sull'ownership e l'hook che
pretende la dichiarazione degli asset hanno reso ogni ticket successivo un
lavoro locale. Se F3 fosse arrivato prima di F1 avrei spostato regole dentro un
sistema che nessuno stava ancora controllando.

**Delegare un ticket per subagente.** Il costo in contesto per ticket si è
ridotto a: brief + report + review del diff. È l'unico modo in cui sono arrivato
in fondo. Il brief che ha funzionato meglio conteneva: il testo del ticket, le
decisioni già prese dai ticket precedenti, le trappole che avevo già imparato, i
comandi di verifica e l'elenco preciso delle cose da riportare.

**La review indipendente non è opzionale.** Ogni ticket l'ho verificato io: diff,
suite, screenshot. Ha catturato, tra gli altri:

- F4 ha derivato l'`id` del campo da `name` → `id="email"` duplicato su `/login`
  e la label del dev-login che puntava all'input sbagliato;
- F14 ha reso `{{ tag }}` quando il tag è `None` → la stringa `NONE` visibile
  nella riga del registro;
- F17 (arrivato già scritto) rispondeva 303 a un login htmx riuscito, quindi il
  browser swappava solo `<body>` e la pagina di destinazione perdeva tutti gli
  asset di `<head>` (rail trasparente);
- il mio stesso file `test_legacy_selectors.py` ha sovrascritto una versione più
  ricca.

Nessuno di questi l'avrebbe visto un "compila e passa i test".

**Il gate di F12 ha funzionato esattamente come previsto.** Fermarsi a chiedere
l'approvazione visiva *prima* del rollout ha prodotto la correzione giusta
(griglie sì, registro/atlante no) nel momento in cui costava poco. Se avessi
rollato il componente e poi chiesto, avrei dovuto disfare sette pagine.

**Le harness esistenti, in ordine di valore per questo lavoro:**

1. `harness test frontend` — veri componenti JinjaX in Chromium. È la rete che ha
   retto tutto: geometria, contratti, stati. Economica e precisa.
2. Gli hook di pre-commit — l'ownership guard, `design_tokens`, `template_types`,
   l'hook delle dipendenze CSS. Hanno bloccato errori reali (per esempio E931 su
   `ConfirmDialog`: props non dichiarate su un componente reso da una route).
3. `harness compare` — anche solo come numero, per accorgersi di una regressione.
4. `harness test e2e` — lento ma è l'unico che vede il prodotto intero.
5. `harness material check` e `harness doctor` — silenziosi e affidabili.

---

## 2. Cosa non ha funzionato

**Gli screenshot catturati a metà animazione.** `harness screenshot --click`
scatta subito dopo il click. Il drawer del telefono è uscito come una striscia
nera tagliata e ho perso tempo a sospettare un bug che non c'era; la geometria
misurata nel browser diceva 268px, tutti gli item visibili, background `inert`.
Manca un'attesa di "assestamento".

**I landmark di `prototype_map.yaml` marciscono in silenzio.** `.grid--quick` è
rimasto mappato per settimane puntando a una classe che l'app non emette da
quando esiste `common.Grid`, e ha rotto un test e2e che nessuno collegava a
quella causa. La mappa è scritta a mano e nessuno verifica che i selettori
esistano davvero.

**`config.test.yaml` viene riscritto dall'harness a ogni `env up`/`teardown`.**
Ho dovuto ripristinarlo prima di ogni commit, due volte per ticket. L'harness
scrive già la configurazione attiva nella propria cache
(`config.test.*.local.yaml`), quindi la copia nel repo è ridondante.

**`harness test e2e` non accetta argomenti.** Ha solo `--fresh`. Per diagnosticare
un singolo test ho dovuto lanciare pytest a mano con `ENV_FILE` e
`YAML_CONFIG_FILE` presi dalla cache. È l'attrito più grosso che ho incontrato.

**`tests/frontend/conftest.py` non imposta `PLAYWRIGHT_BROWSERS_PATH`.** Passando
da `harness test frontend` funziona; lanciando pytest direttamente il browser
"non esiste". `harness/test/browser.py` lo fa già con `os.environ.setdefault`,
il conftest del frontend no.

**Due stack di sviluppo e hash ambigui.** `harness doctor` riportava 8021/8022
come porte dev, `harness dev status` diceva che il progetto di questo worktree
stava su 8001/8002. Ho fatto screenshot contro uno stack che non sapevo
attribuire. Il nome del progetto (`rootgdr_dev_199c30c944`) e il percorso del
worktree non compaiono mai insieme.

**`ruff` non è installato nel venv.** Gli hook lo eseguono (via
`ruff-pre-commit`), ma nessun subagente poteva lanciarlo. Risultato: circa otto
commit sono falliti con "files were modified by this hook", seguiti da restage e
nuovo tentativo. È un ciclo meccanico che si poteva evitare.

**`harness dev reset --db show` contro uno stack attivo risponde 500 alla prima
richiesta** (`InvalidCachedStatementError`: lo schema droppato invalida gli
statement preparati di asyncpg). L'ho documentato in `AGENTS.md`, ma è un
fallimento che sembra un bug dell'applicazione e non lo è.

**Il conteggio atteso di e2e cambiava a ogni ticket.** Il piano e il mio file dei
problemi dicevano "3 failed / 28 passed", poi "2 failed / 29 passed": ogni brief
doveva riportare il numero corrente, e un brief con il numero sbagliato avrebbe
fatto sembrare una regressione un fallimento noto. È una classe di errore che si
elimina con un registro leggibile dalla macchina.

**Il provider dei subagenti è caduto due volte**, alla fine. Non è un problema di
harness, ma è la ragione per cui F22 l'ho fatto a mano: vale la pena che il
processo regga anche senza delegati.

---

## 3. Harness che servirebbero

In ordine di rapporto valore/costo.

1. **`harness test <suite> -- <argomenti pytest>`** (o `-k`). Sblocca la
   diagnosi di un singolo test. È la modifica che pagherei per prima.
2. **Verifica che i landmark risolvano.** Un `harness compare --check-landmarks`
   o un test unitario che apre ogni pagina mappata e fallisce se un `app:` di
   `prototype_map.yaml` non esiste nel DOM. Avrebbe catturato la marcescenza di
   `.grid--quick` il giorno in cui è iniziata.
3. **Registro dei fallimenti noti.** Un file che il runner legge, così un test
   noto-rotto si riporta come "atteso" invece di far portare il conteggio a mano
   in ogni brief. Meglio ancora: `xfail` con motivazione e numero di ticket.
4. **`--settle <ms>` su `harness screenshot`**, o un'attesa automatica della fine
   di transizioni e animazioni prima dello scatto.
5. **Il budget dei payload come hook**, non solo come test unitario: F20 ha
   aggiunto `tests/unit/test_payload_budget.py`, ma una regressione di peso
   dovrebbe fallire al commit, non nel run dell'intera suite.
6. **`doctor` che dice per quale worktree sta parlando**, con il percorso e il
   nome del progetto, e un avviso quando le porte "attese" sono tenute da un
   altro worktree.
7. **Una scansione di accessibilità nel giro normale** — F21 ha aggiunto
   `tests/e2e/test_accessibility.py` con axe; le findings di contrasto sono la
   palette decisa, quindi conviene che siano un controllo a parte e non un
   fallimento da rilitigare a ogni run.

---

## 4. Cosa va reinstallato

**Niente delle harness esistenti va reinstallato.** Ho usato `doctor`, `dev`,
`env`, `test` (unit, frontend, integration, e2e), `compare`, `screenshot`,
`material`, `smoke`, `content`, `artifacts` e `browsers` senza mai dover
reinstallare nulla, e `.playwright-browsers/` era già a posto.

**Una cosa sì:** `npm install`. F21 ha aggiunto `axe-core` come devDependency per
la scansione di accessibilità, e `tests/e2e/test_accessibility.py` fallisce con
un messaggio esplicito se `node_modules/axe-core/axe.min.js` non c'è. `setup.sh`
non esegue `npm install`, quindi su un checkout esistente serve a mano:

```bash
npm install
```

Vale la pena aggiungerlo a `setup.sh`, oppure marcare quel test `skip` con una
motivazione quando axe manca, invece di farlo fallire.

**Due piccole cose da sistemare perché il prossimo non ci inciampi:**

- `tests/frontend/conftest.py` dovrebbe importare `harness.test.browser` (o fare
  `os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", …)`) come già fa il resto
  dell'harness;
- `ruff` come dev-dependency, così lint e format si possono eseguire prima del
  commit invece che dentro l'hook.

---

## 5. Cosa cambierei nel processo dei ticket

**Il brief è il collo di bottiglia.** La sua qualità decide quella del ticket. Le
tre cose che hanno fatto la differenza: dire *cosa non fare* (F5: "non sostituire
tutti gli `hx-confirm`"), elencare le trappole già note (l'ordine visivo contro
l'ordine del DOM in F7), e chiedere un report con voci fisse — così un ticket
incompleto si riconosce dalla forma del report prima che dal codice.

**Un ticket, un commit, sempre.** Non ho mai combinato due ticket, e questo ha
reso ogni regressione attribuibile a un commit solo. Il costo è stato qualche
minuto di restage per gli hook che riscrivono i file: accettabile.

**Fermarsi quando il ticket lo chiede.** F12 è l'esempio: la regola "stop al gate
visivo" ha funzionato. La stessa disciplina è servita in F22, dove ho preferito
*registrare* le findings di contrasto invece di cambiare la palette decisa.

**Verificare le affermazioni, non fidarsi.** I report dei subagenti erano accurati
ma non autosufficienti: ogni volta che ho controllato io ho trovato qualcosa
(un `NONE` visibile, un id duplicato, un test sovrascritto). La regola che terrei:
il report dice cosa è stato fatto, la suite e gli screenshot dicono se è vero.
