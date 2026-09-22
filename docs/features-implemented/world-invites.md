# Inviti a un mondo

Un master può aggiungere al mondo chi ha già un account, oppure invitare
un'email esterna che non è ancora nell'app.

## Cosa fa

- Nella sezione **Giocatori** il dialog di aggiunta accetta un'email e un ruolo.
  Se l'email appartiene a un utente, la membership è aggiunta subito.
- Se l'email non esiste, il mondo registra un invito in sospeso e crea anche
  l'invito di piattaforma: al primo accesso con quell'email l'utente entra nel
  mondo col ruolo scelto, senza altri passaggi.
- Gli inviti in sospeso compaiono nella tabella come righe con stato `In attesa`
  e si possono annullare con una conferma condivisa.
- Il messaggio di esito (invito inviato o membro aggiunto) aggiorna la tabella
  con lo swap, senza ricaricare la pagina.

## Come è costruito

- `world_invites` (`WorldInviteModel`, `src/backend/worlds/models.py`) tiene
  mondo, email, ruolo, scadenza e accettazione; `uq_world_invite_email` evita
  doppioni per lo stesso mondo.
- `src/backend/worlds/invites.py` possiede la logica: `invite_email` (upsert),
  `list_world_invites`, `revoke_world_invite`, `apply_pending_invites`.
- `apply_pending_invites` è chiamata dove nasce o si risolve un utente:
  `login_with_provider`, `register_with_password` e il dev-login. Aggiunge la
  membership se manca e marca l'invito come accettato.
- Le view `world_member_add` e `world_invite_revoke` orchestrano: cercano
  l'utente, altrimenti invitano; l'invito di piattaforma resta in
  `auth.service.create_invitation`.

## Limiti

- L'invito esterno crea anche un invito di piattaforma, quindi l'invitato
  accede all'app intera, non solo al mondo. È il modello di accesso attuale
  (nessuna registrazione libera).
- Non c'è invio email: l'invitato deve essere avvisato a mano, come per gli
  inviti di piattaforma.
- La scadenza usa `auth.invitation_expire_days`; un invito scaduto non viene
  applicato e non è mostrato tra i membri.
