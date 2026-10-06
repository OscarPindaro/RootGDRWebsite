---
agent: devin-local
session: flourish-random
created: 2026-10-03T19:44:18Z
---
# Megaplan AFK — infrastruttura, harness e documenti

Realizzare per ticket verificabili il deployment manuale di Root GDR e Vikunja, il tooling di sviluppo e release, e tutte le richieste REQ-0002–REQ-0010, minimizzando gli interventi di Oscar durante l’esecuzione.

## Summary

Il ciclo comprende REQ-0001, le nove nuove richieste REQ-0002–REQ-0010, H1–H7 più setup Node/E2E, CLI Vikunja, convenzioni delle richieste e Towncrier. Il risultato deve essere utilizzabile sul serverino, verificato localmente e pubblicabile su `main`. Non assegna una nuova versione, non pubblica una release e non importa lo storico nella board.

Sono previsti **40 ticket iniziali più due follow-up di verifica**, oltre ai commit iniziali che preservano il lavoro già presente. Il vecchio REQ-0001/T01, relativo a GitHub App e policy PR, è rinviato per decisione dell’utente, non completato.

## 1. Decisioni e autorizzazioni della sessione

Queste decisioni prevalgono sulle formulazioni precedenti dei documenti; vanno registrate nelle specifiche all’inizio dell’implementazione.

| Tema | Decisione operativa |
|---|---|
| Git | Per ora niente GitHub App, PR obbligatorie o ruleset nuovi. Usare l’autenticazione Git esistente senza modificare configurazioni globali. Commit per ticket; push ordinario su `main` normalmente alla fine del ciclo. Mai force-push. |
| GitHub CLI | L’utente non autorizza letture autenticate di impostazioni/quote con `gh`. Non cercare token alternativi. La repository è pubblica, come confermato dall’utente. |
| CI | GitHub Actions su PR verso `main`, push su `main` e dispatch manuale. Runner Linux standard; tutte le suite pertinenti, nessun deploy da CI. Nessuna modifica a billing, visibilità, permessi o segreti GitHub. |
| Deployment | Build, verifiche e invocazione Ansible dal PC locale; trasferimento al server via SSH. Nessun registry, webhook, poller, runner production o aggiornamento automatico. |
| Bootstrap | Root GDR e Vikunja sul server sono la prima tranche bloccante. Il primo bootstrap è autorizzato dopo test locali verdi e collaudo disposable, prima della pubblicazione della nuova CI. Questa eccezione non autorizza a ignorare test/CI falliti in seguito. |
| Root GDR | Nuovo stack separato dal checkout remoto esistente, HTTP sulla LAN fidata, indirizzo IPv4 del server e porta 8001. Login reale; `cookie_secure: false` solo nel profilo LAN approvato, non `env: dev`. Oscar apre il firewall. |
| Vikunja | Nuova istanza server, SQLite e allegati separati; solo loopback e tunnel SSH dal PC. Nessuna migrazione delle demo locali. Kanboard resta intatto. |
| Identità | Oscar, `oscar.pindaro@gmail.com`. Rimuovere riferimenti Shopcircle dai file del progetto, inclusi metadati, configurazione e attribuzione corrente della licenza; conservare il testo MIT e il nome del titolare. Non riscrivere la storia Git. |
| Credenziali | Generare segreti dedicati e password iniziali in file privati/Vault, senza stamparli in chat, argv, log o Git. Non cambiare account/password esistenti. Nessun riuso dei segreti dei bot. |
| Dati iniziali | Solo nuovo account e bundle `seed/boschetto-di-smeraldo.yaml` sul nuovo Root GDR. Niente copia di showcase, scratch, vecchio checkout o dati privati. Il seed è una prima inizializzazione esplicita, non una sincronizzazione ad ogni deploy. |
| Backup | Pre-deploy obbligatorio; settimanale sul PC, domenica 10:00 Europe/Rome, sotto `~/.local/share/rootgdr/backups`. Ultime quattro copie settimanali complete; copie pre-deploy separate senza scadenza automatica. Archivi cifrati. |
| Retention | Eliminare soltanto copie settimanali prodotte dal sistema oltre le quattro conservate, dopo una nuova copia completa e verificata. Nessuna pulizia automatica di pre-deploy, immagini estranee, volumi, dati o artifact preesistenti. |
| Board | Vikunja autorevole per backlog e stato. Repository autorevole per specifiche, decisioni, esiti, manuali e release note. Importare solo i ticket reali di questo ciclo; censire lo storico senza importarlo o rinominarlo in massa. |
| Release | Towncrier con frammenti Markdown; versione autorevole in `pyproject.toml`. Nessun bump, tag, consumo dei frammenti o pubblicazione senza scelta successiva di Oscar. |
| Parallelismo | L’utente ha richiesto flessibilità e approvato la direzione a worktree separati. Massimo operativo proposto: tre subagenti, soltanto su ticket con dipendenze e isolamento verificati, dopo il bootstrap. Il coordinatore integra e verifica ogni risultato; i subagenti non operano sul server reale. |
| Interruzioni | Procedere con assunzioni conservative per i dettagli restanti, registrandole. Fermare il ramo interessato per permessi, autenticazione, dati reali, costo, distruzione o cambio di prodotto sostanziale; continuare i rami indipendenti. |

L’approvazione del piano autorizza implementazione e attivazioni nuove qui descritte. Un restore su dati vivi, una migrazione distruttiva, una pulizia estranea alla retention autorizzata o un cambio di sicurezza/billing richiedono sempre conferma specifica.

## 2. Baseline verificata e conseguenze tecniche

### Repository

- Branch locale `main`, HEAD osservato `d1f8a3f`; remote `origin` SSH su `OscarPindaro/RootGDRWebsite`.
- Modifiche preesistenti: `AGENTS.md`, indice dei manuali, Compose delle board, documenti dei tre filoni, nove richieste UI, screenshot originali, studio `prototypes/devin-prototype/feedback-2026-10-03/`, `tests/frontend/test_feedback_prototype.py` e test delle board. Sono lavoro dell’utente/sessioni precedenti: non sovrascriverli né includerli casualmente in ticket nuovi.
- Python >=3.14, Typer, Pydantic, httpx, PyYAML e Playwright già presenti nel tooling. Ruff non è nel gruppo dev; hook pin `v0.15.1`. Axe è già in `package-lock.json`, ma `setup.sh` non esegue `npm ci`.
- Nessun workflow GitHub presente. Dockerfile usa `COPY . .`; `.dockerignore` non esclude sufficientemente dati, browser, Node e artifact. Compose root è development.
- `AppConfig.migrator` è obbligatorio anche nel runtime. Consumatori rilevati: `alembic/env.py` e `src/cli/config/check.py`; il cambiamento va limitato a questi confini.
- `/ping` è solo liveness. Gli helper `harness smoke`/screenshot usano dev-login: non sono una prova production.
- I tre fallimenti E2E storici nel registro sono già dichiarati chiusi. Non assumere che siano ancora fallimenti attesi. Nessuna suite è stata eseguita durante questa pianificazione in sola lettura.

### Server osservato via SSH, senza modifiche

- Target esistente: `pinball@pinball-server.local`, Fedora Linux 43 **Server Edition**, x86-64.
- Podman 5.8.4 rootless; lingering già `yes`; SELinux Enforcing; timezone Europe/Rome.
- Nessun provider Compose installato. Python 3.14 e rsync disponibili.
- Bot e WebDAV attivi: preservare servizi, volumi, immagini e porte. Nessun container Root GDR osservato, ma esiste `/home/pinball/RootGDRWebsite` con HEAD `f02f1d7` e un file non tracciato: non usarlo come destinazione del rollout.
- Filesystem `/` di 15 GB, circa 6,4 GB liberi al momento del sopralluogo. `/home` e graphroot Podman insistono sullo stesso filesystem. È un rischio da verificare con dimensioni reali degli artifact, non una capacità garantita.
- IPv4 LAN osservato: `192.168.1.201/24`. Firewalld usa `FedoraServer`; le letture di servizi/porte sono negate a pinball. Non tentare escalation automatica. L’apertura della porta 8001 da `192.168.1.0/24` è un’azione dell’utente.

### Harness

- `commands/test.py` chiama `runner.run(suite)` senza argomenti. Il runner ha `PytestOptions` e selettori validati, ma aggiunge sempre `tests/unit`/`tests/frontend`: un selettore non restringe davvero quelle suite.
- `commands/compare.py` misura i landmark in navigazioni separate; `MEASURE_JS` usa `querySelector`, quindi non rileva ambiguità. Le differenze sono stringhe diagnostiche, non un gate strutturale.
- Screenshot e misure usano Pixel 7 per phone; i nuovi regressioni e i controlli richiesti devono includere anche 390×844 esplicito, mantenendo coerenti i due lati di ogni confronto.
- `harness browsers` forza la posizione repository anche con override e salta l’installazione se esiste la directory: non prova che la revisione Chromium richiesta sia disponibile.

### Documenti UI

- Field: il fieldset/legend può spostare la rule visibile rispetto al box. Gli assert esistenti tollerano un intervallo largo; serve misurare la rule effettiva, non solo `top: 0`.
- SaveIndicator: testo in fondo alla banda di padding e pseudo-elemento centrato sull’intera banda. Conservare l’overlay senza spostare la toolbar.
- DocEdit: il blocco vuoto è focusabile, ma senza invito o geometria utile; `mountDocEdit` già espone `docOpen`/`docStopOpen`.
- Autosave: `flush()` ritorna subito quando c’è una richiesta in volo; `flushAll()` è fire-and-forget. Pubblicazione e navigazione possono precedere la persistenza.
- Metadata: un controller per URL API è già condiviso con corpo/identità; riusarlo anche nei pannelli, senza una seconda architettura di salvataggio.
- Slug: il successo del PATCH chiama `location.replace` prima di completare la gestione delle dirty fields. REQ-0010 deve preservare editor/caret e accodamenti.
- Dialog: il listener `htmx:afterSwap` apre tutti i dialoghi trovati. Un pannello dettagli pre-renderizzato necessita di opt-out esplicito, senza cambiare il comportamento delle conferme caricate dinamicamente.
- Menzioni: la route in `content/actions.py` filtra il world, non le bozze come le liste. Il payload non porta animal/shape. La dipendenza CodeMirror installata offre `icons: false` e `addToOptions` per il rendering, quindi non serve una libreria nuova.
- Storie: `_resolve_sessions` controlla il world, non la visibilità delle bozze; `StoryResponse` non espone le sessioni. La selezione e il riepilogo devono avere prove persistite e non esporre dati inaccessibili.

## 3. Assunzioni UI adottate per non interrompere l’AFK

Queste scelte completano le domande lasciate aperte dalle specifiche; non autorizzano redesign più ampi.

1. **REQ-0005:** comandi icon-only, con label/tooltip italiani; menu secondario etichettato per le azioni distruttive. Ownership resta dov’è. Badge editoriali rettangolari con testo: pubblicato carta/verde bosco, bozza carta/ocra e inchiostro leggibile. Non cambiare tutti i `common.Pill` né la palette globale.
2. **REQ-0006:** F2 apre il blocco focalizzato, altrimenti il corpo editabile; Ctrl/Command+Shift+Enter invoca il comando di pubblicazione corrente. Sono inattivi dentro input, textarea, contenteditable, CodeMirror, autocomplete e dialoghi. Nessuna scorciatoia diretta per delete o lock nella prima versione. Preservare Enter/F2 sui blocchi, frecce native e Mod+Enter dell’editor.
3. **REQ-0007:** oggi è la data calendario locale del browser, inviata alla creazione interattiva in ISO date, senza conversione UTC. Fallback esplicito Europe/Rome per richieste interattive prive del valore. API di creazione ordinaria e import non ricevono nuovi default. Calendario atlas desktop e nativo su phone, con fallback nativo se JS non è disponibile; nessuna preferenza timezone persistita.
4. **REQ-0008:** trigger compatto swatch+nome che apre una palette rettangolare; dodici token esistenti. Riutilizzare ChoiceGrid/radio e i primitivi popup, senza montare ImageEditor sui documenti senza immagine.
5. **REQ-0009:** mark rettangolare ricco: animal esistente per character/NPC, shape esistente per place, cue del tipo come fallback. Nessuna nuova tassonomia race, thumbnail o icon runtime globale.
6. **REQ-0010:** direzione C confermata: riepilogo compatto e dettagli laterali desktop/full-screen phone, costruiti su `common.Dialog`. Stories e pages soltanto; title/summary/body restano sul documento. La banda progress duplicata nella StoryDetail viene ridotta, non rimossa dalle altre superfici che la usano. Stato wire esistente resta invariato.
7. Sessioni collegate: lista di checkbox native con ricerca, selezioni mantenute anche se filtrate; modifiche attraverso il controller autosave esistente. Nessun nuovo pulsante Salva per l’intero pannello; il mock `Applica selezione` non diventa un requisito di persistenza.
8. Browser automatico di riferimento: Chromium desktop, 390×844 e Pixel 7. Non dichiarare test su Safari/Firefox o su telefono fisico se non eseguiti. Il picker nativo OS non viene falsamente “skinnato”.

## 4. Architettura e confini

### Ambienti

Mantenere separati `test`, `work`, `showcase`, target disposable di deployment, production Root GDR, production Vikunja e demo locali.

- Root production: progetto Compose `rootgdr-production`, base `/home/pinball/rootgdr-production`; PostgreSQL e uploads persistenti propri. DB non pubblicato sulla LAN. Runtime senza sorgenti montate e reload.
- Vikunja production: progetto `rootgdr-vikunja`, base `/home/pinball/rootgdr-vikunja`; SQLite, allegati e signing secret propri, versione 2.6.0 iniziale verificata. Non riusare `rootgdr-task-boards_*`.
- Listener Root soltanto IPv4 LAN configurato; niente wildcard IPv6, Internet o cambi router. Vikunja su `127.0.0.1:3456`; tunnel locale su una porta distinta dalla demo, proposta 3458.
- Provider Compose installato nella venv dedicata dell’utente pinball, versione fissata e pubblicata da almeno sette giorni; nessun sudo o cambio del Python di sistema. systemd user richiama il percorso esplicito.
- Inventario/esempi e ruoli in `deploy/`; dati privati del coordinatore sotto `~/.config/devin/rootgdr/` e mai nel repository. Le unit systemd applicative mantengono la loro posizione nativa, non sono configurazione di un altro agente.

### Deployment e backup

Ansible resta il proprietario dell’orchestrazione. Una CLI `harness deploy` può fornire preflight, build/status/verify e invocare playbook con argv, senza duplicare in Python la sequenza di rollout.

Ruoli previsti: `image_transfer`, `rootgdr_application`, `vikunja`. Non un ruolo per ogni task. Il controller costruisce il commit selezionato, il server carica le immagini; nessuna dipendenza dai checkout dei bot.

Sequenza di un rollout Root:

1. Verifiche del commit e del manifest, configurazione, spazio, target e segnale test/CI prima del downtime.
2. Lock per applicazione, valido anche contro backup periodici; lock atomico con ID del run, cleanup solo se posseduto da quel run. Un lock stale non viene rimosso automaticamente.
3. Se image ID, configurazione e generazione dei segreti sono già quelli attivi e healthy: no-op, senza restart, backup o migration inutili.
4. Salvare il riferimento alla precedente immagine/configurazione e fermare tutti i writer dell’applicazione. Attendere arresto completo; l’app è attualmente l’unico writer individuato, ma riesaminare eventuali nuovi worker.
5. Dump PostgreSQL logico custom-format e copia coordinata uploads; manifest con checksum, build, schema, configurazione e informazioni necessarie a ricreare ruoli/grant. Copia cifrata verificata sul controller prima delle migrazioni.
6. Migrazione one-shot con credenziali DDL separate, avvio runtime con sole DML, readiness e autenticazione reale.
7. Aggiornare atomicamente il manifest corrente soltanto dopo successo.
8. Su fallimento: tentare una sola volta rollback dell’immagine/configurazione se la compatibilità schema è comprovata. Default conservativo: stessa revisione Alembic. Se schema diverso senza prova di compatibilità, restare fermi e registrare recovery; niente downgrade/restore automatico.

Per Vikunja, fermare il writer prima del backup coordinato di SQLite/allegati/configurazione/secret. Usare SQLite backup API o dump upstream collaudato, non copia di un `.db` vivo. Un cambio immagine che ha migrato lo schema non autorizza rollback del database.

Proposta cifratura: `age` fissato, chiave dedicata generata sul PC in storage privato, installazione locale user-scoped verificata; nessuna chiave privata sul server. Le copie plaintext di staging sono mode 0600 in directory 0700 e vengono rimosse solo se create da quel run. Se questo install non è disponibile senza privilegi, predisporre la procedura e lasciare il gate esplicito, senza pubblicare copie non cifrate.

### Backlog e release

- Conservare REQ-0001–REQ-0010. Prima dell’implementazione riesaminare gli ID appena creati dall’utente.
- Riservare **REQ-0011** per il documento harness esistente e **REQ-0012** per board/workflow/release, se ancora liberi. Per l’harness si può mantenere il filename legacy con frontmatter numerico, evitando rename/link churn. Nuove richieste hanno filename numerico.
- Frontmatter minimo: `id`, `requested_on`, `title`; niente stato corrente. Date storiche ignote distinguono prima registrazione/importazione da data richiesta.
- Identità dei ticket: `REQ-nnnn/Tnn`, con alias H1–H7 e riferimenti F1–F22 conservati. Numeri non implicano ordine o versione.
- `harness tickets` con client httpx/Pydantic su **API v2** della 2.6.0, verificata sull’istanza locale. Token dedicato in file privato, permessi minimi e utente con accesso solo al progetto reale.
- CRUD richiesto: list/show/create/move/close/comment; niente delete, sincronizzazione bidirezionale o integrazione Kanboard. Profilo, project/view e bucket ID espliciti, mai ID demo hardcoded.
- Chiave stabile del ticket nel prefisso del titolo e riferimento alla specifica; import scansisce tutte le pagine API. Duplicati sono errore, non fuzzy matching. Create/mutation non vengono ritentati alla cieca dopo timeout.
- Reimport aggiunge soltanto ticket mancanti. Non modifica stato, scadenze, owner, relazioni o testo editato dall’utente. Eventuale aggiornamento della sola specifica è un comando esplicito/dry-run.
- Chiudere un ticket solo dopo test, review e prove visuali; commento finale con esito, commit, verifiche, limiti e manuale. Gli stati transitori dei ticket bootstrap completati prima della CLI si ricostruiscono solo dalle prove del ciclo, non dalle demo.
- Towncrier in dev, versione proposta `26.9.0` (release 2026-09-04), `changelog.d/` e `CHANGELOG.md`. Nomi tipo `REQ-0002-T01.fixed.md`, categorie added/changed/fixed/security/upgrade; riferimenti testuali REQ, non falsi GitHub issue ID.
- Una nota per cambiamento significativo, non per commit. Esclusioni interne motivate negli esiti. `draft` non cambia versioni né rimuove frammenti. La build reale di release resta un’operazione futura con versione scelta e cancellazione frammenti autorizzata.
- `pyproject.toml` resta 0.1.0 durante il ciclo. Eliminare il contatore applicativo indipendente da package.json, che è private; esporre versione/build nel backend e nei label/manifest delle immagini, senza obbligo di nuovo chrome UI.

### Frontend

Riutilizzare JinjaX, htmx, CodeMirror, ChoiceGrid, IconButton, Menu e Dialog. I componenti nuovi giustificati sono DatePicker, TintPicker, DocDetails e SessionPicker; ciascuno con asset colocati, test e specimen. La barra documenti e l’autosave restano condivisi.

Non rifattorizzare tutta `editor/index.js`: modificare le sezioni necessarie; estrarre soltanto logica realmente riusata. L’unico bundle generato `static/js/editor.js` va rigenerato da sorgenti dopo ogni integrazione che lo tocca. Nessuna seconda persistenza, nessun renderer del mock, nessun framework client-side, nessuna migrazione DB prevista per queste UI.

## 5. Preparazione e Definition of Done

### Prima dei nuovi ticket

1. Rileggere stato/diff perché le nuove richieste e il prototipo sono stati creati contemporaneamente a questa pianificazione. Attendere che i file siano stabili, senza sovrascrivere la sessione precedente.
2. Review dei file già presenti e test board/prototipo, poi commit distinti per baseline board/processo e baseline feedback/prototipo. Correggere solo eventuali difetti dimostrati di questi artifact; non eliminarli per ottenere verde.
3. Registrare nelle specifiche le nuove decisioni Git/LAN/backup/AFK, e riservare ID nuovi senza collisioni. Non mettere una tabella manuale di stato corrente nel repo.
4. Eseguire la baseline unit/frontend/integration/E2E e registrare comandi, revisione, esiti e artifact. Gli ambienti test vanno creati e smontati esclusivamente attraverso la harness. Non toccare showcase.

### Per ogni ticket

- Riprodurre prima i bug; aggiungere una regressione fallente quando possibile, poi fix e nuova verifica.
- Cambiamento minimo, convenzioni esistenti, attributi espliciti e Pydantic ai confini; conservare i commenti esistenti.
- Test pertinenti verdi, nessun nuovo skip/xfail, nessun aumento delle soglie o indebolimento dei controlli per passare.
- Ogni browser write verificato da GET API o query integration dopo il commit della transazione; includere reload. Test con fixture rollback non provano una persistenza di produzione.
- Screenshot desktop e phone confrontati con il prototipo appropriato. Per ticket non visuali: screenshot di regressione Root GDR, senza fingere che CLI/Ansible abbiano un prototipo UI; per Vikunja aggiungere le proprie prove funzionali.
- Aggiornare il manuale tematico pertinente e un frammento significativo o l’esclusione motivata; esito conciso sulla board.
- Review del diff, hook attivi, un commit per ticket completato, prima di avviare un dipendente.
- Screenshot di evidenza fuori dall’area non leggibile, ad esempio output-dir dedicata in `/tmp`; nessun percorso `/tmp` come dipendenza persistente del prodotto o dei test.

## 6. Ticket infrastruttura e bootstrap — prima tranche bloccante

### REQ-0001/T00 — Identità personale e riferimenti correnti

**File:** `pyproject.toml`, `config.yaml`, `LICENSE`; audit mirato dei file del progetto e nuove configurazioni.

Sostituire email autore/bootstrap con `oscar.pindaro@gmail.com`, rimuovere `@ShopCircle` dall’attribuzione corrente mantenendo Oscar e MIT. Non modificare Git config, commit passati o account DB esistenti. Verificare che riferimenti residui non arrivino da cache/dependency o dati privati esclusi.

**Verifica:** config tests, validazione TOML/YAML, ricerca case-insensitive sui file di progetto, test applicabili e screenshot login/worlds. **Dipendenze:** baseline.

### REQ-0001/T03 — Packaging production e separazione delle credenziali

**File:** `Dockerfile`, `.dockerignore`, `deploy/production.compose.yaml` nuovo; `src/backend/config.py`, `src/cli/config/check.py`, `alembic/env.py`, test config e nuovi test packaging.

1. Runtime capace di avviarsi con `migrator=None`; Alembic fallisce chiaramente se manca il migratore, senza fallback al runtime. Le configurazioni development/test che forniscono migrator restano compatibili.
2. Build da commit scelto con contesto curato e lockfile frozen. COPY espliciti per sorgenti/assets e Alembic; esclusione di `.env*`, dati, browser, Node, artifact, private config, test e prototipi dal contesto production.
3. UID/GID runtime stabili, uploads persistenti con ownership corretta; niente browser tooling necessario al runtime, reload o source mounts production. Non rompere i compose di test/dev.
4. Env/runtime config separati da migrazione e bootstrap DB; nell’app non entrano password migrator/superuser. Mantenere i due ruoli e nessun `create_all` di startup.
5. Label/tag per SHA completo, immagine precedente preservata; verificare architettura e image ID. Spegnere SQL echo in production se può divulgare dati auth; nessun debug di env/config segreti.

**Verifica:** immagine reale da commit, sentinel privato escluso da contesto/layer, avvio senza migrator, migrazioni con DDL-role, rifiuto DDL con runtime, uploads dopo recreation. **Dipendenze:** T00.

### REQ-0001/T05 — Readiness e smoke production reale

**File:** `src/backend/health/` nuovo, `server.py`, configurazione build/version; confini auth/router se necessari; test integration/production smoke e `src/harness/deploy/` per il verifier.

Liveness `/ping` resta compatibile. Readiness controlla DB, schema Alembic atteso e scrittura storage tramite un file effimero proprio, con timeout e risposta pubblica minima 503 su dipendenza non pronta. Non esporre DSN, percorsi privati o trace. Runtime production non registra endpoint dev-login/form, showcase e content dev; replay è off.

Verifier usa password login reale, cookie/token mantenuti solo in memoria, lettura autenticata di worlds/documento e immagine nota; non usa helper dev-login. Verificare anche refresh/logout nella regressione production. È stato rilevato nel sorgente `int(payload['sub'])` per refresh mentre i token usano UUID: riprodurre prima e, se blocca il flusso, correggere localmente la conversione con test, senza rifare l’autenticazione.

**Verifica:** DB indisponibile, schema errato, storage non scrivibile, token scaduto/invalidità e percorsi dev assenti in una app costruita davvero in env production. **Dipendenze:** T03.

### REQ-0001/T04 — Backup coordinato e restore isolato

**File:** `deploy/backup.yaml`, `deploy/restore.yaml`, task backup/restore dei ruoli applicativi, modelli/utility backup sotto `src/harness/deploy/`, test di recovery.

Manifest tipizzato, checksum e archivio DB/uploads/config/segreti necessari; writer arrestati durante il capture. Ruoli/grant riproducibili, nessuna copia live dei file PostgreSQL. Supporto separato a snapshot SQLite/allegati Vikunja senza dipendere dalle demo. Cifratura e verifica della copia sul PC prima delle migrazioni; se capture/trasferimento/cifratura falliscono, abort.

Restore rifiuta target production/default e storage non vuoto. Solo namespace disposable esplicito; verificare account, contenuto, upload, autorizzazioni, revisioni e grants. Il playbook restore non viene mai richiamato dal rescue del deploy.

**Verifica:** recupero reale DB+file+permessi, backup corrotto/incompleto, upload scritto vicino al capture, errore dump, errore cifratura/transfer, restart dello stesso build prima della migrazione. **Dipendenze:** T03/T05.

### REQ-0001/T06 — Ansible manuale, idempotenza e rollback sicuro

**File:** `deploy/deploy.yaml`, `deploy/ansible.cfg`, esempi inventory/vars, ruoli `image_transfer` e `rootgdr_application`, template env/config/systemd; `commands/deploy.py` e `src/harness/deploy/` solo per facciata/verifica, registrazione CLI.

Usare i bot come riferimento, senza modificarli o dipenderne a runtime. Installare il provider Compose user-scoped, gestire systemd user, lock e preflight spazio. Trasferire image archive save/copy/load con cleanup `always` solo dei temporanei creati. Vault/no_log/diff off su task segreti. Implementare l’intera sequenza descritta in §4.

Preflight capacità misura archivio, immagini correnti/precedenti, dump e uploads, considerando che home e Podman condividono `/`; lascia un margine operativo. Se non basta, stop: niente prune globale o cancellazione di vecchie immagini estranee. Reapply invariato deve essere no-op. Rollback applicativo una volta sola, solo con compatibilità provata; primo deploy fallito senza predecessor resta fermo.

**Verifica:** syntax, check mode non mutante e senza build, due applicazioni uguali, cambio config/build, lock concorrente, migrazione fallita, backup fallito, readiness fallita con schema uguale/diverso e rollback fallito. Target disposable isolato gestito dalla harness, non avvio Uvicorn manuale. **Dipendenze:** T03/T04/T05.

### REQ-0012/T01 — Vikunja production separata sul server

**File:** `deploy/vikunja.compose.yaml`, ruolo `vikunja`, template config/systemd; estendere test board/deploy senza cambiare il Compose delle prove locali.

Pinned 2.6.0, loopback-only, volumi/config/secret isolati. Bootstrap account Oscar e account tooling limitato al progetto reale; disabilitare registrazione pubblica, mail e link sharing. Se per il primo account occorre una fase registration, mantenerla solo su loopback e richiuderla anche su fallimento; preferire un percorso upstream verificato che non esponga password in argv. Token API v2 con scope minimo, non login Oscar riusato ad ogni comando.

Backup SQLite consistente e ripristino disposable; riavvio/systemd e reapply preservano dati e account. Non usare ID/progetti demo; niente Kanboard sul server in questo ciclo.

**Verifica:** info/version/API v2, login reale, restart, privacy project, listener e storage, backup/restore, sintassi/check mode. **Dipendenze:** T04/T06.

### REQ-0001/T07 — Attivazione reale dei due nuovi stack

**File:** inventory/config private, nuovi manifest di deployment; aggiornare i manuali pertinenti.

Eseguire il primo rollout di commit puliti verificati verso le nuove directory. Creare segreti/account idempotentemente, mai resettare account trovati; seed Root del solo bundle di riferimento tramite i servizi esistenti e una transazione esplicita. Non aggiungere PyYAML/Typer al runtime solo per richiamare la CLI dev: usare conversione bundle sul controller e il service layer nel processo controllato, oppure un entrypoint backend minimale e testato.

Aprire tunnel Vikunja distinto dalla demo locale. Verificare Root via LAN dopo l’apertura firewall di Oscar; se non è ancora aperta, verificare temporaneamente via tunnel e lasciare l’accesso phone come gate pendente, senza bloccare gli altri ticket. Nessun riavvio server o servizi bot.

**Verifica:** login reale, worlds/reference, file e persistenza dopo service restart, readiness/version/schema, board utilizzabile, desktop/phone screenshot Root e Vikunja. Annotare esattamente il build iniziale. **Dipendenze:** T06, REQ-0012/T01; eccezione bootstrap CI già autorizzata.

## 7. Ticket board, storico, release e backup periodici

### REQ-0012/T02 — Metadati, ID e censimento storico

**File:** richieste attuali, documento planning storico, `AGENTS.md`, workflow esistente; modelli/validator sotto `src/harness/tickets/` e test unit.

Riservare 0011/0012 solo dopo nuova scansione; schema minimo frontmatter, ID univoci, link relativi validi e ticket/alias validati. Applicare metadati ai nuovi documenti del ciclo; inventariare legacy, evidenza delle date e collegamenti Git senza rinomina/import massivi. Nessun campo current status nel repo. Registrare App/PR rinviate e assunzioni UI della sessione.

**Verifica:** duplicate ID, metadata invalida, link mancante, alias H/F, data ignota e repo senza accesso alla board. **Dipendenze:** baseline; operativamente dopo bootstrap.

### REQ-0012/T03 — Client API v2, lettura e creazione ticket

**File:** `src/harness/tickets/{schemas.py,client.py}`, `commands/tickets.py`, `cli.py`, test unit e integrazione board disposable.

Client httpx con modelli Pydantic per config, project/view/bucket/task, paginazione, errori e esiti. Token letto da file privato o env esplicita, mai argv/output. `list/show/create` con output umano e JSON; timeout finiti, paginazione completa e limite di progetto. Nessun backend model/API Root GDR per il backlog.

**Verifica:** API 2.6.0 reale isolata, pagination > una pagina, 401/403/404/422, token assente/scaduto, timeout e redazione, nessuna mutazione su errore di profilo. **Dipendenze:** T01/T02.

### REQ-0012/T04 — Spostamento, chiusura e commenti di esito

**File:** stessi moduli client/commands, modelli mutation, test board.

`move` usa project/view/bucket corretti; `close` e bucket conclusa restano coerenti con il done bucket di Vikunja. PATCH minimi, precondizioni/ETag dove supportati dalla release; non riscrivere rich text quando non necessario. Esiti/commenti idempotenti con ID del ticket/run; nessun delete. Su un timeout dopo una write rileggere prima di ritentare.

**Verifica:** spostamento reale, done/reopen, view errata, permesso read-only, retry dopo esito ambiguo e nessun duplicato/commento perso. **Dipendenze:** T03.

### REQ-0012/T05 — Importazione dei soli ticket nuovi

**File:** loader delle specifiche, comando import/dry-run, test; riferimenti stabili nelle richieste.

Creare il progetto reale separato con workflow semplice: Backlog/In corso/Review/Conclusi, default e done bucket espliciti; blocked/deferred indicati senza fingere completamento. Importare i 40 ticket del piano, escluso T01 App rinviato dall’esecuzione (può restare card deferred con motivazione), e nessuna demo/storia passata. Secondo import non duplica né cambia avanzamento manuale. Registrare esiti provati dei bootstrap già svolti.

**Verifica:** dry-run senza write, due import, duplicati preesistenti, più pagine, modifiche manuali preservate, specifiche collegate e API read-back. **Dipendenze:** T02/T03/T04.

### REQ-0012/T06 — Towncrier e autorità della versione

**File:** `pyproject.toml`, `uv.lock`, `package.json`/lock quando necessario, `changelog.d/`, `CHANGELOG.md`, validator frammenti e backend build/version metadata.

Aggiungere Towncrier via package manager, pinned e solo dev. Config Markdown, tipi e pattern REQ, draft esplicito con versione placeholder non pubblicata; nome progetto/versione unici. Rimuovere il contatore separato npm senza bump. Backend, manifest e label mostrano version/SHA, Alembic resta separata. Frammenti per cambiamenti significativi, nessuna obbligazione “un frammento per commit”. Non chiamare build consumante sul repository.

**Verifica:** draft lascia invariati frammenti, changelog e versioni; aggregazione e filename invalido su fixture temporanea; wheel/runtime version coherence. **Dipendenze:** T02 e T03 per build info. Serializzare pyproject/lock rispetto a H7.

### REQ-0001/T08 — Backup settimanale dal PC e retention

**File:** `deploy/backup.yaml`, template unit/timer systemd user locale, `harness deploy backup/status`, test retention e manuale deployment.

Domenica 10:00 Europe/Rome, timer Persistent; invoca solo backup, mai deploy. Due applicazioni con snapshot e manifest distinti; checksum/cifratura e archiviazione off-server prima di marcare success. Conservare quattro complete settimanali per applicazione e tutti i pre-deploy separati. Prune ristretto a manifest propri, mai symlink/path escape o incomplete che sostituiscano l’ultima copia valida.

PC spento, server irraggiungibile o credenziali non disponibili possono ritardare la copia: esporre last success/last failure/overdue (oltre un intervallo settimanale più margine dichiarato), journal e comando retry; non promettere RPO di sette giorni se il PC resta offline. Backup automatizzato deve avere accesso non interattivo ai propri segreti, senza dipendere da prompt Vault.

**Verifica:** selezione retention su fixture, fallimento nuova copia non cancella vecchie, pre-deploy esclusi, timer/config e una esecuzione reale più restore disposable. **Dipendenze:** T04/T07.

## 8. Ticket harness — REQ-0011, alias H1–H7

### T01 / H1 — Argomenti pytest dalla CLI

**File:** `commands/test.py`, `test/runner.py`, test command/runner nuovi e test environment esistenti.

Passare token dopo `--` per tutte le quattro suite; harness options prima del separatore. Riusare PytestOptions e validazione, non shell/shlex ricostruite. Un path/node ID esplicito sostituisce il target di default; senza argomenti il comportamento resta invariato. Interpretare correttamente valori di opzioni, incluso un `-k` quotato; suite boundary e configurazione harness non possono essere aggirati da selector/override. Errori di parsing e pytest propagano exit status. Mantenere API MCP tipizzata compatibile.

**Verifica:** `-k`, node IDs, due selector, `-x`, traceback/verbosity, path traversal/symlink, cross-suite, unknown/invalid args e codici 1/2/5; fresh soltanto E2E. Prima priorità dei ticket harness.

### T02 / H2 — Gate landmark strutturali

**File:** `test/landmarks.py`, `commands/compare.py`, `test/compare.py`, `seed/prototype_map.yaml`, test unit e browser reali.

Aggiungere `compare --check-landmarks`, separato da `--fail-on-diff`. Misure tipizzate includono numero match e stato visible/hidden, con requisiti viewport espliciti. Report route/viewport/landmark/side/selector per missing e ambiguous; geometria/pixel restano diagnostica. Non fallire perché una rail phone prevista chiusa è offscreen. Preferire misure delle stesse pagine/stati dello screenshot; se restano navigazioni separate, identiche interazioni/readiness e nessuna write nel frattempo.

**Verifica:** DOM reale con selettore stale e ambiguo, corretto, landmark opzionale/nascosto phone, desktop e 390×844, artifact failed coerente con exit status. **Dipendenze:** H4/H6.

### T03 / H3 — Registro piccoli fallimenti noti

**File:** `docs/features-request/problems/pre-existing-e2e-failures.md` e eventuali note problema pertinenti; nessuna eccezione del runner.

Formato con test preciso, sintomo, riproduzione, data, revisione/evidenza antecedente, ticket e chiusura. Conservare come chiusi i tre problemi già chiusi salvo nuova riproduzione distinta. Nessun totale memorizzato, skip, xfail o verde artificiale. Aggiungere soltanto problemi realmente osservati nella baseline.

**Verifica:** seguire la riproduzione di ogni voce nuova e confrontare l’evidenza; l’eventuale test noto continua a fallire. **Dipendenze:** baseline corrente.

### T04 / H4 — Settling bounded di screenshot e misure

**File:** `test/browser.py`, `commands/screenshot.py`, `commands/compare.py`, tests screenshot/browser.

Helper condiviso di attesa font/layout e transizioni/animazioni finite rilevanti, con deadline globale. Nessun networkidle illimitato, sleep lungo indiscriminato o reduced motion forzato. Override `--settle` in millisecondi limitato per casi eccezionali, e diagnostica di timeout. Riutilizzo su capture_url, capture_screenshots e misure compare. Esporre profilo phone 390×844 per le prove richieste, mantenendo Pixel 7 e stessa geometria sui due lati.

**Verifica:** drawer e dialog con transizione ritardata sono completamente aperti; no-action rapido, font lento, animazione perpetua, request stalled e console error. Preserve manifest e flag expected-status. **Dipendenze:** H6.

### T05 / H5 — Payload budget in pre-commit

**File:** `.pre-commit-config.yaml`, `tests/unit/test_payload_budget.py`, test del trigger hook se necessari.

Hook locale invoca lo stesso test budget, senza seconda registry di soglie: trigger su asset rilevanti, editor sorgente/bundle, icon registry/build inputs e definizione budget. Pass filenames false; unrelated commit skip. Usare uv frozen/no-sync coerente con setup e ambiente già sincronizzato. Fixture oversized verifica messaggio label/misura/limite. Non promettere browser transfer completo o asset colocati già fuori dal budget esistente.

**Verifica:** offline, CSS/editor/font/icon oversized, gzip, commit unrelated e config hook. **Dipendenze:** H7 consigliato.

### T06 / H6 — Browser runtime coerente

**File:** `src/harness/browser_runtime.py` nuovo e leggero, `test/browser.py`, `commands/browsers.py`, `tests/frontend/conftest.py`, `setup.sh`, browser tests.

Default repository-local prima dell’avvio Playwright, override esplicito preservato anche dall’installer (inclusi valori speciali supportati). Installazione verifica revisione/binary richiesti, non sola directory; errore di librerie OS distinto da browser mancante. Setup usa harness browsers, non playwright install diretto. Opzione esplicita dipendenze OS per runner CI, senza installazioni privilegiate automatiche sul desktop Fedora.

**Verifica:** harness e pytest frontend diretti dopo una sola installazione; override e revisione vecchia, nessuna reinstallazione harness/MCP; cwd diverso con config/env test assoluti ma senza prefisso PLAYWRIGHT_BROWSERS_PATH.

### T07 / H7 — Ruff nello sviluppo

**File:** `pyproject.toml`, `uv.lock`; hook solo se versione riletta differente.

`uv add --dev ruff==0.15.1` se il pin è ancora quello; nessun update coordinato non necessario, production dependency o format massivo. Hook attivi.

**Verifica:** fresh sync dev, ruff check/format check, stessi risultati del hook su fixture. **Dipendenze:** baseline; esclusione lockfile condiviso con Towncrier.

### T08 — Setup Node/axe con lockfile

**File:** `setup.sh`, test setup/asset existing, manuali harness/component tests.

Con `--harness` installare `npm ci` dal lockfile e Chromium dal comando supportato. Risolvere root script correttamente se invocato da altro cwd. Non saltare accessibility se manca axe, non aggiungere nuove dipendenze npm o reinstallare configurazioni MCP per risolvere browser/axe. CI esegue dependency setup esplicito, non installer agente globale.

**Verifica:** clean setup simile CI, axe locale presente, browser coerente, nessun download/rebuild editor arbitrario. **Dipendenze:** H6.

## 9. Ticket frontend — tutte le richieste nuove

### REQ-0002/T01 — Label e notch dell’outlined Field

**File:** `common/Field.css`/`.jinja`, `tests/frontend/test_field.py`; token/inventory soltanto se serve un valore nuovo.

Riprodurre su `/worlds/new`. Correggere l’anatomia legend/rule nel componente, non con override WorldCreate. Misurare centro label contro rule effettiva e notch, preservando outline/accessibilità e filled. Coprire input/textarea, empty/focus/populated/autofill/blur/error/disabled, long label, zoom e reduced motion; no movimento box/supporting/neighbors.

**Verifica:** browser regression con tolleranza geometrica stretta più screenshot forms desktop/phone. **Manuale:** `field-anatomy.md`. **Dipendenze:** H4 per capture affidabile.

### REQ-0003/T01 — Corpo vuoto realmente scrivibile

**File:** `editorial/DocEdit.jinja`/`.css`, sezione mountDocEdit in editor/index.js e bundle; call site dei sei Detail per copy contestuale; test navigator/autosave/empty body.

Invito UI distinto dalla source e hit area utile per chi può scrivere, con stessa focus language e apertura Enter/F2/double click più comando singolo touch. Il placeholder non entra mai nel Markdown/preview/API. Aggiornare empty state anche dopo preview/clear, senza clonare o perdere caret. Reader e locked non ricevono inviti. Conservare click su link e layout character/place.

**Verifica:** sei tipi, nuova bozza e corpo svuotato, API dopo autosave/reload, lettore/lock e tastiera/touch. **Manuali:** `in-place-editing.md`, `document-navigator.md`. **Dipendenze:** H4/H6.

### REQ-0004/T01 — Allineamento SaveIndicator

**File:** `common/SaveIndicator.css`/`.jinja` soltanto se necessario; test_save_indicator e test_autosave.

Dot centrato sulla riga del testo, non sull’intera banda. Preservare pseudo-elemento se textContent rimane il protocollo; overlay e aria live invariati. Gestire messaggi lunghi/wrapped senza collidere con crumbs o muovere Docbar.

**Verifica:** dirty/saving/saved/error/conflict, verde/giallo, zoom, 390px, bbox Docbar prima/dopo entro tolleranza. **Manuale:** `save-indicator.md`. **Dipendenze:** H4.

### REQ-0005/T01 — Toolbar a icone e menu secondario

**File:** `editorial/Docbar.jinja`/`.css`, caller place per comando corrente, component Menu/IconButton solo se un’estensione generale è indispensabile; test Docbar/actions.

Icon-only edit/lock/publication/more con label italiana del comando corrente, selected lock e touch >=44px. Fatti leggibili, ownership invariata; per delete/cancel-draft menu etichettato che invoca le conferme attuali. Comando place coerente con la barra. Nessun cambio ai route toggle/service o alla semantica draft/lock. Locked non permette publication che il service rifiuta.

**Verifica:** sei documenti, owner lungo, master/reader, draft/published e lock, menu tastiera/touch e conferme/API. Aggiornare test che richiedono vecchie righe o testo visibile, preservando i vincoli utili. **Manuale:** `docbar-regions.md`. **Dipendenze:** H4.

### REQ-0005/T02 — Badge editoriali di pubblicazione

**File:** nuovo componente editorial PublicationStatus, Docbar e CSS/tokens pertinenti; test badge/Docbar.

Forma rettangolare compatta carta/forest oppure carta/ochre, testo leggibile e marker, distinta da tint del documento, progress e save feedback. Non cambiare common.Pill globale, ownership o current-place badge.

**Verifica:** combinazioni stato/tint e reader, contrasto leggibile del nuovo controllo, focus non applicabile ai fatti, long copy/phone e nessun salto geometrico. **Dipendenze:** T01.

### REQ-0006/T01 — Barriera di persistenza per i comandi

**File:** AutosaveController e command interception in editor/index.js, bundle; Docbar data hooks; test_autosave/test_docbar_actions.

Esporre un’attesa Promise del controller che drena richiesta in-flight e dirty queue fino a esito noto. Non basarsi soltanto su testo “Salvato” o `await flush()` attuale. Mouse e hotkey devono invocare lo stesso comando visible/htmx dopo save riuscito. Non procedere con offline/409/422/423; conservare snapshot/recovery e focus. Evitare click ricorsivi e azioni duplicate. Coordinare eventuali ImageEditor writes ancora pendenti che condividono versione, senza nuova persistenza.

**Verifica:** richiesta lenta, ulteriori edit mentre save è in-flight, queue, conflitto, offline, lock e più click; API prova che l’ultima body/metadata è salvata prima della pubblicazione. **Dipendenze:** REQ-0003/T01, REQ-0005/T01.

### REQ-0006/T02 — Scorciatoie e help italiano

**File:** document key handler in editor/index.js, Docbar/help su Dialog/tooltip e bundle, test_document_navigator e shortcut E2E.

F2 e Mod+Shift+Enter come §3, hint `aria-keyshortcuts` quando pertinente e voce Scorciatoie nel menu. I key handler ignorano repeat/IME/modal/editor; una sola registrazione anche dopo htmx. Comando corrente autorizzato, nessuna alternativa backend. Phone mantiene tutti i comandi via touch.

**Verifica:** parity mouse/hotkey, locked/reader, dialogs/autocomplete/native typing, save error e focus; nessun override di Mod+Enter. **Dipendenze:** T01 e toolbar definitiva.

### REQ-0007/T01 — Data locale persistita alla creazione

**File:** `sessions/views.py`, schema di creazione interattiva in sessions/schemas.py, trigger SessionList e suo JS/vals mirato; test integration session creation e E2E.

Il browser calcola la propria data ISO con componenti locali, invia payload tipizzato al POST interattivo e il service persiste prima del redirect. Fallback Europe/Rome esplicito. Nessun default render-time/model-wide, timezone DB nuova o modifica degli import/API ordinari. Nullable clear e date storiche rimangono supportate.

**Verifica:** timezone su lati opposti di mezzanotte con clock controllato, API read-back immediato/reload, explicit date/null/import invariati, ordering/neighbours. **Manuale:** editing/session capability esistente. **Dipendenze:** H1 utile; indipendente dal nuovo calendario.

### REQ-0007/T02 — Calendario ibrido accessibile

**File:** nuovo `common/DatePicker.{jinja,css,js}`, Metadata e tipo campo se necessario, specimen e tests browser.

Input data canonico condiviso da typed entry e calendario desktop; griglia roving focus, frecce, Home/End, cambio mese/anno, selected/today, Oggi/Cancella, Escape e ritorno focus. Phone usa date input nativo. Nessuna dipendenza nuova prima di dimostrare che serve; usare Intl/Date con gestione date-only e leap day. Popup nel pannello chiude sé stesso prima del parent.

**Verifica:** invalid date, leap day, fine mese/anno, tastiera, resize/phone, lock/reader, API save/null e fallback. **Dipendenze:** T01, H4; serializzare integrazione Metadata con REQ-0008.

### REQ-0008/T01 — TintPicker compatto condiviso

**File:** nuovo `editorial/TintPicker.{jinja,css,js}`, ChoiceGrid riusato, test component e specimen.

Trigger swatch+nome, radio grid palette, selected mark non solo colore, focus/Escape/return e bounds dentro viewport. Il controllo canonico produce la stessa stringa p1–p12 del campo esistente; popup state non è document state. Nessun thumbnail o ImageEditor completo.

**Verifica:** tutti i nomi/token, keyboard/phone >=44px, apertura in Dialog, nested Escape, readonly/disabled e recovery state.

### REQ-0008/T02 — Integrazione con autosave e superfici

**File:** Metadata.jinja/asset, navigation.MetadataField, sessions/stories/pages views, eventuale sezione mountDocMetadata e bundle; E2E tint.

Tipo campo esplicito per tint; hidden/select canonico per autosave e sincronizzazione visuale in change/apply/recovery. Un campo registrato, non dodici radio concorrenti. `autosave:saved` aggiorna i fatti persistiti; scelta locale preview immediata senza falso “salvato”. Session/story/page tint-dependent surfaces si aggiornano senza reload e senza alterare colori publication.

**Verifica:** scelta rapida, rete lenta, 409/offline, restore locale, API/reload per i tre tipi e body pending conservato. **Dipendenze:** T01 e contratto autosave REQ-0006/T01; integrazione Metadata seriale con DatePicker/pannelli.

### REQ-0009/T01 — Payload tipizzato e visibilità delle menzioni

**File:** `content/actions.py`, piccolo service/schema content per suggestions se necessario, modelli esistenti letti esplicitamente; integration API matrix/references.

Arricchire MentionSuggestion con animal/shape opzionali e cue di fallback. Per shape/kind SVG usare generatori server fissi esistenti o primitive DOM whitelist, mai HTML da nomi/contenuto utenti. Filtrare world/draft/reader con la stessa policy dei service di lista prima di limit/disambiguazione; niente N+1 o download di tutto il world per ottenere otto suggerimenti. Non introdurre nuovi campi DB o cambiare la sintassi `@[...]`.

**Verifica:** propri/altrui draft, altro world, ruoli, stessi nomi fra tipi, metadata assente e contenuto ostile; formato insertion e campi precedenti compatibili. Non estendere il ticket a un audit completo di backlinks, ma registrare difetti esterni eventualmente osservati.

### REQ-0009/T02 — Rendering del menu CodeMirror

**File:** mentionSource/autocompletion in editor/index.js, Reference.css, bundle; test menu e E2E mention persistence.

`icons: false` + addToOptions dalla dipendenza già installata, mark rettangolare a dimensione fissa, animal text via textContent, shape/kind da valori sicuri. Label/tipo italiani, active selection chiara, long name ellipsis senza stretch e bounds phone. Conservare Up/Down/Enter/Escape/caret; non modificare inline mentions o live-preview grammar.

**Verifica:** sei tipi, fallback, nomi lunghi/uguali, caratteri escapati, autocomplete in summary/body/panel context e API dopo save. **Dipendenze:** T01; esclusività di editor/index.js durante questa integrazione.

### REQ-0010/T01 — Contratto DocDetails e pannello riusabile

**File:** nuovo `editorial/DocDetails.{jinja,css,js}`, `common/Dialog` opt-out/variant minimale, modelli view tipizzati, specimen e component tests.

Summary trigger sempre raggiungibile, desktop panel a destra e phone full-screen; riutilizzare native showModal e focus restore. Dialog pre-renderizzati non si aprono automaticamente dopo qualsiasi htmx swap. Non cambiare il body DOM/CodeMirror per aprire/chiudere; preservare selection/scroll/history. Errori metadata/recovery restano visibili nel pannello pertinente, mentre SaveIndicator rimane unico. Nested picker Escape non chiude parent; niente nuovo save mode.

**Verifica:** editor attivo dietro il pannello, readonly, empty/populated, nested dialogs/picker, afterSwap, focus e 390×844. **Dipendenze:** REQ-0006/T01, REQ-0008/T02 e opt-out Dialog stabile.

### REQ-0010/T02 — Contratto persistito delle sessioni collegate

**File:** `stories/schemas.py`, service `_resolve_sessions`, routes solo per serializer/error boundary, test_stories_service/API matrix.

Esporre relazioni persistite in un campo read-only additivo (ad esempio sessions summaries) per aggiornare count/names da risposta autentica. Resolver controlla anche visibilità dei draft, non solo world; errori validazione tipizzati e spiegabili, niente 500 per input utente invalido. Conservare contratti update/version/lock e validare deduplicazione.

**Verifica:** add/remove/empty, duplicate ID, altro world, draft altrui e 409/423; query DB dopo commit e GET API, non count DOM. **Dipendenze:** baseline; integrare prima del pannello story.

### REQ-0010/T03 — Story authoring e SessionPicker

**File:** StoryDetail, stories/views.py, DocDetails; nuovo editorial SessionPicker/asset se necessario, metadata e test frontend/E2E.

Titolo/sintesi/corpo primari; riepilogo progress/count/tint al posto della metadata boxed e della banda duplicata. Dettagli contengono period/progress/tint/session selection: checkbox native ricercabili, selected mantenuti fuori filtro, autosave controller unico. Readonly può leggere fatti ma non scrivere. Riutilizzare backend/picker, non mock rendering o multiselect custom improvvisato.

**Verifica:** nuove bozze, già pubblicate, sessioni duplicate/filtrate, body dirty e caret, close/reopen, 409/422/offline/lock/reader, GET e DB relations, backlinks invariati. **Dipendenze:** T01/T02, REQ-0003 e REQ-0008.

### REQ-0010/T04 — Page authoring e canonical URL senza perdita di editor

**File:** PageDetail/.css, pages/views.py, mountDocMetadata/AutosaveController slug handling e bundle; page service soltanto per bug riprodotti del contratto, test_flows/pages service.

Riepilogo address/menu position/tint e pannello separato con stessi controlli. URL canonical si aggiorna solo dopo ACK del server, usando history e aggiornamenti mirati della chrome invece di location.replace che distrugga l’editor. API URL e recovery key restano basati sull’UUID. Non perdere dirty body mentre slug è in-flight; errori slug/duplicate restano nel pannello e non cambiano URL. Riordinare/aggiornare la navigazione usando output persistito, senza refresh del corpo.

**Verifica:** slug valido/invalido/duplicate, menu position, tint, body pending/caret/undo mantenuti, reload su nuova canonical, close/reopen, lock/reader e other-pages/backlinks. **Dipendenze:** T01, REQ-0006/T01, REQ-0008/T02; dopo Story per riuso verificato.

## 10. CI e chiusura del ciclo

### REQ-0001/T02 — GitHub Actions

**File:** `.github/workflows/ci.yml`, helper di raccolta diagnostic artifact sotto tools/ci se necessario, test statici workflow; documentazione CI/deployment.

Runner `ubuntu-24.04`, Python 3.14 coerente con il progetto e Node LTS già usato; lockfile frozen. Actions essenziali checkout/setup-uv/setup-node/upload-artifact pinned a SHA completi verificati, non inventati. Nessun setup di config agente nel runner.

- Trigger PR base main, push main, manuale; concurrency per ref e cancellation dei superseded.
- Permissions contents read e checkout senza credenziali persistite; niente pull_request_target, segreti production, image upload o deploy.
- Ruff/pre-commit/material/metadata/frammenti e unit; npm ci e browser supportato; frontend; harness env local + integration; teardown; harness env docker + e2e fresh; teardown anche su fallimento.
- Default iniziale: una piattaforma, niente matrice superflua. Job distinti possono restare isolati; non duplicare setup/build inutilmente. Timeout basato sul runtime misurato con margine, senza silenziare suite pesanti.
- Artifact failure-only, allowlist e massimo proposto 10 MB complessivi per run, retention tre giorni: JUnit/log ripuliti e screenshot selezionati. Non caricare l’intero harness-artifacts, HTML/token, dump, .env o image archive.
- Public standard runners hanno minuti gratuiti; artifact storage resta finito. Quote account-wide non sono state ispezionate per scelta dell’utente. Nessuna promessa di assenza di overage; se occorre una verifica billing, lasciarla a Oscar e non cambiare settings.

**Verifica:** clean checkout con tutti i check e suites; deliberately failing fixture in target disposable fallisce; workflow e artifact collector hanno test su failure/size/redaction; prova hosted dopo push. Non inviare appositamente un commit rotto su main.

**Dipendenze:** H1/H5/H6/H7/H8, tooling metadata/Towncrier. Preparabile in parallelo alla UI quando contratti tooling stabili; pubblicazione normalmente alla fine.

### REQ-0001/T09 — Audit, push finale e rollout del build finale

**File:** test/regressioni e manuali già pertinenti; manifest operativi, esiti sulla board e frammenti.

1. Review tutte le richieste e tutti i diff/commit del ciclo, non solo gli ultimi. Ogni requisito ha ticket, prova o blocker esplicito; T01 App resta rinviato.
2. Clean tests completi, harness doctor/material, hooks, metadata e draft Towncrier; nessuna nuova versione.
3. Confronti desktop/phone con prototipo originale e studio selezionato; non giudicare una modifica approvata contro il vecchio mock come regressione. Pixel diff non è gate assoluto.
4. Push ordinario su main con auth esistente solo dopo esito locale verde; remote avanzato/conflitto o credential error fermano il push, niente force/reconfig. Il push rende attiva CI e non deploya.
5. Osservare CI con accesso pubblico non autenticato disponibile o verifica dell’utente, senza letture gh proibite. Se non verificabile, registrare il gate hosted come pendente; non chiamare CI “passata” dalla sola simulazione locale.
6. Build finale dal commit verificato e invocazione locale manuale del playbook: backup pre-deploy, rollout, readiness, login reale, dati iniziali/user changes preservati. Se la CI osservata fallisce, nessun override automatico; continuare correzioni locali o fermare il rollout.
7. Consegna: elenco sintetico di capacità, board reale, endpoint/config non segreti, posizione privata delle credenziali, backup status, immagini/schema attivi e limiti. Nessuna release/tag o storico importato.

**Dipendenze:** tutti i ticket consegnati; un blocco hosted/firewall non viene cancellato dal piano ma riportato separatamente dal codice completato.

## 11. Ordine e parallelismo flessibile

### Grafo alto livello

```
baseline -> T00 -> T03 -> T05 -> T04 -> T06 -> Vikunja T01 -> bootstrap T07
                                                        |
                                                        v
                                      metadata -> CLI read/create -> move/close -> import
                                                        |
                      +---------------------------------+------------------------------+
                      |                                 |                              |
                 harness waves                    UI waves                       weekly backup
                      |                                 |
                      +---- Towncrier / CI --------------+
                                                        |
                                                audit / push / rollout finale
```

La tranche server procede coordinata, senza subagenti sul target. Se un gate firewall/OS dipende dall’utente, verificare via tunnel e proseguire i rami indipendenti; non inventare permessi.

### Onde suggerite dopo bootstrap

| Onda | Fino a tre ticket concorrenti | Integrazione/limiti |
|---|---|---|
| A | H1, H6, H7 | File principali distinti; coordinatore su manuali/AGENTS. Venv separate. Nessun Towncrier contemporaneo a H7. |
| B | H4, H5, REQ-0012/T06 Towncrier | H6/H7 integrati. H4 solo browser/compare, H5 hook/test budget, Towncrier pyproject/lock. |
| C | REQ-0002/T01, REQ-0004/T01, REQ-0007/T01 | Field, SaveIndicator e session creation distinti. Nuovi token integrati serialmente. |
| D | REQ-0003/T01, REQ-0005/T01, REQ-0009/T01 | Un solo owner editor/index.js; toolbar solo componenti, suggestions solo backend. |
| E | REQ-0005/T02, REQ-0008/T01, REQ-0007/T02 componente | Nuovi componenti distinti; wire Metadata/navigation e bundle integrati serialmente. |
| F | REQ-0006/T01, REQ-0010/T02, H2 | Controller JS, story backend e compare separati. |
| G | REQ-0006/T02 oppure REQ-0009/T02, CI, backup periodico | Una modifica del controller/bundle per volta. |
| H | REQ-0008/T02 -> REQ-0010/T01 -> Story T03 -> Page T04 | Dipendenze vere e file comuni: integrazione sequenziale; altri ticket non dipendenti possono affiancarsi. |

Queste sono onde adattabili, non l’obbligo di usare tre agenti. Prima di ciascuna: dichiarare ticket, confini file, contratti già integrati, namespace test e ordine integrazione. Conflitti piccoli su registry/token possono essere risolti dal coordinatore; non parallelizzare automaticamente modifiche concorrenti di AutosaveController, Metadata, auth, migrations o rollback.

### Isolamento obbligatorio

- Un worktree/branch e una venv per ticket, con massimo tre agenti. Subagenti usano harness CLI del proprio checkout, non un MCP server rimasto puntato al checkout coordinatore.
- HARNESS_REPO_ROOT, cache/state, project names, ports, DB, uploads, artifact e CWD devono riferirsi al worktree corrente. Nessun uso del dev stack a porte fisse o board demo per test di agenti.
- Browser già installati possono essere condivisi in sola lettura tramite override esplicito dopo H6, con revisione corrispondente; installazione seriale. Node/venv e artifact separati.
- Il test prototipo preesistente scrive in `/tmp/rootgdr-feedback-prototype`: prima di eseguire suite frontend concorrenti correggere il percorso a un tmp_path/artifact run isolato, oppure serializzare quel test. Non trattare quei file condivisi come isolate per magia.
- Alla review del coordinatore: diff completo, test indipendente, screenshot reali e, per write, API/DB read-back. Ricostruire bundle dal sorgente, mai fare merge testuale del minificato.
- Integrare con un commit per ticket, senza riscrivere history pubblicata. Gli agenti non pushano. Non eliminare worktree, branch o dati altrui; cleanup solo del materiale nuovo autorizzato.

## 12. Files to Modify

### Esistenti — principali

- `AGENTS.md`, documenti delle richieste e processo: decisioni correnti, ID/alias e confini; nessun live-status mirror.
- `pyproject.toml`, `uv.lock`, `package.json`, eventuale `package-lock.json`, `.pre-commit-config.yaml`, `setup.sh`, `config.yaml`, `LICENSE`, `.dockerignore`, `Dockerfile`.
- `src/backend/config.py`, `server.py`, `db/db.py` se SQL echo, `auth/routes/auth.py`, `auth/views.py`, `auth/tokens.py` soltanto per confini production/version e bug dimostrati; `alembic/env.py`, `src/cli/config/check.py`.
- `src/harness/cli.py`, `commands/{test,browsers,screenshot,compare}.py`, `test/{runner,browser,landmarks,compare}.py`, frontend fixtures e test prototipo artifact path.
- `src/frontend/components/common/{Field,SaveIndicator,Dialog}.*`, `editorial/{DocEdit,Docbar,Metadata,Reference}.*`, `pages/sessions/SessionList.jinja`, StoryDetail e PageDetail; call site DocEdit dei sei documenti.
- `src/frontend/js/editor/index.js` e bundle generato; `static/css/main.css` soltanto alias/token globali necessari, non layout nuovi.
- `src/backend/navigation.py`, `content/actions.py`, `sessions/{views,schemas}.py`, `stories/{views,service,schemas}.py`, `pages/views.py`; nessun cambio schema DB previsto.
- Test unit/frontend/integration/E2E esistenti, soprattutto config, board, browser/compare, Field, SaveIndicator, Docbar, Dialog, autosave, navigator, flows, API matrix e services.
- Manuali esistenti: harness-tooling, component-tests, local-task-boards, field-anatomy, save-indicator, docbar-regions, in-place-editing, document-navigator, mention/document/collection capabilities appropriate e indice.

### Nuovi — giustificati dalle capacità richieste

- Specifica REQ-0012 e frontmatter REQ-0011 nel documento harness, se gli ID restano liberi.
- `deploy/production.compose.yaml`, `deploy/vikunja.compose.yaml`, playbook deploy/backup/restore, ruoli e template applicativi/inventory example.
- `src/harness/deploy/`, `commands/deploy.py`, `src/harness/tickets/`, `commands/tickets.py`, `browser_runtime.py` e relativi test.
- `src/backend/health/`, eventuale service/schema per mention suggestions, entrypoint seed solo se necessario.
- DatePicker, TintPicker, PublicationStatus, DocDetails e SessionPicker/asset/test/specimen, evitando nuovi wrapper senza responsabilità.
- `changelog.d/` e `CHANGELOG.md`; al massimo pochi manuali tematici nuovi per deployment e planning/release, non quaranta manuali.
- Config/segreti privati, chiave age, unit timer operative e backup fuori da Git; nessun nuovo config in directory di altri coding agent.

## 13. Verification

### Comandi esistenti, da eseguire in implementazione

```
uv sync --frozen --dev
npm ci
uv run harness browsers
uv run ruff check <file del ticket>
uv run ruff format --check <file del ticket>
uv run pre-commit run --all-files
uv run harness material check
uv run harness test unit
uv run harness test frontend
uv run harness env up --mode local
uv run harness test integration
uv run harness env teardown
uv run harness env up --mode docker
uv run harness test e2e --fresh
uv run harness doctor
uv run harness env teardown
```

Usare MCP harness quando disponibile e puntato all’ambiente giusto; CLI necessaria per provare H1. Questi comandi non autorizzano reset work/showcase/production; fresh e teardown solo nei namespace test propri creati per il ciclo.

### Comandi dopo i ticket che li introducono

```
uv run harness test frontend -- tests/frontend/test_field.py -q
uv run harness test e2e --fresh -- -k empty_body -x --tb=long
uv run harness compare /worlds/<reference-id> --check-landmarks --output-dir /tmp/<run>/compare
uv run towncrier build --draft --version UNRELEASED
ansible-playbook -i <inventory-disposable> deploy/deploy.yaml --syntax-check
ansible-playbook -i <inventory-disposable> deploy/deploy.yaml --check --diff
uv run harness tickets import <specs> --dry-run
```

La facciata deploy/tickets precisa viene documentata mentre si realizza; evitare di far passare opzioni non ancora implementate per comandi attuali. Diff sempre off sui task Vault. Restore e fault injection solo disposable.

### Matrice di accettazione finale

- [ ] Root e Vikunja reali separati, login autentico, build/schema riconoscibili e boot lifecycle configurato senza interferenze coi bot.
- [ ] Root LAN desktop/phone e Vikunja PC/tunnel; firewall phone pendente dichiarato se Oscar non ha ancora aperto la porta.
- [ ] Runtime privo di credenziali DDL; uploads persistenti; nessun dato/credential/artifact privato nell’immagine.
- [ ] Backup pre-deploy + settimanale cifrato sul PC, retention quattro complete/pre-deploy conservati, status failure/age e restore reale isolato.
- [ ] Rollout ripetuto no-op, lock e fallimenti testati, rollback app sicuro; nessun restore automatico.
- [ ] CLI board reale, paginazione/mutazioni/idempotenza, soli ticket nuovi, demo/storico preservati.
- [ ] Harness H1–H7 e setup Node/E2E verificati, senza falsi verdi o soglie alzate.
- [ ] REQ-0002–REQ-0010 interamente coperti da test/persistenza/desktop+phone evidence e manuali aggiornati.
- [ ] Versione invariata e bozza Towncrier, nessun tag/release attribuiti automaticamente.
- [ ] CI clean checkout su push/PR main; prova hosted osservata o blocker esplicitamente aperto, senza dichiarazione falsa.
- [ ] Push finale e deployment finale del commit verificato, dati creati dopo il bootstrap preservati.

## 14. Risks/Considerations e regole AFK

1. **Spazio server:** 6,4 GB erano liberi durante ricerca; packaging snello e staging off-server aiutano, ma il preflight può fermare il rollout. Non rimuovere immagini estranee o espandere storage senza Oscar.
2. **Firewall/permessi:** l’utente apre una porta LAN una volta. Nessun sudo con prompt, TTY workaround o indebolimento SELinux. Se negato, comunicare blocker e continuare tooling/UI.
3. **HTTP LAN:** niente confidenzialità TLS per login/cookie nella LAN; è il profilo privato esplicitamente scelto. Non usare password riutilizzate altrove e non estendere esposizione a Internet. Un futuro HTTPS è separato.
4. **Provider/age/Vault:** versioni fissate e install user-scoped; check mode non installa/builda. I segreti non entrano in branch degli agenti, artifact, token URL o deploy dei bot. Se autenticazione non riesce, non cercare credenziali personali alternative.
5. **Backup PC offline:** weekly non è una garanzia se macchina o rete sono spente; mostrare overdue e ultimo errore, conservare l’ultima buona. Chiave di cifratura non nello stesso archivio; consegnare percorso e necessità di custodirne una copia.
6. **Schema/rollback:** uguaglianza Alembic è il default conservativo, non una prova generale per ogni migrazione futura. Migrations distruttive o schemi sconosciuti richiedono intervento, mai downgrade o restore automatico.
7. **Dati vivi:** nessun seed/restore periodico che sovrascriva modifiche dell’utente, nessun reset showcase e nessuna migrazione demo/storico. Seed bootstrap con marker operativo, non match per nome che aggiorni il world ogni volta.
8. **Concorrenza UI:** autosave, ImageEditor, slug, nested dialogs e versione condivisa sono il rischio principale. Prima prove lente/offline/conflitti, poi composizione. Non estrarre una nuova architettura per facilitare la delega.
9. **Permessi documenti:** estendere suggestions/relationships richiede filtri prima di serializzare. Non introdurre leak di bozze o metadati; registrare eventuali difetti esterni riproducibili, senza trasformare il ciclo in un audit generico.
10. **Baseline in movimento:** il prototipo/nuove richieste sono stati creati mentre pianificavo. Riesaminare i file prima di commit/implementazione; non considerare tutto il contenuto corrente “prodotto dell’agente”.
11. **CI pubblica:** runner standard free non significa storage infinito. Nessuna modifica billing senza autorizzazione; log con dati di test, artifact piccoli e scadenza. Non occultare un test rosso perché Oscar può bypassare.
12. **Assunzioni di design:** adottate per AFK e circoscritte; verificare col prototipo selezionato. Se una scelta richiede un contratto nuovo, palette diversa, una dependency importante o nuovi dati, segnalarla e fermare quel ramo, non improvvisare.
13. **Recovery da compaction:** rileggere richieste e piano, poi leggere stato reale da Vikunja/Git/manifest; non ricostruire completamenti dalla memoria o duplicare stati manuali nei Markdown.
14. **Done e blocked:** nessun task sparisce perché difficile. Esito codice/test, attivazione server, accesso phone, CI hosted e release sono gate distinti. Completare quelli provati e riportare chiaramente quelli ancora aperti.

La consegna AFK termina con prove, stato board e manifest verificabili. La scelta della versione e un eventuale primo rilascio restano una conversazione successiva.

## Execution evidence — 2026-10-03

- Baseline board/process preserved in commit `6559e59`; feedback/specifications and selected prototype preserved separately in `61c85ed`.
- Baseline: 456 unit tests passed, 316 frontend tests passed, 115 integration tests passed (1013 deselected). Integration ran in a newly created local harness environment, then that environment was torn down and config.test.yaml restored.
- Prototype desktop/390×844 details and fields screenshots reviewed. Both board login pages checked at 1440×900 and 390×844, without overflow or page errors. Root worlds desktop/phone compared against the original prototype under `/tmp/rootgdr-baseline-worlds`.
- Existing work/showcase stack and all board data preserved. No push or server deployment performed.
- MCP selector validation uses a different checkout than the current CLI; implementation uses `uv run --frozen harness` from this repository until that mismatch is resolved without changing another environment.
- Full E2E baseline remains to run; production packaging must first prevent the current build context from copying local data/browser/artifact directories into test images.
- Approved cycle decisions and reservations REQ-0011/REQ-0012 recorded in commit `3629f34`; old App/PR proposal is explicitly deferred. Frontend request defaults recorded without duplicating live ticket status.
- REQ-0001/T00 completed in `8520572`: author/bootstrap defaults use the personal Gmail address; current license attribution retains Oscar and MIT without the former affiliation. Regression reproduced before the fix; 457 unit tests and frozen lock check passed; desktop/phone comparison under `/tmp/rootgdr-t00-worlds` reviewed. Existing accounts/private dotenv/test actors preserved. This metadata cleanup does not create a separate feature manual or user release note; deployment identity is covered by the deployment capability.
- REQ-0001/T03 completed in `7700586`: allowlisted build/COPY, UID/GID 10001, production Compose with separate bootstrap/migration/runtime env files and persistent uploads; optional runtime migrator with explicit Alembic refusal; SQL parameter echo disabled. 464 unit and 118 integration tests passed, including real role grants, private-file exclusion, hardened read-only image startup and cross-container upload persistence. Hooks passed; desktop/phone comparison reviewed under `/tmp/rootgdr-t03-worlds`. Initial OCI ENOSPC was caused by 87 MB uv cache copied into a 64 MB tmpfs: cleaned cache in build without increasing the runtime limit.
- Clean selected-commit image built for SHA `7700586a13fb59e6920c0d73bb77b066be5bce58`, image ID `a2b0b2eb89b0d85ad33f32d392780dea2368bc5f371c39e865bb1f5bd9a8f7bc`. No push or production server changes. Local integration environment torn down before commit; Docker E2E baseline is the next verification gate.
- Full Docker E2E baseline passed: 64 tests, 1075 deselected, using a newly created harness environment and `--fresh` only on its E2E database/uploads. Current owned Docker test environment remains active at backend 8000 and database 5432 for T05; work/showcase on 8001/8002 and local board volumes remain untouched. The clean selected-commit image size is 455,930,704 bytes. T05 is the current implementation ticket.
- T05 implementation adds bounded DB/schema/storage readiness and build information, production-only route registration boundaries, and a real-password verifier. Refresh UUID conversion was reproduced and fixed locally. Current verification before the latest world/image test: 464 unit, 129 integration, 64 E2E passed; image-only production startup/route checks passed. T05 is not yet committed.
- Discovered follow-up REQ-0011/T09: Docker `env up --recreate` starts/recreates db, prepares schemas, then force-recreates all services again, losing the ephemeral integration database. E2E fresh recreates only E2E. Exact evidence is in `docs/features-request/problems/harness-recreate-database.md`. The source compose.py predates T05. Owned test integration schema is recovered with harness ensure_databases/run_migrations, without resetting E2E; T09 needs app-only --no-deps startup plus regression tests and its own commit. This is an additional ticket to the original 40, not a dropped requirement.
- REQ-0001/T05 completed in `cd098b0`: readiness/version endpoints, no dev-login routes in production, corrected UUID refresh, and typed real-password verification including persisted world and uploaded image. Final checks: 464 unit, 130 integration, 64 E2E; hooks and desktop/phone comparison passed. The owned Docker test environment was torn down and config.test.yaml restored before commit; no real server changes or push. T09 recreation fix is the next small standalone prerequisite before backup/Ansible testing.
- Follow-up REQ-0001/T10 completed in `7e231a5`: Podman reused metadata-only ARG/ENV/LABEL layers from a default `unknown` build. A build step consumes the argument before metadata. Regression verifies separate cached values in OCI label and runtime; no revision guard weakened. This second new finding brings the cycle to 42 execution tickets.
- REQ-0011/T09 completed in `6de31a4`: backend startup is app-only with --no-deps after DB initialization. Regression failed before fix; an actual recreate retained both database heads, complete 464 unit/131 integration/64 E2E passed, and both heads were verified again after E2E fresh. Desktop/phone comparison `/tmp/rootgdr-h9-worlds` reviewed. Own test environment torn down before both commits; work/showcase/board data preserved; no server deployment or push.
- Current ticket is REQ-0001/T04 (coordinated backup and isolated restore). No subagents/worktrees have been launched: Root GDR/Vikunja bootstrap remains the gate. Local `age`/Go binaries are absent; Ansible and Podman are available, with pinned restic 0.19.1 image cached locally as a possible maintained encryption alternative. Any selection must keep the approved backup/retention/secret-handling contract; do not introduce a bespoke crypto format.

## Execution evidence — 2026-10-04

- User explicitly requested continued execution and subagents, plus a local watchdog checking every 30 minutes until tomorrow 10:00. Local clock was already 2026-10-04 00:27 Europe/Rome; configured stop is 2026-10-05 10:00 Europe/Rome and was explicitly reported. New request/specification REQ-0013 records this operator extension.
- Watchdog implementation committed as `7a3bc44` with 479 unit tests passing. Source/config/hooks/unit sources live in repository `.devin/`; runtime state and machine-local JSON are gitignored. User systemd timer `rootgdr-afk-watchdog.timer` is linked/enabled and ticks at minutes00/30. Actual ticks00:49/01:00 detected the current Desktop coordinator as busy without launching a duplicate. Reader uses target session main-chain metadata and PID lock, never transcript text/credentials; CLI worker has exclusive supervisor lock, Smart mode, normal trust and a Desktop-resumption guard. Deadline/completion disable own timer only.
- ACTUAL CLI WAKE-UP IS BLOCKED: `/home/oscar/.local/bin/devin` and embedded Desktop CLI report not logged in. User was asked to run `devin auth login`; no token lookup, lock deletion, desktop termination or trust bypass attempted. Do not claim authenticated wake-up has passed until login and an actual safe launch check. Current desktop session ID is `flourish-random`, lock PID28850 (`devin acp`). Standalone project hooks are not assumed hot-reloaded into that existing process.
- Subagent 8939aa89 is implementing T04 in `/home/oscar/Progetti/RootGDRWebsite-afk-backup`, branch `afk/req-0001-t04` at base6de31a4; it owns backup modules/roles/playbooks/tests and its own harness environment. Do not edit/reset its environment or duplicate this work while it is active. Last observed it was writing modules and real recovery tests; config.test.yaml is temporarily harness-managed in that worktree. No push/server access allowed for agents.
- Read-only agents ae996ad9 (CLI watchdog) and4174dd63 (deployment architecture) completed research. No documented attach/prompt API for idle locked Desktop: fresh CLI coordinator on the same plan is the fallback, with ownership guard. T06 must integrate the actual T04 contract when landed; proposals are not existing code. Vikunja research suggestions mentioning APIv1 require independent correction to the approved v2 contract before implementation.
- H1 agent9f686a72 completed branch `afk/req-0011-t01` in `/home/oscar/Progetti/RootGDRWebsite-afk-h1`, commit6858a5e. Coordinator independently read CLI/runner code, tested selective quoted -k (40 passed,63 deselected), ran complete582 unit tests, hooks and desktop/phone comparison `/tmp/rootgdr-h1-worlds`, then integrated implementation+manual+fragment as `f777c81`. Main is the authoritative integrated code. Worktree was clean; no infra started/reset for H1.
- Current remaining first prerequisite is T04 review/integration, then T06/REQ0012T01 infrastructure and actual bootstrap. Pending original board/release/harness/CI/UI work is unchanged except H1 completed. Preserve ordinary end-of-cycle push and all deployment/recovery safeguards. No production rollout or push has occurred.

## Continuation evidence — 2026-10-04

- Oscar requested continuation from flourish-random and explicitly abandoned the watchdog. Do not reactivate, repair or use it. Oscar is AFK and requests immediate sequential progression after each tested/committed ticket; ask only for gates requiring his authorization. No new subagents or worktrees have been launched.
- Reviewed all T04 modules/roles/tests from worktree commit 67e3076. Real cached Restic 0.19.1 and PostgreSQL 18.3 execute correctly. Added a failing immutable-image regression and fixed PostgreSQL recovery to its observed digest, preserving --pull=never. Integrated the reviewed implementation on main as e896c85, with 605 unit tests, full 149 integration tests, hooks and desktop/Pixel 7/390x844 prototype comparison at /tmp/rootgdr-t04-review-worlds. T04 and main-owned test environments were torn down; work/showcase and board data preserved.
- Split a small T06 prerequisite as REQ-0001/T11 (specification records the boundary/dependency). Implemented selected-Git-snapshot build, Linux/amd64 and OCI/runtime revision validation, package version through /opt/venv/bin/python, immutable-ID OCI save, private typed/checksummed manifest and dry-run. Real clone with deliberately invalid dirty Dockerfile still builds the chosen commit, saves/loads the image and checks its OCI config digest. 614 unit tests and two real integration checks passed, hooks passed, desktop/Pixel 7/390x844 comparison /tmp/rootgdr-t11-review-worlds reviewed. Committed cc4d8eb; its owned local test environment was torn down. Version remains 0.1.0, no push, production deployment or release.
- REQ-0001/T06 completed as 7cd040c: typed isolated target/proof/configuration fingerprints, verified immutable application/helper/PostgreSQL transfer, conservative disk/listener checks, private minimal pinned Python/Compose tools, atomic shared lock, staged configuration, pre-deploy encrypted gate, DDL-only migration, real password/API/HTML/image verification, conservative single rollback and explicit pending-recovery state. Native user-service restart and data persistence tested. Configuration validation checks both runtime and migrator against the same isolated database; SQL init reads passwords through psql getenv rather than argv.
- T06 verification: 629 complete unit tests, full 164 integration tests, plus the newly added migration-host refusal integration test passed separately (165 distinct integration cases). All-files hooks passed; desktop/Pixel 7/390x844 compare at /tmp/rootgdr-t06-review-worlds reviewed. Test collection initially exposed duplicate T11 unit/integration test basenames; unit file is now test_deployment_artifact_boundaries.py. A hook normalized one existing Python 3.14 except clause in harness/artifacts.py. The owned local harness environment was torn down and config.test.yaml restored; main is clean after the T06 commit.
- Native restart regression found Podman read-only named-volume mounts silently chowning upload root from 10001:10001 to 0:0. Confirmed with before/after stat and public readiness checks (storage false). Backup source_mount and capacity now resolve an existing volume's typed canonical Mountpoint and bind it read-only instead; UID/GID/mode and readiness preservation pass. Enhanced recovery test checks the volume-root owner too. Do not weaken SELinux, chmod live uploads or remove the ownership regression. Temporary safe status diagnostics were removed after root cause was established.
- A duplicate test invocation was interrupted; its own leftover UUID-scoped disposable DB/volume/network (pytest-81/rootgdr-disposable-05fc71a7a207405fb46b4b4788266629) were positively identified and cleaned. Other user/development/board resources were preserved. No background test remains active at ticket completion.
- Oscar resumed AFK implementation, explicitly authorized deploying to his home server and said to finish everything; he also asked that after every compaction the plan and the input documents be re-read. T07 implementation committed as 2ac1b1ea39809bf1b5f909c0352f548a01ea5e77: controller-side bundle conversion (`rollout_cli seed-request`, lazy PyYAML with `# noqa: PLC0415` so the pinned target helper stays minimal), `backend/content/bootstrap.py` (production-only, commit-pinned, advisory-locked, create-or-preserve), `deploy/roles/rootgdr_application/tasks/seed.yaml`, seed+re-verify in rollout.yaml, and a one-attempt-per-invocation guard for the initial account in verify.yaml. 651 unit tests and 316 frontend tests passed; the disposable first-bootstrap seed test passed in 92s. An earlier commit accidentally included harness-written config.test.yaml; it was reverted and the commit amended, then a second amend added the verify.yaml guard.
- T07 live inputs generated privately under `~/.config/devin/rootgdr/` (runtime/migration config+env, database.env, vault-encrypted deployment.vault.yaml, inventory.yaml, board-inventory.yaml, board signing secret, verification.json) plus the restic repository at `~/.local/share/rootgdr/backups/repository`. Values are never printed. Server preflight: pinball-server, x86_64, podman 5.8.4, ~6.86 GB free, `/home/pinball/rootgdr-production` and `/home/pinball/rootgdr-vikunja` both still absent.
- Remaining T07 order: full integration + e2e gates for 2ac1b1e, artifact build, `harness deploy apply --check`, real rollout, `harness deploy board`, LAN/tunnel verification and desktop/phone evidence, then manual/plan/commit. Do not restart bot services or touch the old server checkout.
- First live rollout attempt failed after downtime in the coordinated capture: reviewed tool images transferred as archives exist on the target only by immutable ID, so the pinned digest reference did not resolve for the helper container. Verified by direct reproduction on the server (`No module named`/pull refusal path) and by `podman image inspect <digest>` missing while the same image ID was present untagged. Fixed in c7d61d9 by carrying `helper_image_id` in `DeploymentPlan`/`CurrentDeployment`/`VikunjaPlan` and in `CaptureSpec.helper_image`, used by capture, capacity and board bootstrap. 652 unit tests pass. The failed attempt was cleaned only after confirming zero user tables and no alembic_version; its containers, volumes, network and release directory were removed.
- T07 completed on the server: Root GDR at /home/pinball/rootgdr-production on 192.168.1.201:8001, commit c7d61d9, version 0.1.0, head c35a50fec1ae, service rootgdr-production.service enabled+active; board at /home/pinball/rootgdr-vikunja loopback 3458, owner oscar id 1, bot bot-rootgdr-tooling id 2, project 2, token 1, service rootgdr-vikunja.service enabled+active. Both verified with real password logins, /health/ready 200, /version and the seeded reference world; desktop, Pixel-7-class and 390x844 captures reviewed at /tmp/rootgdr-t07-review. The server firewall does not yet admit 8001 from the LAN, so LAN/phone access remains Oscar's open gate; verification used explicit SSH tunnels (8001 and 3458), since the board frontend builds absolute API URLs from its own public URL.
- T07 committed as 2ac1b1e (seed), c7d61d9 (helper-image boundary), 1bde675 (bootstrap record). T08 committed as e88aecb: `deploy/weekly-backup.yaml` + `deploy/weekly-capture.yaml`, `deploy/systemd/rootgdr-weekly-backup.{service,timer}` (Sun 10:00 Europe/Rome, Persistent), `src/harness/deploy/backup_retention.py` (managed-only retention, private status, overdue after 8 days), `harness deploy backup|backup-status|install-backup-timer`, durable `<base>/plan.json` published by both rollout paths, `rollout_cli capture-spec --purpose weekly` with a fresh run UUID (a reused run ID collided with the existing receipt and failed the seal). 661 unit tests pass. Timer installed and enabled on the PC; two real weekly runs produced distinct encrypted snapshots per application and a disposable restore of the newest Root GDR weekly snapshot verified schema, grants and configuration.
- Private controller state (never print): `~/.config/devin/rootgdr/{inventory.yaml,board-inventory.yaml,backup-inventory.yaml,deployment.vault.yaml,vault-password,verification.json,storage.json,weekly.json,runtime.*,migration.*,database.env,board-signing-secret}`; backups at `~/.local/share/rootgdr/backups/{repository,weekly,predeploy,status}`; artifact at `~/.local/share/rootgdr/build/c7d61d9`.
- Open gate for Oscar: the server firewall still refuses port 8001 from the LAN, so phone/LAN access to Root GDR is unverified; everything else was verified through SSH tunnels. The board frontend builds absolute API URLs from its own public URL, so its tunnel must reuse the same port number (3458).
- REQ-0012/T03 committed as 71e3a74: `src/harness/backlog/client.py` (typed API v2 client, BoardPage pagination up to a reviewed bound, bounded status mapping that never echoes upstream bodies, private token file or `ROOTGDR_BOARD_TOKEN_FILE`, loopback-only base URL), `src/harness/commands/backlog.py` (`projects|list|show|create`, human rows show ids/titles only, `--json` for full records), registered in `cli.py`. 674 unit tests pass; a real isolated 2.6.0 integration case paginates 55 tasks, creates and reads back, and checks 404/422/wrong-token; the live server board was also read through its tunnel with the tooling token. Note: `podman start rootgdr-task-boards_vikunja_1` was used only to read the local demo OpenAPI for path confirmation — the demo container may now be running where it previously was not; do not treat that as a change to demo data.
- Next tickets in order: REQ-0012/T02 (request metadata + historical inventory), T04 (move/close/comments), T05 (idempotent import of the 40 cycle tickets), T06 (Towncrier/version authority); then REQ-0011 H2–H7 harness work, REQ-0002–REQ-0010 frontend tickets, REQ-0001/T02 CI and the final audit. No push, release, version bump or fragment consumption yet; the demo board and Kanboard data remain untouched. REQ-0012/T01 completed locally in e9e6773: thin Vikunja Ansible role/playbook/facade, shared immutable image transfer, minimal pinned Python/HTTP/Compose environments, private owner and owned scoped bot token, operation lock, conservative unchanged reapply, closed-registration failure cleanup/pending marker, native user-systemd lifecycle and coordinated encrypted recovery. Full unit suite: 651 passed. Complete board integration matrix: 10 passed in 228.69s (check mode, API/restart, Ansible no-op, native restart, real minimal tools, refused credential rotation, concurrent lock, failed bootstrap cleanup/no adoption, encrypted SQLite/task/attachment/login/token restore, browser login evidence). Desktop/Pixel 7/390x844 captures at /tmp/rootgdr-t01-review-514c969a23204bf790dc43a7abda5b7b reviewed. Manual updated in production-deployment.md; fragment REQ-0012-T01.added.md; commit hooks passed. Owned harness environment stopped/config restored. T07 now begins with fresh suite gates and read-only remote preflight. No live activation, push or release yet.
- API facts verified on disposable data: registration uses it-IT (it gives 422); ordinary account registration creates Inbox, so tooling uses POST /api/v2/user/bots with bot- prefix and no password/email. Owner creates bot token with owner_id; shared project permission is 1. Scope keys are projects, tasks, tasks_comments, projects_views, projects_views_tasks; bucket operations are projects.views_buckets/views_buckets_tasks. Lists include virtual negative project IDs; filter them when asserting real project boundaries. info.auth.local.registration_enabled replaces the v1 root flag. Token-denied endpoints return 401, not necessarily 403. Token expiry is provisionally one year and should be documented/reviewed.
- Podman service restart changed the attachments root owner to 0 and broke storage. Runtime compose now bind-mounts canonical mountpoints of dedicated named volumes instead of mounting volume names; initialization chowns only newly created volumes. Real restart now passes. Temporary redacted diagnostics removed. Demo Vikunja/Kanboard, work/showcase, production server and Git remote remain unchanged. No new subagents/worktrees, push, release or watchdog activity.
- Preserve the two old AFK worktrees. The backup worktree has review-only modifications to three T04 files; main contains the authoritative integrated result. MCP selector validation still points to another checkout; use uv run harness from this repository rather than modifying MCP state.

## Continuation evidence — 2026-10-05

- Workspace continued on a fresh WSL checkout: the gitignored `.env` was missing, so it was rebuilt locally (values never printed); REQ-0011/T10 then fixed the template itself. `podman` and `ansible-playbook` are absent on this machine, so the seven `test_rollout_boundaries` unit tests fail on the missing binary; GitHub ubuntu-24.04 runners ship both, so the gap is local, not a code defect.
- REQ-0012/T02 completed as 93f48bf (plus formatter fold 806491a): `src/harness/backlog/requests.py` (typed `id`/`requested_on`/`title`, `recorded_on` evidence for labelled unknown dates, extra state fields rejected), offline `harness backlog check-requests` (unique IDs, filename agreement, resolving relative links, `REQ-nnnn/Tnn` references to existing requests, `H1`–`H7` aliases, legacy filenames listed in the inventory), `docs/development_processes/legacy-document-inventory.md` (stated vs first-Git-recording dates, `F1`–`F22` retained, no rename or import), manual `request-metadata.md` and fragment. 25 new unit tests; the full suite is 693 passed with only the seven local podman/ansible failures; hooks and `harness material check` pass; desktop/Pixel-7/390×844 captures at `/tmp/rootgdr-t02-review` reviewed. The check never reads a board token.
- REQ-0011/T10 completed as aaaa2ab: `.env.example` declares `DEV_SHOW_DB`, `AUTH__JWT_SECRET`, `AUTH__BOOTSTRAP_ADMIN_EMAIL` and the documented `root_gdr_dev`/`root_gdr_show` names; the doctor's required-key set is shared with the new test. Verified in a temporary worktree: `.env` copied from the example alone, then `harness dev up` and `dev seed --db work` seeded the reference world; that worktree and its stack were removed afterwards. The main dev stack (work seeded, showcase created but not seeded) keeps serving on 8001/8002.
- Machine preparation with Oscar's explicit approval: `podman` 5.8.7, `podman-compose` 1.6.0 and `ansible` 13.8 installed via dnf; the pinned helper, PostgreSQL, restic and Vikunja images are cached, so the full unit suite is green (709 passed). The WSL kernel refuses nftables inside user namespaces, which breaks netavark on custom networks; `~/.config/containers/containers.conf` sets `firewall_driver = "none"` (user-level, machine-local, documented here only) and rootless custom networks plus port publishing work again. The private deployment state (`~/.config/devin/rootgdr/`, restic repository) did not travel to this machine: real-board operations stay gated on copying or regenerating it.
- Per Oscar's request, tickets now verify with the relevant subset: the whole unit suite (fast), the affected integration tests, and hooks on changed files; full suites remain cycle gates.
- REQ-0012/T05 completed as 737db01: `src/harness/backlog/plan.py` (typed loader of the plan's ticket headings, spec links through the request loader, the deferred REQ-0001/T01 constant), `harness backlog workflow` (owner-side kanban setup that reuses and renames the view's starter buckets to Backlog/In corso/Review/Conclusi with explicit default/done ids; a re-run is a no-op) and `harness backlog import` (dry-run read-only, creates only missing keys, description links the request document and plan section, placement in the given bucket, duplicate keys are an error, existing cards never touched); the client re-reads after Vikunja's empty 304 on an unchanged merge patch. The loader finds 40 executable tickets plus the deferred T01. Verification: loader/import unit tests, a real disposable-board test (36s) covering workflow + no-op re-run, dry-run, 41 created cards with read-back, a manual edit and 12 extra tasks (two pages) followed by a second import that created nothing, and a duplicate-key refusal; 716 unit tests pass, changed-file hooks pass, desktop/Pixel-7 captures unchanged. Live gates: the private state (owner credentials, tooling token, vault) is not on this machine, so the real workflow setup and import remain Oscar's step; the live tooling token also predates the `views_buckets_tasks_get` scope.
- REQ-0012/T06 completed as eeabe98: Towncrier 26.9.0 pinned in the dev group with the Markdown configuration in `pyproject.toml` (fragments `REQ-nnnn-Tnn.<type>.md` in `changelog.d/`, the five approved types, `issue_pattern` keeping the ticket reference, `ignore = []` so an invalid name fails the build), `CHANGELOG.md` with the Keep-a-Changelog header and the towncrier marker, the previous `live` fragment renamed to an approved type, and the npm application counter removed from `package.json`/`package-lock.json`. Tests cover draft-unchanged hashes, fixture aggregation, invalid-name rejection and installed-version coherence; a consuming build was exercised only on a throwaway copy. 720 unit tests pass, changed-file hooks pass, captures unchanged. No version bump, tag, consumption or publication: the first release and its version remain Oscar's decision.
- REQ-0011/T06 completed as 7700423: `src/harness/browser_runtime.py` is the one lightweight source for the browser directory (an explicit `PLAYWRIGHT_BROWSERS_PATH` always wins), `harness browsers` verifies the required revision and binary instead of the directory and reports missing OS libraries distinctly (`--with-deps` only when asked, for CI), `setup.sh` calls the command, `harness doctor` checks the required build, and `FrontendConfig` resolves relative asset directories against the repository root — the different-cwd acceptance run exposed that cwd dependency. Verified: direct pytest from `/tmp` with absolute config/env and no browser-path prefix, the harness frontend run, the full 316-test frontend suite, the override path, 730 unit tests, changed-file hooks and unchanged captures.
- REQ-0011/T04 completed as bab03f4: one bounded settling step in `test/browser.py` (fonts, two animation frames and finite animations; perpetual animations ignored; the deadline is reported) reused by `capture_screenshots`, `capture_url` and the compare measurements, `--settle` (bounded at 15 s) on `screenshot` and `compare`, and `--phone-profile phone390` (390×844) while compare keeps Pixel 7 on both sides. Verified in real Chromium: a delayed transition is complete at capture, a perpetual animation and a stalled request return quickly, a short deadline is reported without over-sleeping; a real member dialog captured fully open at desktop and phone; 390×844 produces a 390×844 image; 732 unit tests; the frontend suite (one pre-existing timing flake in `test_entity_card.py` under CPU contention passes alone — a candidate for the H3 register); changed-file hooks; unchanged worlds captures.
- REQ-0011/T02 completed as aa5db98: typed landmark measurements (match count, rendered, offscreen) and typed issues carrying route/viewport/landmark/side/selector in `test/landmarks.py`, `harness compare --check-landmarks` gating on missing/ambiguous/unexpectedly-hidden landmarks while geometry and pixels stay diagnostics, `optional_on`/`hidden_on` viewport declarations in `seed/prototype_map.yaml` (the world rail is `hidden_on: [phone]`), and `--phone-profile phone390`. Verified on the real DOM: a stale selector exits 1 with its side and selector, an ambiguous selector reports its match count, the declared closed phone rail passes at Pixel 7 and 390×844, geometry-only differences do not gate, and a failed gate marks the artifact run failed; 735 unit tests, the real-DOM frontend test, changed-file hooks, unchanged captures.
- REQ-0011/T03 completed as d47cbd3: `docs/features-request/problems/frontend-flakes.md` records the entity-card lift-back race (exact test, symptom, reproduction under CPU contention, evidence predating the cycle, related tickets, open closure); the historical E2E note keeps its three closed entries and links to the register. No skip, xfail or memorized expected total; the known test still fails when the race occurs (observed once) and passes alone.
- REQ-0011/T05 completed as 293287e: the `payload-budget` pre-commit hook invokes the same `tests/unit/test_payload_budget.py` (one set of thresholds) when an asset, editor source or the bundle, the icon registry and its build inputs, or the budget definition changes; it takes no filenames, runs with `uv run --frozen --no-sync`, and unrelated commits skip it. Verified: the hook runs on a CSS change and skips an unrelated document, an oversized CSS fixture fails both the direct run and the hook with "base CSS (main.css): 68181 raw bytes > 60000", the shared comparison reports group/measurement/limit, and a test guards the hook wiring; 737 unit tests pass.
- REQ-0011/T07 completed as 5bebd40: ruff==0.15.1 in the dev group, matching the ruff-pre-commit revision, so `uv run ruff check` and `uv run ruff format --check` give the hook verdict before a commit; no production dependency, version update or mass reformat. Verified: a frozen fresh sync installs ruff 0.15.1 into a clean environment, the CLI and hooks agree on a staged fixture (E402 error and a reformat), and the repository passes both; 737 unit tests pass.
- REQ-0011/T08 completed as 5626290: `setup.sh --harness` runs `npm ci` from the lockfile (axe-core for the accessibility scan) next to `harness browsers`, resolves the repository from its own path and changes into it, and the accessibility scan keeps failing instead of skipping when axe is missing. Verified: the script runs from `/tmp` for real, `npm ci` installs axe-core from the current lockfile, and a stub-run test proves the harness path calls `npm ci` and `harness browsers` with the repository as the working directory and never `playwright install` or an unlocked `npm install`; 739 unit tests pass.
- REQ-0010/T01 completed as 40931a5: `editorial.DocDetails` composes a reachable summary trigger with a native dialog — right-side sheet on desktop, full screen on phone — that leaves the body, editor state, scroll and URL untouched, returns focus on close, keeps a control's errors in the panel and closes a nested picker before itself; `common.Dialog` gained the `manual` opt-out so a pre-rendered dialog never opens after an unrelated htmx swap. Verified: six component tests.
- REQ-0010/T03 completed as d053b0a: the story page keeps title/summary/text in the document and moved period, progress, tint and the session selection into the panel behind one summary line (the duplicated inline band left the page); `editorial.SessionPicker` filters native checkboxes, keeps chosen sessions visible and writes one hidden multiple select. Verified: five component tests and a real E2E flow with the persisted story, relations and reloaded summary proven through the API.
- REQ-0010/T04 completed as 2d9c8d7 (plus the audit fix b677c61): the page's address, menu position and tint moved into the panel, and an acknowledged slug swaps the address with `window.history.replaceState` and targeted updates instead of `location.replace` — a pending body, the caret, the scroll and the history survive, the API URL and recovery key stay UUID-based, and a refused slug stays in the panel. The browser's `history` is named explicitly because CodeMirror's `history` import shadowed the global. Verified: two E2E flows.
- REQ-0001/T02 completed as b307f37: four CI jobs (checks + unit, frontend, integration, e2e) on `ubuntu-24.04` with frozen lockfiles, SHA-pinned actions, `contents: read`, no secrets, no deployment, always-on teardowns and failure-only diagnostics collected by `tools/ci/collect_artifacts.py` (allowlisted, redacted, 2 MB per file / 10 MB per job, three-day retention). Verified: the exact commands run locally and eleven unit tests over the workflow contract and the collector.
- REQ-0007/T02 completed as 3c0bd65: an atlas calendar beside the canonical native date input (month navigation, `Oggi`, `Cancella`, roving focus with arrows/Home/End/PageUp/PageDown, Enter to pick, Escape to close and return focus), leap-day-safe local dates, the platform picker kept on phone. Verified: eight component tests and an E2E flow asserting the persisted and cleared `realDate` through the API.
- REQ-0010/T02 completed as 88d17f2: a story reports its composed sessions as a read-only additive list (id, title, in-world/real dates, tint); the resolver applies the world check, the draft policy and a duplicate check and raises a typed 422 (`StorySessionsInvalid`, Italian detail) instead of a 500; the serializer filters the references for the reader so a draft title never leaks, while the author still sees it. Verified: five integration tests (references on create/read, clearing, duplicate refused, another world refused, a second master refused on a colleague's draft) plus the stories service and API-matrix suites.
- REQ-0008/T01 completed as 1892b47: `editorial.TintPicker` — the current swatch and Italian name on the trigger, the twelve-tint radio palette in a popover (reusing `common.ChoiceGrid`, borrowing `common/Menu.js` for positioning only), a ring-and-check selected mark, the canonical `p1`–`p12` value, viewport bounds, native Escape/focus return, 44px phone targets and a disabled state; the living kit shows it and `tint-picker.md` records its limits. Verified: seven component tests including opening inside a dialog without closing it.
- REQ-0008/T02 completed as 3cd47db: `editorial.Metadata` renders `kind="tint"` as the picker plus one hidden field, so the autosave registers a single field; a choice writes that field, previews at once and persists as the canonical value, and an applied value (a restored draft) repaints the control; session, story and page panels use it. Verified: four component tests (one field per control, immediate preview under a slow save, a 409 keeping the local choice, an applied value repainting) and a real E2E flow that picks a tint with a pending body edit and finds both stored; 387 frontend, 743 unit and the three feature integration files pass.
- REQ-0009/T01 completed as 8ca3618: `GET /api/worlds/{id}/mentions` now applies each type's own draft policy (a draft belongs to its author) and caps every type before the menu's limit, and `MentionSuggestion` carries the stored mark tokens (`animal`, `shape`) as data. Verified: six integration tests over two users and two worlds (cues, another author's draft hidden, cross-world isolation, the cap, qualified ambiguous names, a hostile name verbatim) plus the existing reference/API-matrix suites and 742 unit tests.
- REQ-0009/T02 completed as 659b120: the `@` menu shows a fixed rectangular mark (`addToOptions`, `icons: false`) with the stored animal written as text, the place shape from whitelisted tokens, the kind mask as fallback and the document tint; long names ellipsize, hostile names stay text, and the arrow/Enter insertion is unchanged. Verified: four component tests and a real E2E flow that picks the character by its animal mark, saves, reloads and finds the rendered mention with `@[Fiamma Rossa]` in the API body; 376 frontend, 742 unit tests and all changed-file hooks.
- Environment note: the docker E2E backend bind-mounts the source but does not reload, so a backend change needs a container restart (`docker restart fastapi_template_harness_<hash>-app-1`) before the E2E suite sees it.
- REQ-0006/T01 completed as 57f5e11: the autosave controller exposes `settle()` (resolves when nothing is left to write, rejects on a failed attempt, drains the in-flight request and the dirty queue, never retries by itself); commands marked `data-requires-saved` (publication and lock) run through it, a failed save cancels them and repeated clicks run once; the component session gained `allow_console_errors` for tests that deliberately drive a 409 or an offline save. Verified: five component tests and a real E2E flow that types and publishes inside the idle window with the API proving the persisted body; 363 frontend, 742 unit and six docbar E2E tests.
- REQ-0006/T02 completed as 3359d96: page-level shortcuts — F2 opens the body when no block is focused, Ctrl/Command+Shift+Enter runs the visible publication command through the same barrier — inert on repeated keydown, IME, text entries, the code editor, autocomplete and open menus/dialogs, with Mod+Enter and the navigator keys preserved; `aria-keyshortcuts` on the commands and an Italian `Scorciatoie` dialog from the `Altre azioni` menu. Verified: seven shortcut component tests, two bar tests, an E2E parity flow with the API payload showing the typed body published by the hotkey; 372 frontend and 742 unit tests.
- REQ-0005/T02 completed as f573694: `editorial.PublicationStatus` replaces the bar's publication pill — a compact rectangular stamp on warm paper with the state colour on the rule and a square marker (forest for published, ochre for draft) and the word always in readable ink; never focusable, identical height in both states, distinct from the tint, story progress and save feedback, with `common.Pill` and the ownership/current-scene badges untouched. Verified: six component tests (state text, differing colours, WCAG contrast ≥ 4.5, rectangular/unfocusable, no geometric jump, no phone overflow), the jinja bar tests, 26 docbar/journey E2E tests, 358 frontend and 742 unit tests, hooks and captures of both stamps.
- REQ-0005/T01 completed as 6aaea45: the document bar's commands are icon-only `common.IconButton`s (edit, lock/unlock, publication, the place's current scene, a new `Altre azioni` trigger) with Italian aria-labels and tooltips naming the action available now; the facts keep their text, the destructive command moved into a labelled `common.Menu` that still opens the same confirmation dialog, and every icon command keeps a 44px phone target. Fixing the `Altre azioni` trigger exposed a popover race (tooltip and menu showing in the same turn; `showPopover` threw `InvalidStateError` when focus returned on close), so the tooltip now reveals on the next frame and yields to an open menu, and a menu closes when an item is activated. Verified: six component tests (labels, current action, menu contents/closing, 44px targets, keyboard reachability), the updated jinja bar tests, seven docbar/flows E2E tests on the docker environment, 352 frontend and 741 unit tests, changed-file hooks (including the payload budget with the new `ellipsis-vertical` icon and the JinjaX CSS sync), and desktop/phone captures.
- REQ-0003/T01 completed as 6a7f851: an empty editable body now keeps a minimum height and shows a CSS-drawn invitation in the document's voice (`Aggiungi una descrizione…`, `Scrivi il resoconto…`, `Inizia a scrivere…`), with the navigator's focus treatment and every open path (double click, Enter/F2, the single-tap Modifica). The copy lives in an attribute and is drawn by CSS, so it never enters the Markdown source, the preview or the API; readers and locked documents get neither copy nor height, and clearing the body restores the target. Verified: nine component tests (invitation, usable target, collapsed caret, all three open paths, the autosave write, reader/locked, clearing), an integration test over all six document pages plus a reader, and a real E2E flow writing an empty recap from Modifica with the body asserted through the API; four component tests fail against the previous CSS; the relevant E2E subset (20), 346 frontend and 739 unit tests pass.
- Machine findings while running the E2E suite on this WSL box: the docker CLI is configured with a Windows credential helper (`docker-credential-desktop.exe`) that cannot execute here, so image builds fail with `error getting credentials`; running the harness with `DOCKER_CONFIG=<dir>` pointing at a minimal config (no `credsStore`) builds and starts the docker environment normally, and `HARNESS_CONTAINER_ENGINE=podman` also starts it. `harness test e2e --fresh` then fails its own database reset because it looks for the compose name `..._db_1` while the container is `...-db-1`; without `--fresh` the freshly created E2E database works. Neither is a repository change.
- REQ-0007/T01 completed as 8c0c8e0: the new-session trigger sends `localIsoDate()` (the browser's local calendar components, never a UTC conversion) as an htmx value; the route persists it before the redirect through a typed `SessionNewRequest`, and an absent value falls back to today in Europe/Rome. Ordinary API/import dates, existing sessions and nullable clearing are untouched. Verified: the real form flow (trigger value, creation, persisted date after reload), a frozen clock at 22:30 UTC proving the Rome fallback on the other side of midnight, a real-browser helper test before/after local midnight, the existing ordering/neighbour tests, 739 unit tests, all 18 changed-file hooks including the payload budget, and desktop/phone captures matching the prototype session study's filled Data reale.
- REQ-0004/T01 completed as 47b2a54: the autosave dot used `align-self: center` against the whole top padding band while the text sat at the band's bottom, so the mark floated above the wording. The dot is now bottom-aligned with the text and lifted by half the difference between the line box (`--leading-normal × --text-sm`) and the dot, putting its painted center on the text's line (measured 0.3px off); the box became a minimum height so a wrapped long message grows downward instead of climbing over the topbar. Component tests derive the dot's center from the real element/text/pseudo geometry in all five states plus wrapped wording, zoom and no-overflow; eight fail against the previous CSS. On the dev stack the crumbs, document bar and page height are identical across hidden/short/long messages at desktop and 390px. 336 frontend, 739 unit, hooks pass.
- REQ-0002/T01 completed as 7f51d22: Chromium paints a fieldset's top border at the legend's vertical center, half the notch below the outline's top edge, so the floated outlined label settled a notch-height above the visible rule. The notch height is now explicit (`--field-label-size-float + --sp-1`) and the outline shifts up by half of it, putting the rule exactly on the box's top edge where the label is centered; the visible outlined rectangle is the full field height again. Component tests assert the label center, the legend center (where the rule is painted) and the box top agree within 0.75px and cover textarea, error, autofill, long label, zoom and a no-movement check; eight of them fail against the previous CSS. 328 frontend tests, 739 unit tests, changed-file hooks and desktop/Pixel-7/390×844 captures matching the prototype's "label on the rule" study.
- REQ-0012/T04 completed as 0473b5d: `harness backlog move|close|reopen|comment` with read-first placement, done-bucket close semantics, never-done reopen, minimal merge-patch `done`, marker-idempotent comments with a timeout re-read, and bounded read-only refusal; the bootstrap's reviewed tooling scopes gain `projects.views_buckets_tasks_get`, which the placement read needs. Verification: 22 client unit tests, the three board integration tests (101s) including a real move/no-op, close into the done bucket, reopen, one comment for a repeated marker, read-only refusal and description preservation, changed-file hooks, and desktop/Pixel-7 captures byte-identical to T02's at `/tmp/rootgdr-t04-review`. Consequence for the live board: the existing server tooling token predates the new scope and must be recreated deliberately (Oscar, credentials) before `move`/`close`/`reopen` read placements there; `create` and `place` still work with it.
