# Richieste, ticket, storico e release — brainstorming

Ricerca del 2026-10-03, seguita dalle decisioni dell'utente qui sotto. Gli esempi
nelle sezioni di brainstorming sono ipotetici; non sono il workflow già migrato.

## Decisioni confermate — 2026-10-03

- Richieste con ID numerici stabili e metadati in testa al Markdown; manuali con
  nomi tematici. Un lavoro da 25 ticket produce 25 esiti, non 25 manuali obbligatori.
- **La board è autorevole per stato e backlog.** Il repo conserva specifiche,
  decisioni, manuale e release note. Non mantenere uno stato corrente duplicato
  nei Markdown: gli esempi precedenti con `status` e tabelle manuali di stato
  descrivono l'alternativa repo-autorevole, ora scartata. Uno snapshot esportato
  può documentare lo storico, ma deve riportare la data e non essere una seconda
  board da aggiornare a mano.
- **Towncrier**, con frammenti Markdown, è lo strumento scelto per le release
  note. La configurazione e l'installazione sono lavoro successivo; oggi non
  sono state aggiunte dipendenze né assegnata una versione.
- **La versione si sceglie alla release**, con conferma dell'utente. Nessun bump
  automatico dell'LLM e nessuna classificazione SemVer vincolante per ticket.
  Un mega-ciclo come quello del frontend può essere una release unica; non
  significa una release per ticket. Il contratto stabile resta da definire.
- Dopo il confronto locale, **Vikunja è la board scelta**. Kanboard resta una
  prova di confronto con dati propri, non un secondo backlog. Il deployment
  continua per ora in questo repo, con SQLite e allegati separati da Root GDR.
  La futura estrazione in un repo di infrastruttura non deve cambiare gli ID.
- La futura harness dei ticket offrirà lettura/lista, creazione, spostamento e
  chiusura tramite **l'API di Vikunja**. Non servono due integrazioni né una
  sincronizzazione bidirezionale. La scelta è confermata; harness, importazione
  dello storico e configurazione Towncrier restano da implementare.

### Ciclo approvato dopo il brainstorming — 2026-10-03

Il ciclo comprende tooling Vikunja, Towncrier, harness, CI/deployment e
REQ-0002–REQ-0010. Importiamo solo i nuovi ticket reali del ciclo; lo storico
viene censito senza migrazione e le demo restano intatte. Vikunja avrà un
nuovo deployment sul server, separato da Root GDR e dalle prove locali.

Per ora l'utente ha rinviato GitHub App e PR obbligatorie: commit locali per
ticket, push su `main` normalmente a fine ciclo, CI su PR/push e deployment
invocato localmente. Il bootstrap server viene prima delle onde parallele,
con fino a tre agenti isolati e review del coordinatore. Nessuna versione,
release o stato simulato delle demo viene attribuito al lavoro reale.

Il deployment di prova è descritto in
[Local task-board trials](../features-implemented/local-task-boards.md).
Il confronto non importa né duplica automaticamente il backlog reale.

## In breve: proposta iniziale (vedi le decisioni sopra)

1. Richieste con un identificatore stabile, data e stato, anche quando non vanno
   avanti. Ticket piccoli dentro una richiesta grande; file separati solo se
   servono davvero.
2. `features-implemented` come manuale del prodotto attuale, con link alle
   richieste di origine. Lo storico dei ticket vive nelle richieste e in Git.
3. Frammenti di release note scritti mentre si lavora, aggregati quando rilasci.
   Il numero di versione lo scegli tu, dopo aver visto cosa cambia.
4. Indici ordinati per data, generabili dai metadati. Nessuna board obbligatoria.
5. Se vuoi provare una board: prima Kanboard o Vikunja. Forgejo ha senso se vuoi
   anche ospitare Git, issue e release; sarebbe molto per avere soltanto le card.

## 1. Il problema del setup attuale

Ho guardato `features-request`, l'indice di `features-implemented`,
`development_processes`, il workflow e Git:

- le richieste mescolano idee, specifiche, feedback, mega-piani, problemi e
  retrospettive; i nomi non seguono una convenzione cronologica uniforme;
- l'indice delle implementazioni è un catalogo tematico, senza date o versioni;
- i ticket F1–F22 stanno in un mega-piano, ma non hanno un registro uniforme di
  approvazione, completamento e prima release;
- le istruzioni attuali richiedono un documento per feature. Durante il megaplan
  alcuni documenti sono diventati resoconti di un ticket o di un audit;
- `pyproject.toml` e `package.json` dichiarano entrambi `0.1.0`, ma nel checkout
  locale non risultano tag Git di release. Questo non prova che l'app non sia
  mai stata distribuita: manca uno storico locale esplicito delle release.

La data del primo commit di un file può aiutare a ricostruire lo storico, ma
non è necessariamente la data in cui hai fatto la richiesta in chat.

## 2. Separare le domande a cui risponde ciascun documento

| Oggetto | Domanda | Dove lo terrei |
|---|---|---|
| Richiesta | Cosa volevamo, perché, e l'abbiamo approvato? | `docs/features-request/` |
| Ticket | Quale pezzo realizziamo e quando è stato verificato? | Dentro la richiesta, o suoi file collegati |
| Feature document | Come funziona oggi questa capacità dell'app? | `docs/features-implemented/` |
| Release note | Cosa cambia per chi usa o aggiorna la versione? | Frammenti, poi changelog |
| Processo/retrospettiva | Come lavoriamo e cosa abbiamo imparato? | `docs/development_processes/` |
| Commit | Quali file e righe sono stati cambiati? | Git |

Una richiesta può produrre molte feature; una feature può evolvere attraverso
molte richieste. Non serve una corrispondenza uno-a-uno tra le due cartelle.
Una release contiene cambiamenti di più richieste, non coincide con uno sprint.

## 3. Numerazione: ID per le richieste, nomi per le funzionalità

Userei un ID stabile come `REQ-0007` e un nome leggibile:
`REQ-0007-document-editing.md`. Il numero è un riferimento, non una priorità,
una versione o una promessa che la richiesta verrà realizzata.

Metadati minimi in testa al Markdown:

```yaml
---
id: REQ-0007
requested_on: 2026-10-03
status: proposed
---
```

Gli stati possibili: `proposed`, `accepted`, `deferred`, `rejected`,
`in-progress`, `completed`, `cancelled`, `superseded`.
- Rinviata: può essere ripresa.
- Rifiutata: abbiamo deciso di non farla, con una breve motivazione.
- Cancellata: era stata accettata, poi il lavoro è stato interrotto.
- Sostituita: rimanda alla nuova richiesta, senza perdere la precedente.

Per i ticket distinguerei `ready`, `in-progress`, `blocked`, `review`, `done`,
`dropped`. Una richiesta parzialmente realizzata resta tale: non si dichiara
completata fingendo che i ticket scartati siano stati eseguiti. Registriamo
l'eventuale riduzione di scope approvata.

Gli ID non si riciclano e non si rinumerano dopo un rifiuto. Il coordinatore li
assegna prima di avviare worktree paralleli, evitando due `REQ-0008` concorrenti.

**Non numererei i documenti di `features-implemented` in ordine di arrivo.**
`image-history.md` resta riconoscibile anche dopo dieci miglioramenti. Gli
aggiungerei riferimenti alle richieste di origine; il suo posto nell'indice
cronologico viene ricavato dai completamenti o dalle release, non dal nome file.

Alternative più semplici: prefisso data nei nomi, oppure solo indice manuale.
Sono valide per cominciare, ma gestiscono peggio richieste dello stesso giorno,
rinvii, collegamenti e lavoro parallelo. L'ID e la data risolvono problemi diversi.

## 4. Un mega-sprint con 25 ticket: quanti documenti?

**25 ticket da tracciare, non necessariamente 25 feature document.**

Per una richiesta grande terrei la specifica e una tabella di avanzamento:

| Ticket | Stato | Completato il | Esito/documentazione |
|---|---|---|---|
| REQ-0007/T01 | done | 2026-10-05 | Aggiornato `document-layout.md` |
| REQ-0007/T02 | review | — | Navigator: test eseguiti, review pendente |
| REQ-0007/T03 | dropped | — | Fuori scope per decisione dell'utente |

Ogni ticket concluso ha poche righe: risultato, verifica, eventuali limiti,
link alla documentazione. Il codice e i dettagli delle modifiche restano in Git.
Se un ticket è lungo o viene delegato, si può estrarre in un file dedicato e
collegarlo; non renderei obbligatori 25 file vuoti o quasi.

I feature document dipendono dalle capacità durature: per esempio uno per
editing, uno per immagini, uno per accesso al mondo. Un fix di focus aggiorna
quello esistente; non crea un nuovo manuale "fix focus numero 3". Un audit o
una migrazione trasversale può avere un resoconto nel processo della richiesta.

Questa proposta cambierebbe la regola attuale di un documento per feature/ticket:
va concordata e poi riscritta nel workflow. Non l'ho cambiata oggi.

## 5. Storico e ordine senza una board

Un indice dovrebbe poter mostrare almeno:
- richieste in ordine di arrivo (`requested_on`, poi ID);
- backlog attivo, rinviate e rifiutate;
- ticket conclusi in ordine di completamento;
- funzionalità per argomento e per prima release.

I dati stanno nei documenti, **una volta sola**. Una futura utility può generare
le tabelle ordinate: non mantenerei a mano sia un registro YAML sia un indice
Markdown con gli stessi stati. Git conserva le revisioni e quindi anche le
transizioni di stato; decisioni importanti hanno una breve motivazione nel testo.

Per distinguere "costruito" da "pubblicato": un ticket può essere `done` e
ancora `unreleased`. La release è provata dal tag e dalle note incluse, non dal
solo fatto che il codice sia su `main`.

## 6. Automatismi o LLM che legge i commit?

Entrambi, ma con compiti diversi:

| Compito | Responsabile proposto |
|---|---|
| Approvare/rifiutare la richiesta e scegliere la versione | Tu |
| Scrivere la specifica e aggiornare l'esito di un ticket | LLM, con verifica |
| Spiegare il cambiamento visibile e i limiti | LLM, testo rivedibile |
| Validare metadati, ID duplicati, link e stati | Controllo deterministico |
| Generare gli indici e aggregare le release note | Strumento deterministico |
| Mostrare file cambiati, commit, diff, tag | Git |
| Stabilire se una richiesta è davvero soddisfatta | Review e test, non Git |

Nel commit basta un riferimento come `[REQ-0007/T01] Fix document focus`.
Così gli hash si possono recuperare senza farli copiare all'LLM dopo ogni commit.
Non si può inserire nel ticket l'hash del commit che sta per includere il ticket
stesso: cambierebbe l'hash. È meglio ricavare quel collegamento dall'ID.

L'LLM legge il diff per scrivere un risultato fedele, ma non ricostruisce ogni
volta tutto lo storico. Un commit non spiega da solo approvazioni, alternative
rifiutate, lavoro ancora incompleto o cosa interessa agli utenti.

## 7. Il sistema di Haystack: confermato

Haystack usa **Reno**: ogni PR normalmente aggiunge un file YAML in
`releasenotes/notes/`, creato con un nome e un suffisso univoco. Si compilano
sezioni come `features`, `enhancements`, `fixes`, `upgrade`; i testi sono
reStructuredText. Le categorie possono essere configurate. Alcune modifiche
solo a test/documentazione tecnica/CI possono essere escluse dai maintainer.

Esempio nello stile di Reno, non una configurazione aggiunta al nostro repo:

```yaml
fixes:
  - |
    Keep the document in place when the save indicator appears.
    Tracked in REQ-0007/T01.
```

Reno legge note e storia Git per raggrupparle nelle release e generare il report.
Ha anche `semver-next`, che suggerisce una versione dalle sezioni: **non lo
userei per decidere automaticamente la nostra versione**.

Punto importante: `fixes` è una categoria del changelog; `patch` è un incremento
di versione. Una release minor può includere molti fix. I due concetti non
vanno saldati in modo rigido.

## 8. Strumenti per le release note

| Strumento | Come scrivi | Come arriva la versione | Per noi |
|---|---|---|---|
| Reno | YAML per modifica, sezioni configurabili | Tag/storia Git; possibile calcolo SemVer opzionale | Più vicino all'idea Haystack; richiede familiarità con tag e reStructuredText |
| Towncrier | Frammenti piccoli, anche Markdown, tipo nel nome | Si può passare esplicitamente `--version` | Molto adatto se vuoi restare in Markdown e scegliere tu il numero |
| Utility nostra | Schema YAML/Markdown scelto da noi | Solo valore approvato dall'utente | Flessibile, ma parser, template e manutenzione diventano nostri |

Towncrier ha una modalità draft e può generare `CHANGELOG.md`. Nella build reale
normalmente consuma i frammenti e li rimuove con Git: restano nello storico e nel
changelog. Reno invece ricostruisce le note usando Git. Non mescolerei i due
modelli con un archivio manuale aggiuntivo.

**La mia preferenza:** Reno se lo YAML di Haystack è un requisito; Towncrier se
lo YAML era solo un esempio e vuoi meno attrito con le nostre note Markdown.
Non scriverei un generatore nuovo prima di provare uno di questi. Neppure serve
adottare tutta la pipeline di release di un progetto grande come Haystack.

## 9. Quante release note per 25 ticket?

Una per cambiamento significativo per utente o amministratore, non una per
commit. Per modifiche solo interne si registra un'esclusione motivata nel ticket.
Se i ticket sono indipendenti, frammenti separati riducono conflitti nei worktree.

Nel megaplan, per esempio:
- "modifica i documenti con la tastiera" è una nota per utenti;
- "icone server-side e font locali" è una nota di distribuzione/performance;
- una rinomina di classe interna non merita necessariamente una voce pubblica;
- più fix dello stesso flusso possono essere riepilogati insieme.

Quindi 25 esiti di ticket, pochi documenti duraturi, e un numero di note di
release proporzionato alle novità reali. Non 25 copie dello stesso changelog.

## 10. Major, minor, patch per una web app personale

SemVer richiede di chiarire cosa prometti di mantenere compatibile. Per Root GDR
proporrei: API usate da integrazioni, bundle esportati/importati, configurazione
di deployment supportata, dati delle campagne e possibilità di aggiornamento.
I componenti JinjaX e le classi CSS interne non sono automaticamente API pubbliche.

| Tipo | Criterio proposto dopo 1.0 | Esempi |
|---|---|---|
| Patch | Corregge comportamento sbagliato senza cambiare il contratto | Bug di salvataggio, focus, overflow, aggiornamento di sicurezza compatibile |
| Minor | Aggiunge capacità o migliora flussi mantenendo compatibilità | Nuovo tipo di contenuto, storico immagini, nuova vista, redesign compatibile |
| Major | Rompe un contratto supportato o richiede un passaggio incompatibile | Rimozione di API usata, vecchi bundle non importabili, perdita di un percorso di upgrade supportato |

Una migrazione Alembic **non è automaticamente una major**: aggiungere una
colonna con migrazione compatibile può accompagnare una minor o una patch.
Un refactor enorme può non cambiare il contratto. Un fix piccolissimo può
romperlo. Il numero non si decide dal numero di righe o di ticket.

Se vuoi chiamare "major" ogni grande redesign per motivi di prodotto, si può,
ma è una convenzione di milestone, non SemVer rigoroso. Va scritto chiaramente.

### Durante 0.x

SemVer considera `0.y.z` sviluppo iniziale: non promette un'API stabile. Per
noi si può scegliere una convenzione pratica: patch per fix, minor per nuove
capacità e cambiamenti incompatibili, segnalando questi ultimi nelle note di
upgrade. `1.0.0` significherebbe "definiamo un contratto e un percorso di upgrade
che intendiamo mantenere", non "non ci sono più bug".

Non scelgo se il megaplan debba diventare `0.2.0` o `1.0.0`: quella è la tua
decisione, dopo una baseline dello stato che vuoi distribuire.

## 11. Versione scelta dall'utente: workflow concreto

1. Mentre implementa, l'LLM scrive note di cambiamento e segnala incompatibilità.
   Non cambia la versione e non pubblica release.
2. Quando vuoi rilasciare, presenta le note non ancora pubblicate e gli eventuali
   passi di upgrade, e ti chiede il numero o l'incremento da applicare.
3. Solo dopo la scelta genera la bozza di changelog, aggiorna la versione e
   verifica i test. Tu puoi rivedere la bozza prima di tag/pubblicazione.
4. Il tag `vX.Y.Z` identifica esattamente il commit della release. Push, deploy e
   pubblicazione restano azioni da autorizzare, non conseguenze automatiche.

Chiederei **una volta per release**, non major/minor/patch ad ogni ticket.
Se preferisci approvare l'impatto per ticket, possiamo registrarlo, ma anche
allora il numero finale riguarda l'insieme dei cambiamenti pubblicati.

La versione va definita in un solo punto autorevole e riportata nell'interfaccia
o nel backend per sapere cosa gira sul server, insieme all'hash della build.
Decidere dove conservarla è un dettaglio di implementazione successivo; ora non
renderei `pyproject.toml` e `package.json` due contatori indipendenti. La revisione
Alembic resta separata: descrive lo schema, non la versione dell'applicazione.

## 12. Board self-hosted: ricerca, non installazione

Non ho misurato RAM/CPU sul tuo server. "Leggera" qui indica quantità di servizi
necessari e semplicità operativa; non prometto un consumo senza provarla.

| Opzione | Licenza verificata | Hosting | Valutazione per un solo sviluppatore |
|---|---|---|---|
| Nessuna board: documenti + indice Git | Nessun servizio aggiuntivo | Il repo | Prima scelta per cominciare; niente sincronizzazione né DB da mantenere |
| Kanboard | MIT | PHP, SQLite oppure DB esterno; Docker disponibile | Board essenziale, subtasks/API; dichiarato in maintenance mode. Buono se vuoi soltanto Kanban |
| Vikunja | AGPLv3 | Frontend/API in un unico binario o container; SQLite possibile | Lista, tabella e Kanban: interessante se sei scettico sulla board ma vuoi un task manager consultabile |
| Forgejo | GPLv3+ dalle versioni 9 | Piattaforma Git con issue, board e release; SQLite supportato | Ha senso se vuoi anche una forge sul server; eccessivo per la sola board |
| WeKan | MIT | Meteor/Node e MongoDB | Ricco, ma più servizi e manutenzione; documenta almeno 1 GB RAM libera e 4 GB totali per server production |
| PLANKA | Fair Use / Pro / Enterprise, dichiarato fair-code | Self-hosting possibile | Non lo classifico come open source nel senso richiesto; le guide che citano soltanto AGPL sono da ricontrollare |

Caveat Kanboard: la pagina requisiti sconsiglia SQLite con Docker/NFS, mentre
quella Docker include un esempio SQLite. La documentazione non è coerente qui:
prima di scegliere il deployment va chiarita la combinazione supportata. Non
presenterei "un container SQLite e basta" come soluzione production garantita.

Se vuoi fare una prova, limiterei il confronto a **Kanboard e Vikunja**, usando
una decina di ticket reali. Nessun workflow di sprint, velocity o story point
necessario: backlog, in corso, review, concluso bastano.

### Evitare due fonti di verità

Una board non ordina automaticamente i Markdown e non genera il changelog.
Se la aggiungiamo, va scelto dove vive lo stato:
- repo autorevole, board come vista/collegamenti; oppure
- board autorevole per stato e backlog, repo per specifiche, manuale e release.

Non scrivere lo stesso stato a mano in entrambi. Una sincronizzazione
bidirezionale sarebbe un progetto aggiuntivo, non un requisito per cominciare.
In ogni caso, DB della board e allegati hanno bisogno di backup; Git non salva
le card di una board esterna senza un'esportazione.

## 13. Come recuperare il passato senza inventarlo

1. Censire i documenti esistenti, distinguendo richieste, decisioni, manuale,
   problemi e retrospettive. Spostamenti/rename solo dopo approvazione.
2. Assegnare ID senza rompere F1–F22 o altri riferimenti già usati: per esempio
   registrare l'epic e mantenere i vecchi ticket come alias locali stabili.
3. Per le date usare quelle esplicite; Git aiuta per il resto. Se la data della
   richiesta non è nota, annotare "prima registrazione in Git" o "importata il",
   non fabbricare una data in cui presumibilmente hai chiesto la feature.
4. Collegare risultati ai commit e alle verifiche disponibili. "Implementato"
   non si presume soltanto perché un documento dice "done".
5. L'inventario operativo dei documenti legacy è
   [legacy-document-inventory.md](legacy-document-inventory.md): date esplicite
   o prima registrazione Git, alias `H1`–`H7`/`F1`–`F22` conservati, nessuna
   rinomina e nessuna importazione nella board.
6. Prima release tracciata: tu scegli versione e commit di baseline. Lo storico
   precedente può avere un riepilogo "sviluppo precedente alla prima release
   tracciata", senza inventare retroattivamente versioni che non sono esistite.

## 14. Decisioni da discutere prima di scrivere ticket di implementazione

- Ti piace avere ID numerici sulle richieste ma nomi tematici sui manuali?
- Accetti che 25 ticket producano 25 esiti e solo i feature document necessari?
- Preferisci frammenti YAML con Reno o Markdown con Towncrier?
- Versione scelta al momento della release, o vuoi anche approvare l'impatto di
  ogni ticket? Quali contratti vuoi dichiarare stabili?
- Cominciamo con un indice nel repo, o vuoi provare una board in parallelo?

La mia partenza sarebbe: ID/date/stati e storico ticket nel repo, frammenti di
release note, scelta manuale della versione. Board solo se la consultazione del
backlog continua a risultare scomoda.

## Fonti primarie consultate

Verificate il 2026-10-03; licenze e modalità di deploy vanno ricontrollate sulla
versione scelta al momento dell'eventuale installazione.

- [Haystack: CONTRIBUTING, sezione Release notes](https://github.com/deepset-ai/haystack/blob/main/CONTRIBUTING.md)
- [Reno: YAML, report, tag e semver-next](https://docs.openstack.org/reno/latest/user/usage.html)
- [Towncrier: frammenti, version esplicita e modalità draft](https://towncrier.readthedocs.io/en/stable/tutorial.html)
- [Towncrier: changelog Markdown](https://towncrier.readthedocs.io/en/stable/markdown.html)
- [Semantic Versioning 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [Kanboard: repository, licenza e maintenance mode](https://github.com/kanboard/kanboard)
- [Kanboard: requisiti](https://docs.kanboard.org/v1/admin/requirements/) e [Docker](https://docs.kanboard.org/v1/admin/docker/)
- [Vikunja: funzionalità e licenza](https://vikunja.io/) e [installazione](https://vikunja.io/docs/installing/)
- [Forgejo: board](https://forgejo.codeberg.page/docs/latest/user/collaboration/project/), [SQLite](https://forgejo.org/docs/latest/admin/installation/database-preparation/) e [licenza](https://forgejo.org/2024-08-gpl/)
- [WeKan: licenza e requisiti](https://github.com/wekan/wekan/blob/main/README.md)
- [PLANKA: licenza attuale nel README](https://github.com/plankanban/planka/)
