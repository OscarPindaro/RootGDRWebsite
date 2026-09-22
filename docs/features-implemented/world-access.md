# Accesso a un mondo (Giocatori)

La sezione **Giocatori** di World Settings è la superficie con cui il
proprietario vede e cambia chi ha accesso al mondo.

## Cosa fa

- Una tabella espone le colonne **Persona**, **Ruolo**, **Stato**, **Azioni**.
  Il proprietario è marcato `Proprietario`, gli altri membri `Master` o
  `Giocatore`, gli inviti in sospeso `In attesa`: ruolo e stato sono Pill, non
  frasi.
- Un `IconButton` con la più nella testata della sezione apre il dialog di
  aggiunta. Il dialog chiede email e ruolo.
- Un'email di un utente esistente aggiunge (o lascia invariato) il membro; un
  email sconosciuta segue il flusso di invito in sospeso già esistente.
- Il proprietario non ha l'azione di rimozione, né la conferma la offre.
- Rimuovi e annulla invito chiedono conferma attraverso `common.ConfirmDialog`,
  non più con `hx-confirm` del browser.

## Come è costruito

- `pages/worlds/WorldMembersTable.jinja/.css` — la tabella. Riusa
  `common.Table`, `common.Pill`, `common.Avatar`, `common.IconButton`,
  `common.Alert`. Confronta `member.user.id` con `world.created_by.id` per
  riconoscere il proprietario.
- `pages/worlds/WorldMemberDialog.jinja/.css` — il dialog di aggiunta. Riusa
  `common.Dialog` e `common.Field`; il form posta a `POST /worlds/{id}/members`
  con `hx-target="#world-members"`, quindi il successo sostituisce la tabella e
  `common/Dialog.js` chiude la superficie.
- `pages/worlds/WorldSettings.jinja` compone tabella e dialog; il dialog e la
  conferma vivono in `#world-member-dialog` e `#world-member-confirm`, caricati
  da htmx.
- `src/backend/worlds/views.py` possiede i frammenti: `world_member_add`,
  `world_member_remove` e `world_invite_revoke` restituiscono
  `WorldMembersTable`; `world_member_dialog`, `world_member_remove_confirm` e
  `world_invite_revoke_confirm` restituiscono le superfici htmx. Il servizio e
  il modello degli inviti restano invariati.
- I frammenti `common.ConfirmDialog` ricevono `hx-delete` / `hx-target` /
  `hx-swap` attraverso `_attrs`, così la richiesta vive sul pulsante di conferma
  e non sulla superficie o su Annulla.

## Usato da

- `pages.worlds.WorldSettings`, per `/worlds/{id}/settings`.

## Limiti

- La tabella scorre in orizzontale su schermo stretto invece di impilarsi: le
  quattro colonne restano allineate, il contenitore ha `overflow-x: auto`.
- Dopo una rimozione o un annulla invito il focus non torna al controllo che ha
  aperto la conferma, perché lo swap ha rimosso quel controllo (stesso limite
  documentato per la revoca admin in [dialog-pattern.md](dialog-pattern.md)).
- Un errore di validazione del server chiude la richiesta con stato non-2xx: il
  dialog resta aperto e mostra il messaggio generico nella regione live, non un
  errore per campo.
