# Piano — feedback sessione 2026-09-21

Deriva da `feedback-2026-09-21.md`. Sono esclusi i punti che richiedono un
redesign grafico (2 creazione mondo, 21 metadati sessione, 22 storie e pagine).
Ogni ticket si chiude da solo: implementazione, test, commit.

## Ticket

| # | Punti | Cosa | Dove |
|---|-------|------|------|
| T1 | 1 | Trigger menu utente su una riga, chevron a destra | `layout/UserMenu.css` |
| T2 | 3 | Copertina mondo coerente tra lista e impostazioni | `editorial/ImageEditor.css`, `WorldSettings.jinja` |
| T3 | 4, 11 | Pulsante "Storico" fuori dall'immagine | `editorial/ImageEditor.jinja/.css` |
| T4 | 5, 15 | Indicatore "Salvato" unico per documento, con colore | `layout/Page.jinja`, `js/editor/index.js`, componenti editorial |
| T5 | 6, 7, 12 | Label Nome/Descrizione/Titolo, via "Markdown", via titolo "Identità" | `WorldSettings.jinja`, `DocIdentity.jinja`, pagine editor |
| T6 | 13, 16 | Descrizione senza scroll orizzontale e subito sotto la breve | `main.css`, pagine editor |
| T7 | 17, 18 | Menu menzioni "@" stilizzato; menzione identica in render ed edit | `main.css`, `js/editor/live-preview.js` |
| T8 | 19 | Scegliere forma/tinta non deve aprire l'area del nome | `js/editor/index.js` |
| T9 | 20 | Pillola "Scena corrente" fuori dalle azioni della docbar | `PlaceDetail.jinja`, `main.css` |
| T10 | 10 | Pulsanti del masthead in verticale | `main.css` |
| T11 | — | Button group M3 connected: due opzioni sono due bordi; testo di fianco | `common/ButtonGroup.css`, `Settings.jinja` |
| T12 | 8, 9 | Invito membro a utente esistente e a email esterna; banner vicino al form | `worlds/*`, `auth/*`, `WorldSettings.jinja` |

## Note di implementazione

- **T1**: `common.Button` avvolge il contenuto in `.btn-label`; il `display:flex`
  di `.user-menu .btn` vede un solo figlio. Fix locale: `.user-menu .btn-label
  { display: contents; }`.
- **T2**: la lista usa `16 / 7` (`.cover__media`), le impostazioni `4 / 5`
  (`image-editor__surface`). La copertina del mondo è orizzontale nella lista:
  allineo la preview delle impostazioni. Solo `owner_kind == "world"`.
- **T3**: `image-editor__history-trigger` è `position:absolute` sull'immagine.
  Lo sposto in una riga di comandi sotto la superficie.
- **T4**: ogni blocco (identità, sommario, corpo) ha il suo `.autosave-status`,
  ma condividono lo stesso controller per URL: lo stesso testo compare più
  volte. Un solo indicatore per pagina, in cima, con stato colorato.
- **T7**: il menu menzioni è l'autocomplete di CodeMirror
  (`.cm-tooltip-autocomplete`), non `.mention-menu` (che resta del prototipo).
  In modifica la menzione è testo rosso, a riposo è una pillola: le do la stessa
  resa.
- **T8**: `mountAll` apre in editing il primo `[data-doc-field]` quando
  `data-auto-edit='true'`; il reload dopo il salvataggio di forma/tinta lo
  riattiva. L'auto-edit deve valere solo al primo caricamento della scheda.
- **T11**: `.button-group-connected .button-group-input:checked + .btn` forza
  `border-radius: var(--radius-full)`, che trasforma il segmento selezionato in
  una pillola. Va rimosso: i due segmenti restano due bordi.
- **T12**: non esiste invio email. L'invito esterno crea un invito di
  piattaforma legato al mondo; al primo accesso con quell'email l'utente entra
  nel mondo col ruolo scelto. Il banner di errore si sposta accanto al form.

## Test

- Unit/Jinja: rendering dei componenti toccati (`tests/unit/jinja/`).
- Integration: invito membro, settings view (`tests/integration/`).
- E2E: autosave, image editor, flussi membri (`tests/e2e/`).
- Screenshot desktop + telefono contro `prototypes/devin-prototype/`.
