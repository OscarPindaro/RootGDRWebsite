# Prototipi

Prototipi usati per esplorare flussi, gerarchia delle informazioni e identità
visiva prima dell'implementazione in FastAPI + JinjaX + htmx.

Il proprietario ha approvato due modalità il 2026-10-21 (commit `bf4f6ce`):
l'esplorazione statica e l'esperimento composto dall'applicazione. Le regole di
lavoro, il ciclo e i criteri di verifica sono in
[`docs/development_processes/prototyping.md`](../docs/development_processes/prototyping.md).

## Modalità

| Modalità | Quando | Vincoli |
|---|---|---|
| **Esplorazione statica** | Identità visiva o struttura di pagina ancora aperte | File statici, nessun build step, dati hardcoded, nessuna API, non tocca `src/` |
| **Esperimento applicativo** | Aggiunte dentro l'identità dell'atlante, dove controlli, asset e layout reali sono l'incognita | Componenti JinjaX reali serviti dal backend dell'harness, route solo dev sotto `/components/`, fixture tipizzate, nessuna lettura o scrittura della campagna |

L'esperimento applicativo non autorizza un ridisegno, un framework di anteprima
o route di produzione. Il primo esempio è
[`bookkeeping-study/`](bookkeeping-study/README.md).

## Elenco

Esplorazioni statiche:

| Prototipo | Approccio | Identità visiva | Avvio |
|---|---|---|---|
| [`glm-prototype/`](glm-prototype/) | Multipagina reale, shell iniettata da JS | Editoriale/soft | `cd glm-prototype && python3 -m http.server 8090` |
| [`gpt-luna-prototype/`](gpt-luna-prototype/) | Single-page con navigazione hash | Editoriale neobrutalista/Mondrian | `cd gpt-luna-prototype && python3 -m http.server 4173` |
| [`devin-prototype/`](devin-prototype/) | Multipagina reale, shell iniettata da JS | Atlante editoriale/Mondrian funzionale | `cd devin-prototype && python3 -m http.server 4174` |
| [`photo-vector-study/`](photo-vector-study/) | Fotografie → SVG, forme e confronto dei modelli di posa | Personaggi geometrici, contorni marcati | Aprire `photo-vector-study/output/shapes/index.html` |

Esperimenti applicativi:

| Prototipo | Approccio | Identità visiva | Avvio |
|---|---|---|---|
| [`bookkeeping-study/`](bookkeeping-study/) | Pagine reali JinjaX con fixture tipizzate e route dev-only | Atlante editoriale esistente | `uv run harness dev up`, poi `http://127.0.0.1:8001/components/planning` |
| [`document-layout-study/`](document-layout-study/) | Scheda personaggio reale, due disposizioni sullo stesso DOM, server effimero | Atlante editoriale esistente | `uv run python prototypes/document-layout-study/capture.py --serve` |
| [`appearance-study/`](appearance-study/) | Scheda personaggio reale, controlli aspetto sempre visibili o dietro disclosure sul telefono, stesso DOM | Atlante editoriale esistente | `uv run python prototypes/appearance-study/capture.py --serve` |

## Convenzioni

- Un prototipo = una cartella, con il proprio `README.md` che descrive
  **approccio e identità visiva**, abbastanza dettagliato da poter essere
  riprodotto.
- Un prototipo non è una proposta architetturale: la logica server-side
  definitiva vive in `src/backend/`.
- I dati sono finti hardcoded oppure fixture tipizzate dichiarate come tali.
  Nessun fatto inventato sulla campagna del proprietario.
- Ciò che è simulato va detto nell'interfaccia e nel README: stato solo nel
  browser, JSON finto, salvataggi di fixture. Una preferenza simulata non è
  persistenza di dominio. Un salvataggio di dominio richiede un'approvazione
  separata e una verifica isolata sull'ambiente di test, riletta da API o
  database.
- Nessun build step per i prototipi statici: restano file statici. Eventuali
  dipendenze di sviluppo servono soltanto ai test automatici.
- Il README registra modalità, data, revisione di fixture e componenti (commit),
  percorsi degli screenshot desktop e telefono, e il comando usato per produrli.
- La decisione registra l'alternativa scelta, quella rifiutata e il motivo. Il
  comportamento accettato viene promosso nei documenti in
  `docs/features-request/`; il ticket di implementazione legge quelli, non il
  sorgente del prototipo.
- Route, fixture e CSS sperimentali sono dev-only e vengono rimossi oppure
  mantenuti esplicitamente con il loro gating a fine giro.
- Un prototipo applicativo segue i componenti reali: le sue catture valgono per
  la revisione indicata e non sono un riferimento congelato.

## In-application studies

The owner also approved fixture-backed studies inside the actual frontend.
[Bookkeeping and agents](bookkeeping-study/README.md) render through real JinjaX
components and the dev-only application showcase at `/components/planning`.
[Document layout](document-layout-study/README.md) renders one real character
document on the ephemeral component server and compares two arrangements on
the same DOM; its write controls are inert and it uses no application route.
[Phone appearance](appearance-study/README.md) uses the same method to compare
always-visible appearance controls with an explicit phone disclosure, and
records the identity distance, control count, focus order and touch floor.
Neither simulated state writes campaign data or calls providers.
The bounded mode is documented in
[the prototyping process](../docs/development_processes/prototyping.md);
the older standalone studies and their static conventions remain unchanged.
