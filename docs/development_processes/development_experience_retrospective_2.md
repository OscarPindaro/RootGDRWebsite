# Retrospettiva sull'esperienza di sviluppo — secondo giro

Opinione mia (Devin) sul lavoro di questa sessione: cosa ho imparato, cosa mi
sarebbe servito, quali strumenti mancano. Materiale di discussione, non un piano
approvato.

---

## 1. Errori miei, senza attenuanti

1. **Ho dichiarato "salvato" qualcosa che non salvava.** Il test e2e asseriva il
   testo a schermo (`document.body.innerText`), che includeva anche il testo
   dell'editor: passava mentre il POST andava su un URL letterale
   (`/worlds/{{ world.id }}/…`) e non scriveva niente. L'ho scoperto solo
   asserendo il valore **via API**. Regola: dopo un'azione che scrive, si asserisce
   l'effetto sul server, non il DOM.
2. **Ho "aggiustato" un bug e ne ho creato un altro.** Ho reso condiviso l'engine
   del database (per il leak di connessioni) e questo ha reso visibile la race
   *commit dopo la risposta*: un redirect htmx può essere seguito prima del
   commit, quindi 404 sulla pagina di destinazione. Ho revertito e documentato i
   due insieme, ma ho speso tempo in una correzione a metà.
3. **Ho creduto a un attributo JinjaX.** `base="/worlds/{{ world.id }}/…"` è una
   stringa letterale: va scritto `:base="'/worlds/' ~ world.id ~ …"`. L'ho visto
   leggendo l'HTML renderizzato, non scrivendo il codice.
4. **Ho inseguito un 404 flaky guardando dalla parte sbagliata.** Pensavo a un
   asset mancante; era il reloader che riavviava l'app mentre pytest scriveva i
   `.pyc` sotto `src/`. Se un test passa da solo e fallisce in suite, il
   sospetto è il processo, non la pagina.
5. **Ho dato per scontato che l'anteprima markdown funzionasse.** Usava `Form()`
   mentre htmx manda JSON: era 422 da sempre, e nessun test la copriva.
6. **Ho toccato file tuoi**: un `git add -A` ha incluso una tua modifica in
   corso. Lo staging va fatto per file.

---

## 2. Cosa ho imparato sul progetto

- **Due stack, due `env_file`.** `podman-compose` carica il `.env` della
  directory corrente: senza `--env-file` esplicito il database di test veniva
  creato con il nome di quello di sviluppo. Rompe in silenzio.
- **`compose up --wait db`** (podman-compose) aspetta che il container sia *up*,
  non che l'entrypoint abbia creato il database: le migrazioni possono partire
  troppo presto.
- **Il reloader di uvicorn osserva `src/`**: pytest che scrive `__pycache__` lo
  fa ripartire a metà suite.
- **JinjaX**: `{{ }}` dentro un attributo quotato è letterale, `:prop="expr"` è
  l'espressione; e i componenti si annidano come `CallBlock`, cosa che il
  checker tipizzato non conosceva.
- **htmx + `json-enc`**: le route che ricevono form prendono JSON (Pydantic), mai
  `Form()`.
- **Il container gira non-root**: un bind mount in scrittura va reso scrivibile,
  o diventa un volume.
- **Playwright**: la cache in `~/.cache` non è affidabile in questo ambiente.

---

## 3. Harness che mi sarebbero servite

1. **`harness doctor`** — un controllo unico: stack attivi, porte libere,
   connessioni Postgres disponibili, browser Playwright installato, `.env`
   valido, registrazione replay rimasta accesa. Metà delle diagnosi di oggi
   sarebbe stata una riga.
2. **`harness env up` riparatore** — quando il compose cambia (mount, comando)
   non ricrea il container; e un `up` fallito fa `down`, perdendo lo stato. Serve
   un `--recreate` esplicito e un fallimento che non distrugge.
3. **`harness smoke`** — dopo l'avvio, colpisce le pagine principali e dice
   subito "l'app è rotta", invece di farlo scoprire dai test e2e.
4. **`harness test e2e --fresh`** (o un database per run) — gli e2e scrivono sul
   database e non puliscono: 108 mondi, dump lenti, e un test che prende
   `worlds[0]` dipende da cosa ha lasciato la run precedente.
5. **`harness logs --request-id`** — i log sono già JSON e correlati, ma per
   leggerli si fa `podman logs | grep`. Un filtro per request/trace id chiude il
   cerchio dell'osservabilità senza introdurre Prometheus.
6. **Un'asserzione onesta nei test e2e**: un helper `expect_api(...)` accanto a
   `session.page`, così l'errore del punto 1 non è possibile per distrazione.
7. **`harness dev up --no-build`** — oggi ricostruisce sempre l'immagine, anche
   quando è cambiato solo un mount.
8. **Replay**: un filtro per le richieste di servizio, una modalità "solo
   letture", e un `replay diff` fra due registrazioni (prima/dopo un fix).

---

## 4. Hook che valgono più di un test

1. **`{{ }}` in un attributo quotato** di un componente `.jinja`: è un grep, e
   il bug del punto 1.3 non torna più. Il più concreto di tutti.
2. **`Form()` in una route raggiunta da htmx**: quasi tutte le form dell'app
   sono JSON-encoded; l'hook eviterebbe il 422 silenzioso.
3. Una riga nelle convenzioni di test: **una scrittura si verifica via API**.

---

## 5. Cosa vorrei dal progetto (non harness)

- **`data-testid` sugli elementi interattivi** (submit, voci di menu, campi): i
  selettori registrati oggi cadono su `:has-text`, che si rompe appena cambia la
  copy. È il singolo cambiamento che rende robusti i test generati dal replay.
- **Definizione di "fatto" che includa l'asserzione via API** per ogni scrittura.
- **Chiudere i due bug aperti** (engine per richiesta, commit dopo la risposta):
  sono in `AGENTS.md` come "da fare insieme".

---

## 6. Prossimi passi, in ordine

1. I due bug di connessione/commit: bloccano la fiducia nei test.
2. `harness doctor` e `harness smoke`: costo basso, valore alto.
3. L'hook sui `{{ }}` negli attributi quotati.
4. `data-testid` sugli elementi interattivi, poi rigenerare i test dal replay.
5. Isolamento del database negli e2e.
6. `harness logs --request-id`.
