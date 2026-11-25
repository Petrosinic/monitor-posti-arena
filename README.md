# Monitor posti — Il Lago dei Cigni, Teatro Filarmonico

Sorveglia le **6 recite** del Lago dei Cigni sullo shop della Fondazione Arena e
manda un messaggio **Telegram** appena cambia qualcosa in **Platea A / Platea B**.

---

## 1. Come funziona (e perché non confronta immagini)

La mappa dei posti sul sito non è un'immagine statica: viene disegnata a partire
da un JSON che il sito stesso scarica. Il programma legge **quel JSON**:

```
https://shop.arena.it/map.php?cmd=orchestrator&pcode=<recita>&tcode=vt0020008&operator=arenaverona
```

La risposta contiene, zona per zona, il campo `availability` con il **numero
esatto di posti liberi**. È molto più affidabile di un confronto di pixel: non
ci sono falsi allarmi per un pop-up, un banner cookie o un colore sfumato, e si
sa subito *quanti* posti si sono liberati e in quale zona.

Lo shop è protetto da Imperva/Incapsula, quindi una semplice richiesta HTTP
viene rifiutata. Per questo il programma usa **Playwright + Chromium** con un
profilo persistente: apre una pagina vera dello shop una volta, poi interroga il
JSON dall'interno di quella pagina. Un ciclo completo = 1 navigazione + 6
chiamate JSON, con 1,5–3,5 s di pausa fra una recita e l'altra per non pesare
sul server.

---

## 2. Telegram: una cosa importante sul numero di telefono

**Telegram non permette di inviare messaggi a un numero di telefono.** Non
esiste nessun modo (né ufficiale né affidabile) per far arrivare un messaggio a
un numero di cellulare partendo da un programma: i bot possono scrivere solo a
chi ha aperto una conversazione con loro.

La soluzione è un bot personale tuo, che richiede 2 minuti una volta sola.
I messaggi arriveranno comunque sul telefono, con la notifica push normale.

**→ Procedura completa, passo per passo: [GUIDA TELEGRAM.md](GUIDA%20TELEGRAM.md)**

In breve:

1. Su Telegram cerca **@BotFather**, scrivi `/newbot`, dai un nome (es. *Posti
   Arena*) e uno username che finisca per `bot` (es. `posti_arena_np_bot`).
   BotFather risponde con un **token**, tipo `8123456789:AAHk...`
2. Doppio clic su **`1 - Configura Telegram.bat`**: ti chiede il token a
   schermo, basta incollarlo. Non serve modificare `config.json` a mano.
3. Il programma ti stampa il link del tuo bot: aprilo sul telefono e premi
   **START**. Il `chat_id` viene trovato e salvato da solo, e ti arriva un
   messaggio di conferma.

> Il token è una password: non mandarlo a nessuno. Se ti scappa, in BotFather
> fai `/mybots` → il tuo bot → *API Token* → **Revoke current token**.

> Se preferisci le notifiche via email o SMS invece di Telegram, si può
> cambiare: dimmelo e adatto la parte di invio.

---

## 3. Avvio

| File | Cosa fa |
|---|---|
| `1 - Configura Telegram.bat` | collega il bot (una volta sola) |
| `2 - Controllo singolo.bat` | stampa la situazione attuale di tutte le recite ed esce |
| `3 - Avvia monitor.bat` | **il programma vero**: controlla ogni ~3 minuti, per sempre |

`3 - Avvia monitor.bat` va lasciato aperto. Se Python o la rete si piantano, la
finestra riparte da sola dopo 60 secondi. Per fermarlo: chiudi la finestra o
premi `CTRL+C`.

Da riga di comando, aprendo PowerShell nella cartella del monitor, è lo stesso:

```powershell
python monitor_arena.py watch
```

---

## 4. Quando ti scrive (e quando no)

* ✅ **Posti liberi** — una zona sorvegliata passa da 0 a >0, o il numero
  aumenta. Il messaggio dice zona, quantità, valore precedente e ha il link
  diretto all'acquisto.
* ⚠️ Se i posti liberi sono **meno di 2** (`min_seats`) il messaggio arriva
  comunque, ma marcato: utile perché spesso i posti si liberano uno alla volta.
* ❌ **Posti spariti** — tornano a 0 perché li ha presi qualcun altro. Serve a
  capire con che velocità girano. Si disattiva con `"notify_on_gone": false`.
* 🎟 **Promemoria** — se i posti restano liberi, te lo ricorda ogni 45 minuti
  (`repeat_minutes`), per non perdere l'occasione se non hai visto la notifica.
* 🟢 **Monitor attivo** — riepilogo silenzioso all'avvio e poi ogni 12 ore, così
  sai che il programma sta girando davvero e non è morto in silenzio.
* ⚠️ **Monitor in difficoltà** — se tre cicli di fila vanno in errore.

Nessun messaggio doppio: lo stato di ogni zona è salvato in `state.json` e si
avvisa solo sui **cambiamenti**. Le gallerie e gli altri settori vengono letti e
registrati nel log, ma **non** generano notifiche (sono già in vendita).

Gli avvisi di "posti liberi" suonano **sempre**, anche di notte. Solo i messaggi
di servizio (riepilogo, posti spariti nelle ore notturne) arrivano silenziosi,
secondo `quiet_hours`.

---

## 5. Configurazione (`config.json`)

| Campo | Significato |
|---|---|
| `zones_watch` | zone sorvegliate. Confronto per sottostringa: `"PLATEA"` copre A e B insieme. Aggiungi `"PALCHI"` o `"BALCONATA"` se ti interessano |
| `min_seats` | quanti posti ti servono: 2. Serve solo a marcare il messaggio, non a filtrarlo |
| `interval_seconds` | 180 = un controllo ogni 3 minuti |
| `jitter_seconds` | 60 = aggiunge 0–60 s casuali, così le richieste non sono a orologeria |
| `repeat_minutes` | ogni quanto ripetere il promemoria se i posti restano |
| `notify_on_gone` | avvisare anche quando i posti vengono ripresi |
| `heartbeat_hours` | ogni quanto il riepilogo "sono vivo" |
| `quiet_hours` | `[1, 7]` = fra l'1 e le 7 i messaggi di servizio sono silenziosi |
| `headless` | `false` apre una finestra Chromium visibile, utile se qualcosa non va |
| `events` | le recite. Si rigenerano con `python monitor_arena.py discover` |
| `show_filter` | lo spettacolo da cercare con `discover` |

**Quanto spesso controllare.** 3 minuti è un compromesso ragionevole: abbastanza
frequente per prendere un posto che si libera, abbastanza raro da non somigliare
a un attacco. Scendere sotto il minuto, per 6 recite, significa bussare molto
spesso a un sito protetto da un firewall applicativo: rischi di farti bloccare
l'IP e di non ricevere più nulla. Se vuoi, si può scendere a 60–90 secondi solo
per il 13 dicembre lasciando le altre più lente.

---

## 6. Farlo girare a PC spento (GitHub Actions)

Il monitor può girare sui server di GitHub ogni 15 minuti, gratis, senza che il
tuo PC sia accesso. In quel caso non si usa `watch` ma il comando `once`, che
fa un solo controllo e poi esce: la ripetizione la fa lo scheduler di GitHub.

I file sono già pronti: `.github/workflows/monitor.yml`, `config.ci.json`,
`requirements.txt`.

**→ Procedura completa: [GUIDA GITHUB.md](GUIDA%20GITHUB.md)**

Avvertenza importante: lo shop è protetto da Imperva/Incapsula e non è detto che
accetti le richieste dai datacenter di GitHub. Si verifica in due minuti con un
run manuale, ed è il primo passo della guida.

---

## 7. Partire da sola all'accensione del PC

1. `Win + R` → `shell:startup` → Invio
2. Trascina dentro **`3 - Avvia monitor.bat`** tenendo premuto `ALT`
   (crea un collegamento)

Il monitor parte a ogni accesso a Windows. Nota: deve esserci corrente, rete e
il PC acceso — se lo spegni la notte, in quelle ore non controlla nulla.

---

## 8. Situazione al 25 novembre 2026

| Recita | Platea A | Platea B | 1ª Gall. | 2ª Gall. |
|---|---|---|---|---|
| dom 13/12 15:30 | 0 | 0 | 0 | 0 |
| mer 16/12 19:00 | 0 | **1** | 32 | 72 |
| ven 18/12 20:00 | 0 | 0 | 6 | 15 |
| sab 19/12 15:30 | 0 | 0 | 2 | 36 |
| dom 20/12 15:30 | 0 | 0 | 5 | 7 |
| gio 31/12 19:30 | **70** | **109** | 91 | 74 |

Due cose utili subito:

* la recita che mi hai mandato (**13 dicembre**) è l'unica completamente
  esaurita in tutti i settori;
* il **31 dicembre** ha platea larghissima disponibile adesso — è il Capodanno,
  quindi probabilmente a prezzo maggiorato, ma i posti ci sono;
* il **16 dicembre** ha **1 posto** in Platea B in questo momento: se ne serve
  un secondo, è la recita da tenere d'occhio più da vicino.

---

## 9. File prodotti

* `monitor.log` — storico di tutti i controlli, con la disponibilità vista ogni
  volta. Utile per capire *quando* si liberano i posti.
* `state.json` — ultimo valore noto per zona. Cancellalo per azzerare la memoria
  (il primo controllo successivo non manderà allarmi, solo il riepilogo).
* Il profilo di Chromium sta in `%LOCALAPPDATA%\MonitorArena\chrome-profile`,
  **fuori** da OneDrive, per non far sincronizzare centinaia di MB di cache.

---

## 10. Requisiti (già installati su questo PC)

* Python 3.14
* `requests`
* `playwright` + Chromium

Se servisse rifarlo su un altro computer:

```powershell
python -m pip install requests playwright; python -m playwright install chromium
```

---

## 11. Avvertenze

* Il programma **non compra** niente: legge la disponibilità e ti avvisa.
  L'acquisto lo fai tu dal link nel messaggio, con il tuo account.
* I posti in platea per una recita esaurita si liberano per rinunce o
  prelazioni scadute: può succedere in qualunque momento, anche a pochi giorni
  dalla data. Non è garantito che succeda.
* Se il sito cambia il funzionamento della mappa, il programma te lo dice con il
  messaggio "Monitor in difficoltà" invece di restare zitto. In quel caso va
  adattato il modo in cui legge il JSON.
* Legge solo pagine pubbliche dello shop, alla frequenza di un utente attento.
  Non elude il firewall del sito e non simula più utenti.
