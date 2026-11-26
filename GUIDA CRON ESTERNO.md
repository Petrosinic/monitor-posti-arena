# Far partire il controllo in modo affidabile, senza PC

Lo scheduler di GitHub è capriccioso: nelle prime dodici ore ha fatto partire
**un solo** controllo programmato, mentre tutti i run lanciati a mano sono
riusciti. Il meccanismo funziona, il grilletto no.

L'idea qui è sostituire il grilletto: un servizio di cron esterno chiama ogni
quindici minuti l'API di GitHub e fa partire il workflow **come se premessi tu
il pulsante** — che è l'unica cosa che sappiamo funzionare sempre.

Risultato: controlli regolari 24 ore su 24, a PC spento, telefono spento,
qualunque giorno della settimana.

---

## Cosa stai per dare a un terzo, detto chiaramente

Serve un token GitHub, e lo incollerai nel sito del servizio di cron. Non è una
cosa da fare alla leggera, quindi ecco il perimetro esatto.

Il token sarà di tipo **fine-grained**, limitato a:

* **un solo repository**: `monitor-posti-arena`
* **un solo permesso**: *Actions*, lettura e scrittura
* **una scadenza**: mettila a gennaio, non "nessuna scadenza"

Con quel token, il peggio che può fare chi lo possedesse è far partire, annullare
o rileggere i log di quel workflow. Non può leggere i tuoi altri repository, non
può toccare il tuo account, non può leggere i Secrets (GitHub non li espone via
API a nessuno). Il repository è già pubblico, quindi non c'è nulla da proteggere
nel contenuto.

È un rischio piccolo e circoscritto, ma è un rischio, ed è giusto che la scelta
sia tua. Alla fine c'è anche l'alternativa senza terzi.

---

## PASSO 1 — Crea il token

Apri **https://github.com/settings/personal-access-tokens/new**

| Campo | Valore |
|---|---|
| Token name | `cron monitor posti` |
| Expiration | una data a gennaio |
| Repository access | **Only select repositories** → `monitor-posti-arena` |
| Permissions → Repository permissions → **Actions** | **Read and write** |

Lascia tutto il resto su *No access*. *Metadata: Read-only* si attiva da solo ed
è obbligatorio: va bene.

**Generate token**, poi copialo subito: GitHub non te lo mostrerà più.

---

## PASSO 2 — Provalo prima di darlo a qualcuno

Questa è la parte che conviene non saltare. Prima di incollare il token in un
sito di terzi, verifica che funzioni e che faccia esattamente quello che deve.

Apri PowerShell e lancia:

```powershell
$t = Read-Host "Incolla il token" -AsSecureString; $k = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($t)); try { Invoke-RestMethod -Uri "https://api.github.com/repos/Petrosinic/monitor-posti-arena/actions/workflows/monitor.yml/dispatches" -Method Post -Headers @{Authorization="Bearer $k"; Accept="application/vnd.github+json"; "X-GitHub-Api-Version"="2022-11-28"} -Body '{"ref":"main"}'; Write-Host "OK: il workflow e' partito. Guarda la scheda Actions." -ForegroundColor Green } catch { Write-Host ("ERRORE: " + $_.Exception.Message) -ForegroundColor Red }
```

Il token lo digiti nascosto e non resta scritto da nessuna parte.

* **OK** → vai su Actions, deve esserci un run nuovo appena partito.
* **403 / Resource not accessible** → al token manca il permesso *Actions:
  Read and write*, o non hai selezionato il repository giusto.
* **404** → nome del repository sbagliato, o il token non vede quel repository.

---

## PASSO 3 — Configura il servizio di cron

Vai su **https://cron-job.org**, crea un account gratuito, poi **Create cronjob**.

### Scheda COMMON

| Campo | Valore |
|---|---|
| Title | `Monitor posti Arena` |
| URL | `https://api.github.com/repos/Petrosinic/monitor-posti-arena/actions/workflows/monitor.yml/dispatches` |
| Schedule | *Every 15 minutes* (oppure *Custom* → minuti `*/15`) |

### Scheda ADVANCED

| Campo | Valore |
|---|---|
| Request method | **POST** |
| Request body | `{"ref":"main"}` |

Headers, uno per riga:

```
Accept: application/vnd.github+json
Authorization: Bearer IL_TUO_TOKEN
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

Al posto di `IL_TUO_TOKEN` incolli il token del passo 1, lasciando la parola
`Bearer` e lo spazio.

**Save.**

---

## PASSO 4 — Verifica

GitHub risponde a questa chiamata con **204 No Content**: nel registro di
cron-job.org vedrai `204`, che è il successo. Non è un errore il fatto che non
ci sia contenuto nella risposta.

Dopo un quarto d'ora, nella scheda Actions devono comparire run nuovi. Li
riconosci perché l'evento è di nuovo **workflow_dispatch**, non *schedule*: per
GitHub è come se avessi premuto il pulsante tu.

Da quel momento hai un controllo ogni quindici minuti, sempre.

---

## Cosa resta acceso, e perché

| Chi | Quando | Note |
|---|---|---|
| Cron esterno → GitHub | sempre, ogni 15 min | la copertura vera |
| Attività pianificata sul PC | mentre il PC è acceso, ogni 10 min | più veloce quando ci sei |
| Scheduler interno di GitHub | quando gli pare | innocuo, lascialo |

I primi due possono segnalare lo stesso cambiamento due volte, perché hanno
memorie separate. Succede solo quando un posto si libera davvero. Se i doppioni
ti danno fastidio più della ridondanza, togli l'attività pianificata dal PC con
`.\Crea attivita pianificata.ps1 -Rimuovi`.

---

## Se cambi idea

* **Revocare il token**: https://github.com/settings/tokens?type=beta → il token
  → *Delete*. Il cron esterno inizierà a fallire, e basta.
* **Fermare il cron esterno**: nel pannello di cron-job.org, interruttore del
  job su *disabled*.
* **Quando avrai comprato i biglietti**: revoca il token, disabilita il job,
  disabilita il workflow su GitHub e rimuovi l'attività dal PC.

---

## Alternativa senza affidare il token a terzi

**Cloudflare Workers** ha i Cron Triggers gratuiti: scrivi una funzione di dieci
righe che fa la stessa chiamata, e il token resta nelle variabili d'ambiente di
Cloudflare. Più affidabile e il token sta in una grande infrastruttura invece che
in un servizio piccolo, ma richiede di creare un account Cloudflare e caricare il
Worker. Se preferisci questa strada, dimmelo e preparo il codice.
