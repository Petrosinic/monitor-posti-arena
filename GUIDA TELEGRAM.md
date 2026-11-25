# Guida passo passo — collegare Telegram al monitor

Tempo richiesto: circa 3 minuti. Si fa **una volta sola**.

Ti servono: il telefono con Telegram, e questo PC.

---

## Perché serve un bot

Telegram **non permette di mandare messaggi a un numero di telefono**. Nessun
programma può scrivere al tuo numero di cellulare: i bot possono scrivere
soltanto a chi ha aperto una conversazione con loro.

Quindi crei un bot tuo (è gratis, è tuo, non lo vede nessun altro), premi START
una volta, e da quel momento il monitor può scriverti. Le notifiche arrivano
come qualsiasi messaggio Telegram, con la push sul telefono.

---

## PARTE 1 — Creare il bot (sul telefono)

### 1. Apri BotFather

Su Telegram, nella barra di ricerca in alto, scrivi:

```
@BotFather
```

Aprilo. **Controlla che abbia la spunta blu** di account verificato: ci sono
imitazioni con nomi simili. Il nome esatto è *BotFather*.

### 2. Premi START

Se è la prima volta che lo apri, in basso c'è un pulsante **START**. Premilo.
Ti risponde con un elenco lungo di comandi: ignoralo.

### 3. Chiedi un bot nuovo

Scrivi nella chat e invia:

```
/newbot
```

BotFather risponde:

> Alright, a new bot. How are we going to call it? Please choose a name for your bot.

### 4. Dai un nome

È il nome che vedrai in cima alla chat. Qualsiasi cosa va bene, anche con spazi
e accenti. Per esempio:

```
Posti Arena
```

BotFather risponde:

> Good. Now let's choose a username for your bot. It must end in `bot`.

### 5. Dai uno username

Questo invece deve essere **unico in tutto Telegram** e **finire per `bot`**.
Niente spazi, solo lettere, numeri e trattini bassi. Per esempio:

```
posti_arena_np_bot
```

- Se risponde **"Sorry, this username is already taken"** è già di qualcun
  altro: aggiungi qualcosa e riprova (`posti_arena_np2_bot`, `np_arena_1986_bot`…).
- Se risponde **"Sorry, I don't like that username"** hai usato caratteri non
  ammessi o non finisce per `bot`.

### 6. Prendi il token

Quando lo username va bene, BotFather risponde:

> Done! Congratulations on your new bot. You will find it at t.me/posti_arena_np_bot
>
> Use this token to access the HTTP API:
> `8123456789:AAHk9xV-abcDEFghiJKLmnoPQRstu0123456`
>
> Keep your token secure and store it safely...

Quella riga in carattere monospaziato è il **token**: una quarantina di
caratteri, con i due punti nel mezzo.

**Tocca il token**: Telegram lo copia da solo negli appunti (compare
"Copiato"). Non trascriverlo a mano, è facile sbagliare un carattere.

> **Il token è una password.** Chi lo ha può far scrivere il tuo bot. Non
> mandarlo a nessuno, non incollarlo in chat, non metterlo in un documento
> condiviso. Se ti scappa, in BotFather fai `/mybots` → scegli il bot →
> *API Token* → **Revoke current token** e te ne dà uno nuovo.

### 7. Portalo sul PC

Il modo più semplice: su Telegram apri la chat **Messaggi salvati**
(cercando `Messaggi salvati`, oppure il tuo stesso nome) e incolla lì il token.
Poi apri Telegram Desktop sul PC e lo ritrovi, pronto da copiare.

Se non hai Telegram sul PC, va benissimo anche trascriverlo guardando il
telefono: lo incollerai nel passo successivo.

---

## PARTE 2 — Collegare il monitor (sul PC)

### 8. Lancia la configurazione

Nella cartella `Monitor Biglietti Arena`, doppio clic su:

```
1 - Configura Telegram.bat
```

Si apre una finestra nera che ti ricorda i passi di prima e poi ti chiede:

```
 Token >
```

### 9. Incolla il token e premi Invio

Nella finestra nera si incolla con il **tasto destro del mouse** (oppure
`CTRL+V`). Il token non si vede mentre lo incolli? Normale in alcune
configurazioni: incolla e premi `Invio` comunque.

Puoi anche incollare **tutto il messaggio di BotFather**, non solo il token: il
programma lo cerca da solo dentro al testo.

Se il token è buono, risponde:

```
 Token verificato e salvato in config.json.
```

Se risponde **"Telegram rifiuta questo token"**, l'hai copiato a metà: il
programma lo cancella e basta rilanciare il file e riprovare.

### 10. Apri il tuo bot e premi START

Il programma ti stampa l'indirizzo del tuo bot:

```
 ==>  https://t.me/posti_arena_np_bot
```

Aprilo **sul telefono** — attenzione, è il bot che hai appena creato, non
BotFather — e premi il pulsante **START** in basso. Se non vedi START,
scrivigli un messaggio qualsiasi, per esempio `ciao`.

### 11. Fine

Entro qualche secondo la finestra nera scrive:

```
 Trovato! chat: Mario Rossi  (chat_id 123456789)
 Salvato in config.json.
 Messaggio di conferma inviato.
 Configurazione finita. Ora puoi lanciare  3 - Avvia monitor.bat
```

E sul telefono ti arriva il messaggio **"Monitor Arena di Verona collegato"**.

Premi un tasto per chiudere la finestra.

---

## PARTE 3 — Due regolazioni consigliate sul telefono

Il senso del monitor è reagire in fretta, quindi vale la pena che la notifica
non passi inosservata. Nella chat del bot, tocca il nome in alto → **Notifiche**:

1. Assicurati che **non** sia silenziata.
2. Mettici un **suono diverso** dagli altri: così riconosci la notifica senza
   guardare lo schermo.
3. Opzionale: torna all'elenco chat, tieni premuto sulla chat del bot e scegli
   **Fissa in alto**.

---

## Problemi tipici

| Cosa vedi | Cosa è | Cosa fare |
|---|---|---|
| "Sorry, this username is already taken" | lo username è preso | aggiungi un numero o le tue iniziali |
| "Telegram rifiuta questo token: Unauthorized" | token incompleto o bot cancellato | rilancia il `.bat` e reincolla tutto il token |
| "Non ho ricevuto nessun messaggio entro 5 minuti" | non hai premuto START, o l'hai premuto su BotFather | apri il link `t.me/...` che ti ha stampato il programma e premi START lì |
| "Non riesco a contattare Telegram" | rete assente, o VPN/proxy aziendale che blocca `api.telegram.org` | prova in rete normale o via hotspot del telefono |
| `python non è riconosciuto come comando` | Python non è nel PATH di quella finestra | riavvia il PC, oppure dimmelo e sistemo il `.bat` con il percorso completo |
| Il bot non ti scrive più | hai bloccato il bot, o hai revocato il token | sbloccalo dalla chat; se hai revocato, svuota `bot_token` in `config.json` e rifai la configurazione |

---

## Dove finiscono le cose

Token e `chat_id` vengono scritti in `config.json`, in questa cartella. È un
file di testo in chiaro: resta sul tuo PC, ma tienilo presente se condividi la
cartella con qualcuno (è dentro OneDrive).

Per rifare tutto da zero: apri `config.json` col Blocco note e svuota i due
campi, lasciando le virgolette:

```json
"telegram": { "bot_token": "", "chat_id": "" }
```

Poi rilancia `1 - Configura Telegram.bat`.
