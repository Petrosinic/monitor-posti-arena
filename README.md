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

**Regola unica: un messaggio arriva solo se, fra un controllo e il precedente,
i posti liberi in una zona sorvegliata sono AUMENTATI.** Nient'altro. Niente
promemoria, niente riepiloghi periodici, niente conferme che è vivo.

Il confronto è fra il numero di adesso e quello del controllo precedente:

| Prima | Adesso | Cosa significa | Messaggio |
|---|---|---|---|
| 0 | 2 | si sono liberati due posti | **sì** |
| 2 | 5 | se ne sono liberati altri tre | **sì** |
| 5 | 3 | qualcuno ne ha comprati due | no |
| 3 | 0 | comprati tutti, di nuovo esaurito | no |
| 1 | 1 | non è successo niente | no |

Le diminuzioni non vengono segnalate di proposito: significano che altri hanno
acquistato, non c'è niente da fare e non cambiano nessuna tua decisione.

* 🎟 **Posti liberi** — l'unico avviso ordinario. Dice giorno, ora, zona,
  quantità, il valore precedente, e ha il link alla pagina dei biglietti.
* ⚠️ Se i posti liberi sono **meno di 2** (`min_seats`) il messaggio arriva
  comunque, marcato *«per 2 biglietti non basta»*: spesso i posti si liberano
  uno alla volta, e il secondo può arrivare poco dopo.
* ⚠️ **Non riesce a leggere il sito** — se un controllo fallisce del tutto. Al
  massimo uno ogni 6 ore (`failure_alert_hours`). Questo non è un aumento di
  posti, ma serve: senza, un monitor rotto e un monitor che non ha niente da
  dire sarebbero indistinguibili, perché entrambi tacciono.

Zone sorvegliate: **Platea A, Platea B, Palchi, Balconata**. Le due gallerie
vengono lette e registrate nel log, ma **non** generano notifiche: hanno
disponibilità larga e cambiano continuamente.

Nessun messaggio doppio: l'ultimo valore di ogni zona è in `state.json` (sul PC)
o `ci-state.json` (su GitHub), e il confronto è su quello.

Gli avvisi di posti liberi suonano **sempre**, anche di notte: sono l'unica
ragione per cui il monitor esiste. Solo l'avviso di guasto arriva silenzioso
nelle ore di `quiet_hours`.

### Com'è fatto il messaggio

```
🎟 Posti liberi
dom 13/12, ore 15:30

✅ Platea A: 3 posti  (erano 0)
⚠️ Balconata: 1 posto  (era 0)
      per 2 biglietti non basta

👉 Vai alla pagina dei biglietti
controllo delle 23:02
```

Il «(erano 0)» è il numero del controllo precedente: serve a capire a colpo
d'occhio quanti se ne sono liberati adesso.

Titolo dello spettacolo e teatro non vengono ripetuti: sono gli stessi per tutte
e sei le recite, quindi l'unica cosa che le distingue è giorno e ora.

---

## 5. Configurazione (`config.json`)

| Campo | Significato |
|---|---|
| `zones_watch` | zone sorvegliate: Platea A, Platea B, Palchi, Balconata. Confronto per sottostringa, quindi `"PLATEA"` da solo coprirebbe A e B insieme. Le gallerie sono escluse di proposito |
| `min_seats` | quanti posti ti servono: 2. Non filtra i messaggi, li marca: con 1 solo posto l'avviso arriva ma dice che non basta |
| `interval_seconds` | 180 = un controllo ogni 3 minuti |
| `jitter_seconds` | 60 = aggiunge 0–60 s casuali, così le richieste non sono a orologeria |
| `repeat_minutes` | **0 = disattivato** (nessun promemoria). Un valore >0 ripete l'avviso ogni N minuti finche' i posti restano liberi |
| `notify_on_gone` | **false**: le diminuzioni non si segnalano. A `true` riceveresti un avviso quando una zona torna a zero, rompendo la regola dei soli aumenti |
| `heartbeat_hours` | **0 = disattivato** (nessun riepilogo periodico). Un valore >0 manda ogni N ore un "Monitor attivo" silenzioso |
| `quiet_hours` | `[1, 7]` = fra l'1 e le 7 gli avvisi di esaurimento e di guasto arrivano silenziosi. I posti liberi suonano sempre |
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

## 7. Controllo automatico a PC acceso (Utilità di pianificazione)

L'alternativa a GitHub: Windows lancia il controllo ogni 10 minuti **mentre il
PC è acceso**. Non sveglia il computer e non lo tiene sveglio; a PC spento o in
sospensione non controlla niente e riprende da solo al rientro.

Si configura con lo script già pronto in questa cartella:

```powershell
powershell -ExecutionPolicy Bypass -File ".\Crea attivita pianificata.ps1"
```

Crea un'attività chiamata **Monitor posti Arena** così configurata:

| Voce | Valore | Perché |
|---|---|---|
| Programma | `pythonw.exe` | la variante di Python che **non apre nessuna finestra** |
| Argomenti | `monitor_arena.py once` | un solo controllo e poi esce: nessun processo che resta in piedi |
| Avvio | ogni 10 minuti tutto il giorno, più uno all'accesso | due trigger, vedi sotto |
| Istanze multiple | *ignora la nuova* | mai due controlli sovrapposti |
| Avvia appena possibile | sì | se il PC era spento all'orario previsto, recupera al riavvio |
| Batteria | consentito | funziona anche scollegato |
| Limite di esecuzione | 5 minuti | un controllo bloccato viene interrotto invece di restare appeso |

Un controllo dura circa 35 secondi, quindi 10 minuti di intervallo lasciano
margine abbondante. Per cambiarlo: `-Minuti 5`. Per disattivare tutto:
`-Rimuovi`.

### Perché due trigger e non uno

La ripetizione di un trigger parte quando quel trigger **scatta**. Attaccarla al
solo trigger «all'accesso» sembra giusto e non lo è: se registri l'attività
mentre sei già loggato, l'accesso è già avvenuto, il trigger non scatterà fino
al prossimo riavvio, e nel frattempo non gira niente. L'attività risulta
regolarmente creata e abilitata, ma non fa nulla.

Si riconosce da un dettaglio: `Get-ScheduledTaskInfo` mostra **«prossimo avvio»
vuoto**. Lo script lo controlla da solo e protesta se succede.

Quindi: un trigger **giornaliero** che si riarma ogni giorno e ripete per 24 ore
garantisce la copertura continua; quello **all'accesso** serve solo a fare un
controllo subito dopo il login invece di aspettare fino a dieci minuti.

### Perché `once` e non `watch`

`watch` è un processo unico che resta vivo e cicla da solo: va bene se lo lanci
a mano e tieni la finestra aperta. Per l'automatismo è peggio — se si pianta
resta piantato in silenzio, e serve una finestra o un processo nascosto da
gestire. Con `once` ogni controllo è un processo nuovo che nasce, fa il suo
lavoro e muore: se uno fallisce, il successivo riparte pulito dieci minuti dopo.
È Windows a fare da ciclo, ed è più affidabile di qualsiasi ciclo scritto da me.

### Non tenerlo acceso insieme a GitHub

Hanno memorie separate (`state.json` sul PC, `ci-state.json` su GitHub), quindi
riceveresti ogni avviso due volte. Se attivi questo, disattiva il workflow:
Actions → *Monitor posti Lago dei Cigni* → `...` → *Disable workflow*.

---

## 8. Alternativa manuale: la cartella Esecuzione automatica

Più rudimentale dell'attività pianificata qui sopra, e peggiore: lancia
`watch`, cioè un processo che resta in piedi, con la finestra nera aperta.
Serve solo se per qualche motivo l'Utilità di pianificazione non è usabile.

1. `Win + R` → `shell:startup` → Invio
2. Trascina dentro **`3 - Avvia monitor.bat`** tenendo premuto `ALT`
   (crea un collegamento)

Il monitor parte a ogni accesso a Windows. Nota: deve esserci corrente, rete e
il PC acceso — se lo spegni la notte, in quelle ore non controlla nulla.

---

## 9. Situazione al 25 novembre 2026

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

## 10. File prodotti

* `monitor.log` — storico di tutti i controlli, con la disponibilità vista ogni
  volta. Utile per capire *quando* si liberano i posti.
* `state.json` — ultimo valore noto per zona. Cancellalo per azzerare la memoria
  (il primo controllo successivo non manderà allarmi, solo il riepilogo).
* Il profilo di Chromium sta in `%LOCALAPPDATA%\MonitorArena\chrome-profile`,
  **fuori** da OneDrive, per non far sincronizzare centinaia di MB di cache.

---

## 11. Requisiti (già installati su questo PC)

* Python 3.14
* `requests`
* `playwright` + Chromium

Se servisse rifarlo su un altro computer:

```powershell
python -m pip install requests playwright; python -m playwright install chromium
```

---

## 12. Avvertenze

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
