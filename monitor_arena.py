#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor posti liberi - Fondazione Arena di Verona / Teatro Filarmonico
=======================================================================

Controlla a intervalli regolari la disponibilita' reale dei posti per le recite
di uno spettacolo e manda un messaggio Telegram quando qualcosa cambia nelle
zone sorvegliate (per default PLATEA A e PLATEA B).

Non confronta immagini: legge direttamente il JSON che la mappa interattiva del
sito usa per colorare i posti (map.php?cmd=orchestrator), quindi sa esattamente
quanti posti sono liberi in ogni zona.

Il sito e' protetto da Imperva/Incapsula, percio' serve un browser vero:
usa Playwright (Chromium) con un profilo persistente, carica una pagina del
negozio una volta sola e poi interroga il JSON con fetch() dall'interno della
pagina. Un ciclo completo = 1 navigazione + 1 chiamata JSON per recita.

Comandi
-------
    python monitor_arena.py setup      # trova il chat_id del tuo bot Telegram
    python monitor_arena.py test       # invia un messaggio Telegram di prova
    python monitor_arena.py discover   # ricarica l'elenco delle recite
    python monitor_arena.py check      # un solo controllo, stampa la situazione
    python monitor_arena.py once       # un solo controllo CON notifiche, poi esce
    python monitor_arena.py watch      # controllo continuo (il programma vero)

Variabili d'ambiente (usate da GitHub Actions)
----------------------------------------------
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   credenziali, vincono sul file
    MONITOR_CONFIG, MONITOR_STATE, MONITOR_LOG   percorsi alternativi dei file
    MONITOR_HEADLESS=0                     apre una finestra Chromium visibile
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    sys.exit("Manca il pacchetto 'requests'. Installa con: python -m pip install requests")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Manca Playwright. Installa con: python -m pip install playwright "
             "&& python -m playwright install chromium")


# --------------------------------------------------------------------------- #
# Percorsi e configurazione
# --------------------------------------------------------------------------- #

BASE = Path(__file__).resolve().parent


def _path_from_env(var: str, default_name: str) -> Path:
    """Permette di spostare config/stato/log con una variabile d'ambiente.
    Serve su GitHub Actions, dove config e stato sono file diversi da quelli locali."""
    val = os.environ.get(var, "").strip()
    return Path(val) if val else BASE / default_name


CONFIG_FILE = _path_from_env("MONITOR_CONFIG", "config.json")
STATE_FILE = _path_from_env("MONITOR_STATE", "state.json")
LOG_FILE = _path_from_env("MONITOR_LOG", "monitor.log")

# Quali credenziali arrivano dall'ambiente invece che dal file: quelle non
# vanno mai riscritte nel file (su GitHub sono dei Secrets, e il repository
# puo' essere pubblico). FILE_TELEGRAM tiene il valore originale del file.
TELEGRAM_FROM_ENV = {"bot_token": False, "chat_id": False}
FILE_TELEGRAM = {"bot_token": "", "chat_id": ""}

SHOP = "https://shop.arena.it"
LIST_URL = SHOP + "/it/buy-ticket/arenaverona-tutto/"
BUY_URL = SHOP + "/index.php?nvpg[sell]&pcode={pcode}&tcode={tcode}&cmd=priceTicketSelection"

DEFAULTS = {
    "telegram": {"bot_token": "", "chat_id": ""},
    "tcode": "vt0020008",
    "operator": "arenaverona",
    "show_filter": "Il Lago Dei Cigni",
    "zones_watch": ["PLATEA A", "PLATEA B"],
    "min_seats": 2,
    "interval_seconds": 180,
    "jitter_seconds": 60,
    "repeat_minutes": 45,
    "notify_on_gone": True,
    "heartbeat_hours": 12,
    "failure_alert_hours": 6,
    "quiet_hours": [1, 7],
    "headless": True,
    "profile_dir": "",
    "events": [],
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        sys.exit("File di configurazione non trovato: " + str(CONFIG_FILE))
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    merged = dict(DEFAULTS)
    merged.update(cfg)
    merged["telegram"] = dict(DEFAULTS["telegram"], **cfg.get("telegram", {}))
    FILE_TELEGRAM.update(merged["telegram"])

    # l'ambiente vince sul file: su GitHub Actions i Secrets arrivano cosi'
    for field, var in (("bot_token", "TELEGRAM_BOT_TOKEN"),
                       ("chat_id", "TELEGRAM_CHAT_ID")):
        val = os.environ.get(var, "").strip()
        if val:
            merged["telegram"][field] = val
            TELEGRAM_FROM_ENV[field] = True

    env_headless = os.environ.get("MONITOR_HEADLESS", "").strip().lower()
    if env_headless:
        merged["headless"] = env_headless not in ("0", "false", "no")
    return merged


def save_config(cfg: dict) -> None:
    """Scrive la configurazione. Le credenziali che arrivano dall'ambiente non
    finiscono nel file: su GitHub il repository puo' essere pubblico."""
    out = dict(cfg)
    tel = dict(cfg.get("telegram") or {})
    for field in ("bot_token", "chat_id"):
        if TELEGRAM_FROM_ENV.get(field):
            tel[field] = FILE_TELEGRAM.get(field, "")
    out["telegram"] = tel
    CONFIG_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            log.warning("state.json illeggibile, riparto da zero")
    return {"zones": {}, "last_heartbeat": 0.0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def profile_path(cfg: dict) -> Path:
    """Profilo del browser: fuori da OneDrive, per non sincronizzare centinaia di MB."""
    if cfg.get("profile_dir"):
        p = Path(cfg["profile_dir"])
    else:
        root = os.environ.get("LOCALAPPDATA") or str(Path.home())
        p = Path(root) / "MonitorArena" / "chrome-profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------- #
# Log
# --------------------------------------------------------------------------- #

def setup_logging() -> logging.Logger:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    logger = logging.getLogger("monitor")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


log = setup_logging()


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #

class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = (token or "").strip()
        self.chat_id = str(chat_id or "").strip()

    @property
    def ready(self) -> bool:
        return bool(self.token and self.chat_id)

    def _api(self, method: str, **params):
        url = "https://api.telegram.org/bot" + self.token + "/" + method
        data = requests.post(url, data=params, timeout=30).json()
        if not data.get("ok"):
            raise RuntimeError("Telegram " + method + " ha risposto: " + str(data))
        return data["result"]

    def send(self, text: str, silent: bool = False) -> bool:
        if not self.ready:
            log.error("Telegram non configurato (bot_token/chat_id vuoti). Avviso non inviato:\n%s", text)
            return False
        for attempt in (1, 2, 3):
            try:
                self._api(
                    "sendMessage",
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_notification="true" if silent else "false",
                )
                return True
            except Exception as exc:
                log.warning("Invio Telegram fallito (tentativo %d/3): %s", attempt, exc)
                time.sleep(3 * attempt)
        return False


TOKEN_RE = re.compile(r"(\d{6,12}:[A-Za-z0-9_-]{30,})")


def extract_token(text: str) -> str:
    """Pesca il token anche se e' stato incollato dentro al messaggio di BotFather."""
    m = TOKEN_RE.search(text or "")
    return m.group(1) if m else ""


def ask_token(cfg: dict) -> str:
    """Chiede il token a schermo e lo salva, cosi' non serve modificare config.json."""
    print("")
    print("=" * 68)
    print(" PASSO 1 - Crea il bot su Telegram (serve una volta sola)")
    print("=" * 68)
    print("")
    print("  1. Sul telefono apri Telegram e cerca:   @BotFather")
    print("     (quello giusto ha la spunta blu di account verificato)")
    print("  2. Aprilo e premi START")
    print("  3. Scrivi:   /newbot")
    print("  4. Ti chiede un NOME: scrivi quello che vuoi, es.   Posti Arena")
    print("  5. Ti chiede uno USERNAME: deve finire per 'bot' ed essere libero,")
    print("     es.   posti_arena_np_bot")
    print("     (se risponde 'already taken' provane un altro)")
    print("  6. Risponde 'Done!' e ti da' il TOKEN, una riga tipo:")
    print("        8123456789:AAHk9xV-abcDEFghiJKLmnoPQRstu0123456")
    print("     Tocca il token su Telegram per copiarlo.")
    print("")
    print("-" * 68)
    print(" PASSO 2 - Incolla il token qui sotto")
    print("-" * 68)
    print("")
    print(" (nel Prompt dei comandi si incolla col TASTO DESTRO del mouse,")
    print("  oppure con CTRL+V. Puoi anche incollare tutto il messaggio di")
    print("  BotFather: il token lo trovo io.)")
    print("")
    # Legge una riga alla volta: se incolli tutto il messaggio di BotFather,
    # il token arriva su una riga successiva e lo prendo comunque.
    token, got_something = "", False
    for i in range(12):
        try:
            raw = input(" Token > " if i == 0 else "         > ")
        except (EOFError, KeyboardInterrupt):
            break
        token = extract_token(raw)
        if token:
            break
        if not raw.strip():
            break
        got_something = True
        if i == 0:
            print(" (sto ancora cercando il token; se hai finito di incollare,"
                  " premi Invio a vuoto)")

    if not token:
        print("")
        if got_something:
            print(" Non ho riconosciuto nessun token in quello che hai incollato.")
            print(" Deve essere una riga della forma  numeri:lettere, tipo")
            print("    8123456789:AAHk9xV-abcDEFghiJKLmnoPQRstu0123456")
            print(" Su Telegram tocca il token nel messaggio di BotFather: lo copia da solo.")
        else:
            print(" Niente token, mi fermo qui. Rilancia questo file quando l'hai.")
        return ""
    print("")
    print(" Token letto, verifico con Telegram...")
    return token


def cmd_setup(cfg: dict) -> None:
    """Chiede il token (se manca) e ricava il chat_id dai messaggi arrivati al bot."""
    saved = extract_token(cfg["telegram"]["bot_token"]) or cfg["telegram"]["bot_token"].strip()
    token = saved or ask_token(cfg)
    if not token:
        return

    try:
        me = requests.get("https://api.telegram.org/bot" + token + "/getMe", timeout=30).json()
    except Exception as exc:
        print("\n Non riesco a contattare Telegram: " + str(exc))
        print(" Controlla la connessione e riprova.")
        return
    if not me.get("ok"):
        print("\n Telegram rifiuta questo token: " + str(me.get("description") or me))
        print(" Probabilmente e' incompleto o appartiene a un bot cancellato.")
        if saved:
            cfg["telegram"]["bot_token"] = ""
            save_config(cfg)
            print(" L'ho cancellato da config.json: rilancia questo file e te lo richiedo.")
        else:
            print(" Rilancia questo file e incollalo di nuovo, tutto intero.")
        return

    # token buono: solo adesso lo salvo
    if cfg["telegram"]["bot_token"].strip() != token:
        cfg["telegram"]["bot_token"] = token
        save_config(cfg)
        print(" Token verificato e salvato in config.json.")

    username = me["result"]["username"]

    if cfg["telegram"]["chat_id"].strip():
        print("\n Bot @" + username + " gia' collegato (chat_id " +
              cfg["telegram"]["chat_id"].strip() + "). Invio un messaggio di verifica...")
        ok = Telegram(token, cfg["telegram"]["chat_id"]).send(
            "✅ Verifica collegamento: il monitor sa come scriverti."
        )
        print(" Fatto, controlla Telegram." if ok else " Invio fallito, vedi monitor.log")
        print(" Per collegare una chat diversa, svuota chat_id in config.json e rilancia.")
        return

    print("")
    print("=" * 68)
    print(" PASSO 3 - Apri il TUO bot e premi START")
    print("=" * 68)
    print("")
    print("   ==>  https://t.me/" + username)
    print("")
    print(" Aprilo sul telefono (non su @BotFather: sul bot che hai appena creato)")
    print(" e premi il pulsante START in basso. Se non vedi START, scrivigli")
    print(" un messaggio qualsiasi, per esempio   ciao")
    print("")
    print(" Attendo... (fino a 5 minuti)", flush=True)

    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            upd = requests.get("https://api.telegram.org/bot" + token + "/getUpdates",
                               timeout=30).json()
        except Exception:
            time.sleep(3)
            continue
        if not upd.get("ok"):
            desc = str(upd.get("description") or "")
            if "webhook" in desc.lower():
                print("\n Questo bot ha un webhook attivo e non posso leggere i messaggi.")
                print(" Aprilo in @BotFather, /mybots -> Delete Webhook, oppure usa un bot nuovo.")
                return
            print("\n Telegram risponde: " + desc)
            return
        for item in upd.get("result", []):
            msg = item.get("message") or item.get("my_chat_member") or {}
            chat = msg.get("chat") or {}
            if chat.get("id"):
                chat_id = str(chat["id"])
                name = chat.get("first_name") or chat.get("title") or chat_id
                cfg["telegram"]["chat_id"] = chat_id
                save_config(cfg)
                print("")
                print(" Trovato! chat: " + str(name) + "  (chat_id " + chat_id + ")")
                print(" Salvato in config.json.")
                ok = Telegram(token, chat_id).send(
                    "\U0001F39F <b>Monitor Arena di Verona collegato</b>\n\n"
                    "Ti avviso qui quando si liberano posti in platea "
                    "per Il Lago dei Cigni al Teatro Filarmonico.\n\n"
                    "<i>Consiglio: tieni le notifiche di questa chat attive e non "
                    "silenziate, i posti spariscono in fretta.</i>"
                )
                print(" Messaggio di conferma inviato." if ok
                      else " Invio fallito, vedi monitor.log")
                print("")
                print(" Configurazione finita. Ora puoi lanciare  3 - Avvia monitor.bat")
                return
        time.sleep(3)

    print("")
    print(" Non ho ricevuto nessun messaggio entro 5 minuti.")
    print(" Controlla di aver premuto START sul bot @" + username + " e rilancia questo file.")


def cmd_test(cfg: dict) -> None:
    tg = Telegram(cfg["telegram"]["bot_token"], cfg["telegram"]["chat_id"])
    if not tg.ready:
        print("Telegram non configurato: lancia prima  python monitor_arena.py setup")
        return
    ok = tg.send(
        "<b>Messaggio di prova</b>\nIl monitor posti Arena di Verona funziona.\n"
        "<i>" + format(datetime.now(), "%d/%m/%Y %H:%M") + "</i>"
    )
    print("Inviato." if ok else "Invio fallito, vedi monitor.log")


# --------------------------------------------------------------------------- #
# Accesso al negozio (Playwright)
# --------------------------------------------------------------------------- #

JS_FETCH = """
async (url) => {
  const r = await fetch(url, {credentials: 'include', headers: {'Accept': 'application/json'}});
  const t = await r.text();
  return {status: r.status, ct: r.headers.get('content-type') || '', body: t};
}
"""

JS_EVENTS = r"""
() => Array.from(document.querySelectorAll('a[href*="pcode="]')).map(a => {
  let n = a, info = '';
  for (let i = 0; i < 6 && n; i++) {
    n = n.parentElement;
    if (n && n.innerText && n.innerText.match(/\d{2}\/\d{2}\/\d{4}/)) {
      info = n.innerText.replace(/\s+/g, ' ').trim();
      break;
    }
  }
  const m = a.getAttribute('href').match(/pcode=(\d+)/);
  return {pcode: m ? m[1] : null, info: info};
}).filter(x => x.pcode)
"""


class Shop:
    """Sessione browser verso shop.arena.it."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._pw = None
        self._ctx = None
        self._page = None

    # -- ciclo di vita ----------------------------------------------------- #

    def start(self) -> None:
        self.stop()
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_path(self.cfg)),
            headless=bool(self.cfg.get("headless", True)),
            viewport={"width": 1366, "height": 900},
            locale="it-IT",
            timezone_id="Europe/Rome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._page.set_default_timeout(60000)
        self.anchor()

    def stop(self) -> None:
        for obj, meth in ((self._ctx, "close"), (self._pw, "stop")):
            if obj is not None:
                try:
                    getattr(obj, meth)()
                except Exception:
                    pass
        self._pw = self._ctx = self._page = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    # -- navigazione ------------------------------------------------------- #

    def anchor(self) -> None:
        """Carica una pagina vera del negozio: serve a superare Incapsula e a
        prendere i cookie di sessione che poi useranno le fetch()."""
        url = LIST_URL
        if self.cfg.get("show_filter"):
            url += "?filter_show=" + quote(self.cfg["show_filter"])
        self._page.goto(url, wait_until="domcontentloaded", timeout=90000)
        self._page.wait_for_timeout(2500)

    def get_json(self, path: str, retries: int = 2):
        """fetch() dall'interno della pagina -> dict.
        Se Incapsula interrompe la sessione, ricarica la pagina e riprova."""
        last = None
        for attempt in range(retries + 1):
            try:
                res = self._page.evaluate(JS_FETCH, SHOP + path)
            except Exception as exc:
                last = "evaluate: " + str(exc)[:200]
            else:
                body = res.get("body") or ""
                if res.get("status") == 200 and body.lstrip()[:1] in ("{", "["):
                    try:
                        return json.loads(body)
                    except json.JSONDecodeError as exc:
                        last = "json: " + str(exc)
                else:
                    last = "status=%s ct=%s body=%r" % (res.get("status"), res.get("ct"), body[:120])
            if attempt < retries:
                log.warning("Risposta non valida (%s). Ricarico la pagina e riprovo.", last)
                try:
                    self.anchor()
                except Exception:
                    self.start()
                time.sleep(3)
        raise RuntimeError("Non riesco a leggere " + path + ": " + str(last))

    # -- dati -------------------------------------------------------------- #

    def availability(self, pcode: str) -> dict:
        """{nome zona: posti liberi} per una recita."""
        path = ("/map.php?cmd=orchestrator&pcode=" + str(pcode) +
                "&tcode=" + self.cfg["tcode"] + "&operator=" + self.cfg["operator"])
        data = self.get_json(path)
        zones = {}
        for macro in (data.get("price") or {}).get("macrozones") or []:
            for zone in macro.get("zones") or []:
                name = (zone.get("name") or macro.get("name") or "").strip().upper()
                if not name:
                    continue
                try:
                    avail = int(zone.get("availability") or 0)
                except (TypeError, ValueError):
                    avail = 0
                zones[name] = zones.get(name, 0) + avail
        if not zones:
            raise RuntimeError("Nessuna zona nel JSON della recita " + str(pcode))
        return zones

    def discover_events(self) -> list:
        """Elenca le recite dello spettacolo filtrato."""
        self.anchor()
        raw = self._page.evaluate(JS_EVENTS)
        events, seen = [], set()
        for item in raw:
            pcode = item.get("pcode")
            if not pcode or pcode in seen:
                continue
            seen.add(pcode)
            info = (item.get("info") or "").replace("Acquista", "").strip(" -·")
            events.append({"pcode": pcode, "label": info or ("recita " + pcode)})
        return events


# --------------------------------------------------------------------------- #
# Logica di sorveglianza
# --------------------------------------------------------------------------- #

def watched_zones(cfg: dict, zones: dict) -> dict:
    """Filtra le zone da sorvegliare: confronto per sottostringa, senza maiuscole."""
    wanted = [w.strip().upper() for w in cfg["zones_watch"] if w.strip()]
    if not wanted:
        return dict(zones)
    return {name: n for name, n in zones.items() if any(w in name for w in wanted)}


def is_quiet(cfg: dict) -> bool:
    qh = cfg.get("quiet_hours") or []
    if len(qh) != 2:
        return False
    start, end = int(qh[0]), int(qh[1])
    h = datetime.now().hour
    return start <= h < end if start <= end else (h >= start or h < end)


def buy_link(cfg: dict, pcode: str) -> str:
    return BUY_URL.format(pcode=pcode, tcode=cfg["tcode"])


WHEN_RE = re.compile(r"(\w{3})\s+(\d{2})/(\d{2})/\d{4}\s+(\d{1,2}[:.]\d{2})")


def short_when(event: dict) -> str:
    """Tiene solo giorno e ora dal nome della recita, perche' titolo e teatro
    sono gli stessi per tutte e ripeterli allunga il messaggio per niente:
    'Il Lago Dei Cigni - dom 13/12/2026 15:30 - Teatro Filarmonico'
      ->  'dom 13/12, ore 15:30'"""
    m = WHEN_RE.search(event.get("label", ""))
    if not m:
        return event.get("label") or event.get("pcode", "")
    giorno, gg, mm, ora = m.groups()
    return "%s %s/%s, ore %s" % (giorno, gg, mm, ora.replace(".", ":"))


def zone_name(zone: str) -> str:
    """PLATEA A -> Platea A, BALCONATA -> Balconata"""
    return " ".join(w if w.isdigit() else w.capitalize() for w in zone.split())


def zone_order(cfg: dict, zone: str) -> int:
    """Ordina le zone come sono elencate in zones_watch, non alfabeticamente."""
    for i, w in enumerate(cfg.get("zones_watch") or []):
        if w.strip().upper() in zone:
            return i
    return 99


def format_alert(cfg: dict, event: dict, changes: list, reminder: bool = False) -> str:
    gone = all(n == 0 for _, n, _ in changes)
    quando = html.escape(short_when(event))
    need = int(cfg["min_seats"])

    if gone:
        lines = ["❌ <b>Posti esauriti di nuovo</b>", quando, ""]
    elif reminder:
        lines = ["\U0001F39F <b>Posti ancora liberi</b>", quando, ""]
    else:
        lines = ["\U0001F39F <b>Posti liberi</b>", quando, ""]

    for zone, now, before in sorted(changes, key=lambda c: zone_order(cfg, c[0])):
        nome = html.escape(zone_name(zone))
        if now == 0:
            lines.append("✖ " + nome + ": nessun posto, erano " + str(before))
        elif now >= need:
            prima = "" if reminder else "  (erano " + str(before) + ")"
            lines.append("✅ <b>" + nome + ": " + str(now) + " posti</b>" + prima)
        else:
            parola = "posto" if now == 1 else "posti"
            prima = "" if reminder else "  (era " + str(before) + ")"
            lines.append("⚠️ " + nome + ": " + str(now) + " " + parola + prima +
                         "\n      <i>per " + str(need) + " biglietti non basta</i>")

    lines.append("")
    if not gone:
        lines.append('\U0001F449 <a href="' + html.escape(buy_link(cfg, event["pcode"])) +
                     '">Vai alla pagina dei biglietti</a>')
    lines.append("<i>controllo delle " + format(datetime.now(), "%H:%M") + "</i>")
    return "\n".join(lines)


def run_cycle(shop: Shop, cfg: dict, state: dict, tg: Telegram, first_run: bool) -> tuple:
    """Esegue un giro completo su tutte le recite. Ritorna (letture_ok, letture_fallite)."""
    now_ts = time.time()
    zstate = state.setdefault("zones", {})
    ok_count, fail_count = 0, 0

    for idx, event in enumerate(cfg["events"]):
        pcode = event["pcode"]
        try:
            zones = shop.availability(pcode)
        except Exception as exc:
            fail_count += 1
            log.error("Recita %s (%s): %s", pcode, event.get("label", ""), exc)
            continue
        ok_count += 1

        watch = watched_zones(cfg, zones)
        summary = ", ".join(k + "=" + str(v) for k, v in sorted(watch.items()))
        log.info("%s | %s", event.get("label", pcode), summary or "nessuna zona sorvegliata")

        changes, reminders = [], []

        for zone, avail in watch.items():
            key = pcode + "|" + zone
            prev = zstate.get(key, {})
            before = prev.get("avail")
            last_notified = prev.get("notified_at", 0.0)

            if before is None:
                # prima volta che vediamo questa zona: memorizzo senza avvisare,
                # tranne se i posti ci sono gia' e non siamo al primissimo avvio
                if avail > 0 and not first_run:
                    changes.append((zone, avail, 0))
            elif avail != before:
                if avail > 0:
                    changes.append((zone, avail, before))
                elif cfg.get("notify_on_gone"):
                    changes.append((zone, 0, before))
            elif avail > 0 and cfg.get("repeat_minutes", 0) > 0 and last_notified > 0:
                # last_notified > 0 e' indispensabile: un promemoria ripete un avviso,
                # quindi un avviso ci deve essere stato. Senza questa condizione una
                # zona gia' disponibile alla prima lettura (che non genera avvisi) ha
                # last_notified a 0, e "adesso - 0" supera qualunque intervallo: il
                # promemoria partiva al secondo controllo invece che dopo N minuti.
                if now_ts - last_notified >= cfg["repeat_minutes"] * 60:
                    reminders.append((zone, avail, before))

            # seen_at = da quando la disponibilita' e' questa, non "ultima lettura".
            # Riscriverlo a ogni giro faceva cambiare il file anche quando non
            # cambiava nulla: su GitHub significava un commit ogni controllo, 96 al
            # giorno, e la cronologia del file diventava inservibile per capire
            # quando i posti si sono liberati davvero.
            invariata = before is not None and avail == before
            zstate[key] = {
                "avail": avail,
                "seen_at": prev.get("seen_at", now_ts) if invariata else now_ts,
                "notified_at": last_notified,
            }

        for group, is_reminder in ((changes, False), (reminders, True)):
            if not group:
                continue
            text = format_alert(cfg, event, group, reminder=is_reminder)
            silent = is_quiet(cfg) and all(n == 0 for _, n, _ in group)
            if tg.send(text, silent=silent):
                log.info("Telegram inviato: %s -> %s", event.get("label", pcode),
                         ", ".join(z + ":" + str(n) for z, n, _ in group))
                for zone, _, _ in group:
                    zstate[pcode + "|" + zone]["notified_at"] = now_ts

        save_state(state)
        if idx < len(cfg["events"]) - 1:
            time.sleep(random.uniform(1.5, 3.5))   # gentile con il server

    # battito: conferma periodica che il programma e' vivo
    hb = float(cfg.get("heartbeat_hours") or 0)
    if hb > 0 and now_ts - state.get("last_heartbeat", 0.0) >= hb * 3600:
        rows = []
        for event in cfg["events"]:
            vals = []
            for zone in cfg["zones_watch"]:
                key = event["pcode"] + "|" + zone.strip().upper()
                if key in zstate:
                    vals.append(zone_name(zone) + ": " + str(zstate[key]["avail"]))
            rows.append("• <b>" + html.escape(short_when(event)) + "</b>\n   " +
                        (", ".join(vals) or "n/d"))
        if tg.send("\U0001F7E2 <b>Monitor attivo</b>\n\n" + "\n".join(rows), silent=True):
            state["last_heartbeat"] = now_ts
            save_state(state)

    return ok_count, fail_count


# --------------------------------------------------------------------------- #
# Comandi
# --------------------------------------------------------------------------- #

def cmd_discover(cfg: dict) -> None:
    with Shop(cfg) as shop:
        events = shop.discover_events()
    if not events:
        print("Nessuna recita trovata: controlla il campo show_filter in config.json")
        return
    cfg["events"] = events
    save_config(cfg)
    print("Trovate " + str(len(events)) + " recite, salvate in config.json:")
    for e in events:
        print("  " + e["pcode"] + "  " + e["label"])


def cmd_check(cfg: dict) -> None:
    if not cfg["events"]:
        print("Nessuna recita in config.json: lancia prima  python monitor_arena.py discover")
        return
    with Shop(cfg) as shop:
        print("")
        for event in cfg["events"]:
            try:
                zones = shop.availability(event["pcode"])
            except Exception as exc:
                print("  " + event["label"] + ": ERRORE " + str(exc))
                continue
            watch = watched_zones(cfg, zones)
            flag = "   <<< POSTI LIBERI" if any(v >= cfg["min_seats"] for v in watch.values()) else ""
            print("  " + event["label"])
            print("     " + "   ".join(k + ": " + str(v) for k, v in sorted(zones.items())) + flag)
            time.sleep(1.5)
        print("")


def notify_failure(cfg: dict, state: dict, tg: Telegram, msg: str) -> None:
    """Avvisa che il monitor non riesce a leggere il sito, ma non piu' di una
    volta ogni failure_alert_hours: su GitHub il controllo gira ogni 15 minuti
    e un blocco permanente genererebbe decine di messaggi al giorno."""
    now = time.time()
    window = float(cfg.get("failure_alert_hours") or 6) * 3600
    if now - float(state.get("last_failure_alert") or 0) >= window:
        if tg.send("⚠️ <b>Il monitor non riesce a leggere il sito</b>\n\n" +
                   html.escape(msg[:300]) +
                   "\n\n<i>Finche' non si risolve non ti arrivano avvisi sui posti.</i>",
                   silent=True):
            state["last_failure_alert"] = now
    save_state(state)


def cmd_once(cfg: dict) -> None:
    """Un solo giro completo, con notifiche, poi esce.
    E' la modalita' usata da GitHub Actions: la ripetizione la fa lo scheduler."""
    tg = Telegram(cfg["telegram"]["bot_token"], cfg["telegram"]["chat_id"])
    if not tg.ready:
        log.warning("Telegram non configurato: scrivo solo nel log.")
    if not cfg["events"]:
        sys.exit("Nessuna recita in configurazione: serve 'discover' oppure il campo events.")

    state = load_state()
    first_run = not state.get("zones")
    try:
        with Shop(cfg) as shop:
            ok, fail = run_cycle(shop, cfg, state, tg, first_run=first_run)
    except Exception as exc:
        log.error("Giro fallito prima di cominciare: %s", exc)
        notify_failure(cfg, state, tg, str(exc))
        sys.exit(1)

    log.info("Giro finito: %d letture riuscite, %d fallite", ok, fail)
    if ok == 0:
        notify_failure(cfg, state, tg, "Nessuna delle %d recite e' stata letta." % len(cfg["events"]))
        sys.exit(1)

    if float(state.get("last_failure_alert") or 0) > 0:
        tg.send("\U0001F7E2 Il monitor e' tornato a leggere il sito regolarmente.", silent=True)
        state["last_failure_alert"] = 0
        save_state(state)


def cmd_watch(cfg: dict) -> None:
    tg = Telegram(cfg["telegram"]["bot_token"], cfg["telegram"]["chat_id"])
    if not tg.ready:
        print("ATTENZIONE: Telegram non configurato, gli avvisi finiranno solo nel log.")
        print("Lancia  python monitor_arena.py setup  per collegare il bot.\n")
    if not cfg["events"]:
        print("Nessuna recita in config.json: lancia prima  python monitor_arena.py discover")
        return

    log.info("=" * 70)
    log.info("Avvio monitor | %d recite | zone: %s | min %d posti | ogni ~%ds",
             len(cfg["events"]), ", ".join(cfg["zones_watch"]),
             cfg["min_seats"], cfg["interval_seconds"])

    state = load_state()
    first_run = not state.get("zones")
    shop = Shop(cfg)
    shop.start()
    cycles, failures, notified_down = 0, 0, False

    try:
        while True:
            try:
                run_cycle(shop, cfg, state, tg, first_run=first_run)
                first_run = False
                failures = 0
                if notified_down:
                    tg.send("\U0001F7E2 Monitor ripartito, torno a controllare.", silent=True)
                    notified_down = False
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                failures += 1
                log.error("Ciclo fallito (%d di fila): %s", failures, exc)
                if failures >= 3 and not notified_down:
                    tg.send("⚠️ <b>Monitor in difficolta'</b>\n" +
                            html.escape(str(exc)[:300]), silent=True)
                    notified_down = True
                try:
                    shop.start()
                except Exception as exc2:
                    log.error("Riavvio browser fallito: %s", exc2)
                time.sleep(min(60 * failures, 600))
                continue

            cycles += 1
            if cycles % 80 == 0:          # riavvio periodico: niente memoria che cresce
                log.info("Riavvio preventivo del browser dopo %d cicli", cycles)
                shop.start()

            time.sleep(cfg["interval_seconds"] + random.uniform(0, cfg.get("jitter_seconds", 0)))
    except KeyboardInterrupt:
        log.info("Interrotto da tastiera. Chiudo.")
    finally:
        shop.stop()


def main() -> None:
    ap = argparse.ArgumentParser(description="Monitor posti Arena di Verona -> Telegram")
    ap.add_argument("comando", nargs="?", default="watch",
                    choices=["setup", "test", "discover", "check", "once", "watch"])
    args = ap.parse_args()
    cfg = load_config()
    {"setup": cmd_setup, "test": cmd_test, "discover": cmd_discover,
     "check": cmd_check, "once": cmd_once, "watch": cmd_watch}[args.comando](cfg)


if __name__ == "__main__":
    main()
