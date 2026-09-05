# Deployment attuale di Devin Telegram Bot

Questo documento descrive il deployment realmente presente sul server `pinball-server`. È un prototipo funzionante, non una soluzione generale o definitiva.

## Architettura

```text
Telegram
    │ long polling HTTPS
    ▼
devin-telegram-bot.service
    │ avvia un processo per ogni prompt
    ▼
devin --permission-mode dangerous --print ...
    │
    ▼
/home/pinball/RootGDRWebsite
```

Il processo Python del bot rimane sempre attivo. Per ogni messaggio Telegram avvia un nuovo processo Devin CLI, ne cattura stdout e stderr, invia la risposta a Telegram e termina il processo figlio. I turni successivi usano `--continue`.

## Host

- Server: `pinball-server.local`
- Utente: `pinball`
- Sistema: Fedora 43
- Repository: `/home/pinball/RootGDRWebsite`
- Python: 3.14
- Runtime Python: uv
- Supervisione: user service systemd con lingering abilitato

Sono installati Git, uv, Devin CLI, bubblewrap e socat. Bubblewrap e socat non vengono però usati dal processo Devin nella configurazione finale, per il limite descritto nella sezione sui permessi.

## File sul server

```text
/home/pinball/RootGDRWebsite/
/home/pinball/.config/devin-telegram-bot/env
/home/pinball/.config/systemd/user/devin-telegram-bot.service
/home/pinball/.config/devin/config.json
/home/pinball/.local/share/devin/credentials.toml
```

Il file `env` contiene il token Telegram e ha permessi `0600`. Il token non è nel repository e non viene passato ai processi Devin figli.

Variabili principali:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_USER_ID
DEVIN_PROJECT_DIR=/home/pinball/RootGDRWebsite
DEVIN_SANDBOX=false
DEVIN_PERMISSION_MODE=dangerous
```

## Servizio systemd

Il servizio è installato come user service:

```text
~/.config/systemd/user/devin-telegram-bot.service
```

È abilitato all'avvio del server:

```bash
systemctl --user enable devin-telegram-bot.service
```

Comandi operativi:

```bash
systemctl --user status devin-telegram-bot.service
systemctl --user restart devin-telegram-bot.service
systemctl --user stop devin-telegram-bot.service
journalctl --user -u devin-telegram-bot.service -f
journalctl --user -u devin-telegram-bot.service -n 100 --no-pager
```

Il lingering dell'utente `pinball` permette al servizio di restare attivo senza una sessione SSH aperta.

## Isolamento systemd

Il servizio applica queste protezioni:

- `NoNewPrivileges=true`
- filesystem di sistema in sola lettura
- home directory in sola lettura per impostazione predefinita
- `~/.ssh` non accessibile
- directory contenente il token Telegram non accessibile al processo
- repository e directory runtime strettamente necessarie rese scrivibili
- processi figli terminati insieme al servizio
- device privati e accesso a kernel, clock, hostname e control group limitato

Le directory scrivibili sono:

```text
/home/pinball/RootGDRWebsite
/home/pinball/.local/share/devin/cli
/home/pinball/.local/share/devin/mcp
/home/pinball/.cache/devin
/home/pinball/.config/devin
```

## Modelli

All'avvio il bot esegue:

```bash
devin models list --format json
```

Il catalogo attuale contiene 46 famiglie e 210 varianti. `/model` mostra prima le famiglie e poi le varianti, con paginazione. Il modello selezionato viene passato a ogni processo con `--model`.

## Logging

stdout e stderr del bot sono raccolti dal journal systemd. I log includono:

- modello selezionato
- nuovo turno o continuazione
- PID del processo Devin
- durata
- exit code
- dimensione di stdout e stderr
- cancellazione e consegna della risposta

Non vengono registrati prompt, risposte, token Telegram o credenziali.

## Come è stato copiato il codice

Il repository è stato trasferito dalla macchina di sviluppo tramite archivio tar su SSH, escludendo `.venv`, cache e file `.env`. Le modifiche del bot non erano ancora committate, quindi sul server il working tree contiene file modificati e aggiunti.

Gli aggiornamenti successivi sono stati copiati manualmente con `scp`, seguiti da:

```bash
uv sync --frozen
systemctl --user restart devin-telegram-bot.service
```

Questo processo non è riproducibile né adatto a una distribuzione generale. Non esiste ancora un pacchetto versionato o un comando di installazione.

## Compromesso sui permessi

Questo è il limite principale del deployment.

Con `devin --sandbox`, Devin CLI forza la modalità `autonomous`. Nella versione installata, gli strumenti diretti di modifica file continuano però a chiedere conferma. In modalità non interattiva `--print`, la conferma non può essere fornita e le modifiche vengono rifiutate.

Anche `Write(**)` e un permesso assoluto per il repository non hanno risolto il problema. Inoltre, combinare `--sandbox` con `--permission-mode dangerous` non funziona: la CLI ignora `dangerous` quando il sandbox è attivo.

Per permettere modifiche non presidiate, il server usa quindi:

```text
DEVIN_SANDBOX=false
DEVIN_PERMISSION_MODE=dangerous
```

L'isolamento viene spostato dal sandbox Devin al servizio systemd. Questo permette al bot di funzionare, ma rimane un compromesso: il processo Devin deve poter leggere le proprie credenziali per autenticarsi e la modalità `dangerous` non offre approvazioni interattive via Telegram.

## Limiti attuali

- Un solo repository, scritto nei file di configurazione e nel servizio.
- Un solo utente Telegram.
- Un solo turno attivo.
- Stato del modello e della conversazione solo in memoria.
- `--continue` riprende l'ultima sessione della directory, non un ID persistito esplicitamente.
- Nessun progresso strutturato durante il lavoro.
- Nessuna approvazione remota di tool o comandi.
- Nessun deployment versionato o rollback applicativo.
- Il bot è incluso nel repository applicativo e installa molte dipendenze non necessarie.
- Il servizio contiene path specifici dell'utente `pinball`.

## Direzione consigliata

La soluzione definitiva dovrebbe essere un progetto standalone `devin-telegram`, installabile separatamente dal repository controllato.

Dovrebbe includere:

1. configurazione XDG indipendente;
2. registro di repository esplicitamente autorizzati;
3. sessioni persistite per repository;
4. pacchetto e comando di installazione del servizio;
5. backend intercambiabili;
6. ACP come backend principale;
7. richieste di permesso trasformate in pulsanti Telegram;
8. streaming di messaggi, tool e stato;
9. niente modalità `dangerous` come requisito normale.

Il backend subprocess attuale può restare come fallback semplice, ma ACP è la strada corretta per un bot generale e sicuro.
