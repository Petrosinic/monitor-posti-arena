# Guida passo passo — far girare il monitor su GitHub, a PC spento

GitHub esegue il controllo sui suoi server, gratis, **24 ore su 24**, anche a PC
spento. È l'unica copertura nei giorni in cui il PC non viene acceso.

Quando anche l'attività pianificata sul PC è attiva, lo stesso cambiamento può
essere segnalato due volte: hanno memorie separate. Succede solo quando un posto
si libera davvero, cioè l'evento che stai aspettando — meglio un avviso doppio
che un avviso mancato.

---

## Prima di cominciare: due cose da sapere

### 1. Potrebbe non funzionare, e lo scopriamo subito

Lo shop dell'Arena è protetto da **Imperva/Incapsula**, un firewall che decide
chi può leggere le pagine. Dal tuo PC di casa funziona (l'ho verificato). Dai
server di GitHub, che stanno in un datacenter Microsoft, **è possibile che il
firewall blocchi la richiesta**: gli indirizzi dei datacenter sono sorvegliati
molto più di quelli domestici.

Non posso saperlo in anticipo, e non posso provarlo senza il repository. Però la
risposta arriva in **due minuti**: appena fatto il setup si lancia il workflow a
mano e si guarda se legge le 6 recite. Se è bloccato, il controllo diventa rosso
e si vede immediatamente. In quel caso le alternative sono il PC in sospensione
o un piccolo server in cloud.

### 2. Il repository conviene pubblico

GitHub regala **minuti illimitati** ai repository pubblici, mentre a quelli
privati ne dà 2000 al mese. Un controllo costa circa 2 minuti fatturati, e 96
controlli al giorno fanno circa 5800 minuti al mese: con un repository privato
finirebbero in pochi giorni, e per starci dentro bisognerebbe scendere a un
controllo **ogni ora**, troppo lento per prendere un posto che si libera.

Cosa finirebbe pubblico: il programma, i codici delle recite, e lo storico della
disponibilità dei posti. **Niente di personale.** Il token del bot e il tuo
chat_id *non* stanno nei file: li metti nei Secrets, che restano segreti anche
in un repository pubblico.

Se preferisci comunque il privato, si fa — basta cambiare la frequenza. Dimmelo.

---

## PASSO 1 — Crea il repository su GitHub

1. Vai su **https://github.com/new** (se non hai un account, creane uno)
2. **Repository name**: `monitor-posti-arena`
3. **Description** (opzionale): `Avvisi Telegram quando si liberano posti al Teatro Filarmonico`
4. Scegli **Public**
5. **IMPORTANTE**: non spuntare niente in *"Initialize this repository with"* —
   né README, né .gitignore, né licenza. Il repository deve nascere **vuoto**,
   altrimenti il primo invio dà errore.
6. Clicca **Create repository**

Nella pagina che si apre, in alto, c'è l'indirizzo del repository. Copialo:
sarà qualcosa come

```
https://github.com/TUONOME/monitor-posti-arena.git
```

---

## PASSO 2 — Metti i due Secrets

I Secrets sono le credenziali: GitHub le conserva cifrate e non le mostra più a
nessuno, nemmeno a te.

Nel repository appena creato:

1. **Settings** (in alto a destra, nella barra del repository)
2. Nella colonna di sinistra: **Secrets and variables** → **Actions**
3. Pulsante verde **New repository secret**

Crea il primo:

| Campo | Valore |
|---|---|
| Name | `TELEGRAM_BOT_TOKEN` |
| Secret | il token che ti ha dato BotFather |

**Add secret**. Poi **New repository secret** di nuovo, per il secondo:

| Campo | Valore |
|---|---|
| Name | `TELEGRAM_CHAT_ID` |
| Secret | il tuo chat_id |

Il `chat_id` lo trovi in `config.json`, in questa cartella: è il numero nel
campo `chat_id`. Oppure chiedimelo e te lo leggo.

I nomi devono essere **esattamente** quelli, maiuscole comprese.

---

## PASSO 3 — Invia i file

Il repository locale è già pronto e già committato: manca solo l'invio.

Apri PowerShell nella cartella del monitor e lancia questi due comandi, uno
dopo l'altro, sostituendo `TUONOME` con il tuo nome utente GitHub:

```powershell
git remote add origin https://github.com/TUONOME/monitor-posti-arena.git
```

```powershell
git push -u origin main
```

Al primo `push` si apre una finestra del browser che ti chiede di accedere a
GitHub: è normale, è Windows che salva le credenziali una volta per tutte.
Accedi e la finestra si chiude da sola.

Se preferisci, questi due comandi li posso lanciare io: dimmi solo il tuo nome
utente GitHub. L'accesso nel browser però lo devi fare tu.

---

## PASSO 4 — Attiva e prova subito

1. Nel repository, scheda **Actions**
2. Se compare un avviso tipo *"Workflows aren't being run on this forked
   repository"* o un pulsante **I understand my workflows, go ahead and enable
   them**, cliccalo
3. Nella colonna di sinistra clicca **Monitor posti Lago dei Cigni**
4. A destra, pulsante **Run workflow** → **Run workflow**

Attendi un paio di minuti e ricarica la pagina.

### Se il pallino diventa verde ✅

Funziona. Clicca sul run, poi su **controllo**, poi apri lo step *"Controlla la
disponibilita'"*: vedrai le 6 recite con i numeri, esattamente come sul tuo PC.
Su Telegram ti arriva il riepilogo **🟢 Monitor attivo**.

Da questo momento gira da solo ogni 15 minuti, a PC spento. Non devi fare più
niente.

### Se il pallino diventa rosso ❌

Apri il run e guarda lo step *"Controlla la disponibilita'"*. Se trovi righe
tipo `Non riesco a leggere /map.php...` con dentro `_Incapsula_Resource`, è il
caso previsto sopra: il firewall blocca i server di GitHub. Mandami quel testo e
passiamo al piano B.

---

## Come controllare che stia lavorando

**Dal telefono:** ogni 24 ore ti arriva il riepilogo silenzioso *Monitor attivo*
con la situazione delle 6 recite. Se non arriva per due giorni, qualcosa non va.

**Da GitHub:** scheda **Actions**, vedi l'elenco dei run con l'orario. Dovrebbero
essere circa 4 all'ora.

**Dallo storico:** il file `ci-state.json` nel repository viene aggiornato a ogni
cambiamento. Cliccandoci sopra e poi su **History** vedi la cronologia di quando
i posti si sono liberati e per quanto sono rimasti disponibili.

---

## Modifiche che potresti volere

### Controllare più spesso

Nel repository, apri `.github/workflows/monitor.yml`, matita per modificare, e
cambia la riga del cron:

```yaml
    - cron: "*/15 * * * *"            # ogni 15 minuti, sempre (attuale)
    - cron: "*/5 * * * *"             # ogni 5 minuti: il minimo consentito
    - cron: "*/15 22-23,0-7 * * *"    # solo di notte, ore UTC (23-9 italiane)
```

Le ore del cron sono in **UTC**: d'inverno l'Italia è un'ora avanti, quindi
`22-23,0-7` significa dalle 23 alle 9 italiane.

Tieni presente due cose: 5 minuti è il **minimo** che GitHub accetta, e il cron
di GitHub **non è puntuale** — nei momenti di carico i run partono con qualche
minuto di ritardo, a volte di più. È il prezzo del gratis.

### Sorvegliare anche altri settori

Apri `config.ci.json`, matita, e cambia:

```json
  "zones_watch": ["PLATEA A", "PLATEA B", "PALCHI", "BALCONATA"],
```

### Fermare tutto

Scheda **Actions** → **Monitor posti Lago dei Cigni** → menù `...` in alto a
destra → **Disable workflow**. Per riaccenderlo, **Enable workflow**.

Quando avrai comprato i biglietti, ricordati di disattivarlo: altrimenti
continua a girare per sempre.

---

## Convivenza con il monitor sul PC

Puoi tenerli entrambi, ma **riceverai notifiche doppie**, perché i due hanno
memorie separate (`state.json` sul PC, `ci-state.json` su GitHub).

Il mio consiglio: se GitHub funziona, usa solo quello e chiudi la finestra nera
sul PC. Il PC lo tieni per i controlli a mano con `2 - Controllo singolo.bat`.

---

## Problemi tipici

| Cosa vedi | Cosa è | Cosa fare |
|---|---|---|
| `remote origin already exists` | hai già lanciato il comando `git remote add` | `git remote set-url origin https://github.com/TUONOME/monitor-posti-arena.git` |
| `Updates were rejected because the remote contains work` | il repository non era vuoto | cancellalo su GitHub e ricrealo senza README |
| Run rosso allo step *"Salva lo stato"* | manca il permesso di scrittura | Settings → Actions → General → *Workflow permissions* → **Read and write permissions** |
| Run verde ma nessun messaggio Telegram | Secrets sbagliati o con nome diverso | ricontrolla che si chiamino esattamente `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` |
| Run rosso dopo aver usato **Re-run jobs** | «Re-run» riesegue il *commit di allora*, non l'ultimo. Se quel commit è anteriore al file di stato, il salvataggio può fallire | non usare *Re-run jobs*: per un controllo a mano usa sempre **Run workflow** dalla pagina del workflow, che parte dall'ultima versione |
| I run si fermano dopo mesi | GitHub disattiva i cron nei repository inattivi da 60 giorni | i commit di stato arrivano solo quando i posti cambiano davvero, quindi se restasse tutto immobile per due mesi il cron potrebbe essere sospeso. Per il tuo orizzonte (dicembre) non è un problema; basta un *Run workflow* ogni tanto per riattivarlo |
| Notifiche doppie | gira sia su GitHub sia sul PC | chiudi la finestra nera sul PC |
