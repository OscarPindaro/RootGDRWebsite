# Retrospettiva sull'esperienza di sviluppo

Opinione mia (Devin) sul lavoro fatto su questo repository: cosa mi sarebbe
servito, dove le indicazioni erano ambigue, quali strumenti mancavano e cosa
farei adesso per migliorare il ciclo di sviluppo.

Non è un piano di lavoro approvato: è materiale di discussione.

---

## 1. La causa principale delle divergenze visive

Il grosso dei problemi che vedi (card della panoramica diverse, icone giganti,
menu impostazioni bianco, bottone senza bordo) nasce da **una decisione che ho
preso io e che nessuno mi ha chiesto di prendere**: ho tenuto la libreria di
componenti Material già presente (`common/*`, token `--clr-*`) e ho "ricoperto"
il prototipo sopra di essa mappando i token.

`docs/features-request/starting_description.md` dice che il prototipo è il riferimento
per il linguaggio visivo, ma non dice dove finisce il riferimento e comincia
l'adattamento. Le due strade possibili erano:

- **A. Portare il prototipo 1:1** — `styles.css` diventa la base, i componenti
  JinjaX emettono le classi del prototipo (`.quick`, `.card`, `.lede`…), la
  vecchia libreria M3 viene ritirata o riscritta sopra quei token.
- **B. Quello che ho fatto** — tenere i componenti esistenti e sperare che i
  token li rendessero "abbastanza" simili.

Con B il risultato è prevedibile: ogni volta che il CSS di un componente
(es. `common/Button.css` con `border: 1.5px solid transparent`) viene caricato
dopo il foglio editoriale, **vince lui**, e nascono bug come il bordo sparito.
Non è un caso: è la conseguenza strutturale di avere due sistemi sovrapposti.

Se avessi saputo che la parità visiva contava più della continuità col template,
avrei fatto A dall'inizio e non avrei speso tempo a "reskinare" componenti che
andavano invece riscritti.

**Cosa mi serviva da te:** una frase del tipo «il prototipo è la specifica
visiva: le classi CSS e il markup sono il contratto, la libreria M3 esistente
non è un vincolo».

---

## 2. Chiarimenti che mi avrebbero evitato errori concreti

| Ambiguità | Cosa è successo | Cosa mi serviva |
|---|---|---|
| **URL in italiano o in inglese?** Le route HTML sono `/luoghi`, `/sessioni`, `/storie` (italiano) ma `/characters`, `/npcs` (inglese); le API sono tutte in inglese | Ho derivato l'href dall'id di sezione → `/worlds/{id}/personaggi` e `/worlds/{id}/npc` → **404** | Una regola esplicita: «HTML in italiano, API in inglese» **oppure** «tutto in inglese». Con una delle due, l'errore non esisteva |
| **Il prototipo va portato parola per parola o reinterpretato?** | Ho reinterpretato (classi nuove, componenti nuovi) e ho perso la parità | La scelta A/B del punto 1 |
| **Cosa conta come "fatto" per un ticket?** | Ho ottimizzato l'ampiezza (tutti e sei i tipi di contenuto) e ho lasciato indietro la fedeltà visiva e le rifiniture | Un *definition of done* per ticket che includa uno screenshot di confronto col prototipo |
| **Quale pagina del prototipo corrisponde a quale ticket?** | Ho dovuto dedurlo | Una tabella di mappatura ticket → pagina/i del prototipo |
| **Priorità: ampiezza o parità?** | Ho scelto ampiezza | Un ordine di priorità dichiarato |

In generale: **le specifiche descrivevano bene il "cosa", meno il "quanto
fedele"**. Tutti i problemi della tua lista (`image-2` icone giganti, `image-3`
vs `image-4` card, `image-6/7/8` form di creazione) sono questioni di "quanto
fedele", non di funzionalità.

---

## 3. Errori miei, senza attenuanti

1. **Non ho riletto le specifiche dopo le ricompattazioni di contesto.** Il tuo
   appunto è giusto: dopo una compattazione stavo lavorando su una versione
   impoverita delle specifiche. La regola che proponi («riapri i documenti delle
   feature dopo ogni ricompattazione») va messa in `AGENTS.md`.
2. **Ho indovinato invece di verificare.** Gli URL derivati dall'id di sezione
   sono un esempio: avevo il registro delle route sotto mano e non l'ho
   confrontato.
3. **Ho dichiarato un problema in modo troppo largo.** Ho detto che "un prop
   sbagliato passa silenzioso": in realtà i prop *obbligatori* fanno fallire
   JinjaX; il buco riguardava solo gli opzionali. Me ne sono accorto solo
   provandolo.
4. **Mi sono fermato prima.** A un certo punto ho consegnato 17 ticket su 29 e
   ti ho scritto un riepilogo, mentre avevi detto di andare avanti.
5. **Ho usato `select` per animale e tinta** invece delle griglie di icone e
   della striscia di colori del prototipo: funziona, ma è visibilmente un'altra
   cosa.

---

## 4. Harness e strumenti che mi sarebbero serviti

### 4.1 Un confronto visivo automatico prototipo ↔ applicazione

È lo strumento che mi è mancato di più. Avevo `harness screenshot`, ma nessuno
strumento che dicesse «questa pagina è diversa dal prototipo». Ho verificato a
occhio, e a occhio le divergenze strutturali (griglia delle quick card, scala
delle icone, tema dei popover) non si notano in una schermata a 1440px.

Servirebbe: stesse dati nei due lati, stessa viewport, screenshot affiancati e
un diff (pixel o strutturale) con soglia. Anche solo affiancarli in un report
HTML renderebbe evidente `image-3` vs `image-4` in dieci secondi.

### 4.2 Un dataset di riferimento nel repository

Hai chiesto "il boschetto di smeraldo": 4 giocatori (gatto, volpe, topo, tasso),
3 NPC, un paio di radure, 3 sessioni con Markdown vario, delle pagine. Oggi
`harness content seed` costruisce un mondo in codice: va bene per i test, non
per guardare le feature. Un bundle YAML committato (importabile con
`harness content import`) sarebbe il banco di prova condiviso per screenshot,
confronto visivo e test e2e.

### 4.3 Un ciclo di sviluppo più veloce

Il ciclo vero era: modifica → `podman restart` (~6 s) → screenshot. Con
`--reload` (che il compose di sviluppo ha e quello di test no) il ciclo
scenderebbe a meno di un secondo. Un comando tipo `harness dev` che avvia app
con reload + database + seed sarebbe il default di lavoro.

### 4.4 Test Playwright atomici **e** di flusso

Il tuo appunto è la specifica che mi mancava:

- **atomici**: un controllo per volta (il singolo bottone, il singolo toggle);
- **di flusso**: il percorso dell'utente (crea mondo → dalla panoramica vai ai
  personaggi → crea → torna → NPC → crea → …), controllando **anche che la
  panoramica si aggiorni** (i contatori, il diario).

Io ho scritto test di flusso ma pochi atomici, e non ho mai verificato che i
contatori della panoramica cambiassero dopo una creazione. È un buco reale.

### 4.5 Un hook per i link morti

L'hai chiesto tu: sì, si può fare, e in parte c'è già. `test_route_coverage`
risolve ogni href di navigazione e ogni link letterale dei template contro le
route registrate. Manca la parte "hook": oggi è un test, non un controllo che
blocca il commit. Estenderlo a `hx-*` e ai link costruiti con espressioni
(normalizzando `{{ … }}` in un segnaposto) coprirebbe anche il caso generale.

### 4.6 Il checker tipizzato

Concordato come prossimo passo. Prende una classe di bug che nessuno degli
strumenti attuali vede: `{{ character.titl }}` non è un errore per Jinja, è
output vuoto. Da adattare perché `pre_commits/template_types` oggi scopre
`TemplateResponse(...)` e template `.html`, mentre qui si usa
`catalog.render("Component", ...)` e componenti `.jinja`; e perché i prop
passati con `:prop` vanno tipizzati tra componenti (la parte difficile).

### 4.7 Un linter dei token di design

`docs/jinjax.md` dice «ogni valore legge da un token: niente hex, niente px
magici». Non è verificato da nulla. Un controllo su `*.css` dei componenti
(hex letterali, px fuori da bordi/ombre) avrebbe reso più difficile scrivere il
`border: 1.5px solid transparent` che ha causato il bottone senza bordo.

### 4.8 Un inventario componente ↔ prototipo

Il prototipo ha `.quick`, `.card`, `.cover`, `.ledger`, `.story`… con nomi
precisi. Io ho creato componenti con nomi miei (`editorial.Quick`,
`editorial.Card`) e non ho mai prodotto una tabella "classe del prototipo →
componente JinjaX → stato (fedele / adattato / mancante)". Senza quella tabella
le differenze si scoprono solo guardando, cioè tardi.

### 4.9 Un modo per far emergere i prop opzionali sbagliati a monte

JinjaX ignora silenziosamente un argomento non dichiarato. Il mio hook E904 lo
becca staticamente, ma la libreria potrebbe avvisare a runtime. È una modifica
piccola a JinjaX (o un wrapper): varrebbe la pena proporla a monte.

---

## 5. Prossimi passi che proporrei, in ordine

1. **Decidere A o B sulla parità visiva** (punto 1) e, se A, riscrivere i
   componenti editoriali sulle classi del prototipo, ritirando la libreria M3
   dai percorsi che contano. Tutto il resto è secondario finché questo non è
   deciso: senza, ogni rifinitura combatte contro due sistemi che si
   sovrascrivono.
2. **Dataset di riferimento + confronto visivo** (4.1, 4.2): è ciò che rende
   verificabile "quanto fedele", invece di discuterne a parole.
3. **Checker tipizzato** (4.6), come concordato.
4. **Playwright atomici + flussi con verifica degli aggiornamenti** (4.4).
5. **Hook sui link morti** (4.5) e linter dei token (4.7).
6. **Rifiniture note**, in blocco, dalla tua lista: card della panoramica
   attaccate e più larghe che alte, icone dei mark a misura, nessun bordo
   sull'icona, griglia di emoji + striscia di colori nel form di creazione,
   tema scuro per popover e menu (il problema ricorrente del menu bianco),
   overflow orizzontale della rail.
7. **Ciclo di sviluppo con reload** (4.3).
8. **Regola in `AGENTS.md`**: dopo ogni ricompattazione di contesto, rileggere
   `docs/features-request/*.md`; e un *definition of done* per ticket che includa
   screenshot di confronto.

---

## 6. Cosa ha funzionato e vale la pena tenere

Non è tutto da rifare. Le cose che hanno pagato:

- **L'accesso centralizzato** (`src/backend/access/`) e i servizi per feature:
  zero logica di autorizzazione duplicata, e i test di autorizzazione sono
  semplici.
- **La separazione servizio / route / view**: gli stessi servizi servono API ed
  HTML, quindi i test di servizio coprono entrambi.
- **Il seed idempotente** (`harness content import`): riproducibile e già usato
  per screenshot e test.
- **Gli hook**: `model-registry` e `session-commit-guard` hanno impedito errori
  veri; `jinja-globals` (E901–E904) ora copre i bug di render che abbiamo avuto.
- **`render_document`**: un solo punto che risolve le reference e calcola i
  backlink, quindi server e anteprima non possono divergere.

La parte backend/architetturale regge. È la parte visiva che va ripresa con una
decisione esplicita, non con altre toppe.
