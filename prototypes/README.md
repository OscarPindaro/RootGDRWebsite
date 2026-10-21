# Prototipi

Prototipi statici (HTML + CSS + JS, nessun build) usati per esplorare flussi,
gerarchia delle informazioni e identità visiva prima dell'implementazione in
FastAPI + JinjaX + htmx.

Ogni prototipo è autonomo: si apre con un server statico e non tocca
`src/`, `alembic/` o la configurazione del progetto.

## Elenco

| Prototipo | Approccio | Identità visiva | Avvio |
|---|---|---|---|
| [`glm-prototype/`](glm-prototype/) | Multipagina reale, shell iniettata da JS | Editoriale/soft | `cd glm-prototype && python3 -m http.server 8090` |
| [`gpt-luna-prototype/`](gpt-luna-prototype/) | Single-page con navigazione hash | Editoriale neobrutalista/Mondrian | `cd gpt-luna-prototype && python3 -m http.server 4173` |
| [`devin-prototype/`](devin-prototype/) | Multipagina reale, shell iniettata da JS | Atlante editoriale/Mondrian funzionale | `cd devin-prototype && python3 -m http.server 4174` |
| [`photo-vector-study/`](photo-vector-study/) | Fotografie → SVG, forme e confronto dei modelli di posa | Personaggi geometrici, contorni marcati | Aprire `photo-vector-study/output/shapes/index.html` |

## Convenzioni

- Un prototipo = una cartella, con il proprio `README.md` che descrive
  **approccio e identità visiva**, abbastanza dettagliato da poter essere
  riprodotto.
- Nessun build step: i prototipi restano file statici. Eventuali dipendenze di sviluppo servono soltanto ai test automatici.
- Dati finti hardcoded. Un prototipo non è una proposta architetturale: la
  logica server-side definitiva vive in `src/backend/`.

## In-application studies

The owner also approved fixture-backed studies inside the actual frontend.
[Bookkeeping and agents](bookkeeping-study/README.md) render through real JinjaX
components and the dev-only application showcase at `/components/planning`.
Their simulated state never writes campaign data or calls providers.
The bounded mode is documented in
[the prototyping process](../docs/development_processes/prototyping.md);
the older standalone studies and their static conventions remain unchanged.
