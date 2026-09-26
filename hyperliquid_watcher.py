"""
Hyperliquid trader koevetes -> Telegram push ertesito (GitHub Actions valtozat)
================================================================================

Ez a szkript EGYSZER fut le, majd kilep -- a GitHub Actions egy utemezes
szerint (pl. 5 percenkent) ujra es ujra elinditja. Az allapotat (hogy
milyen koetesekrol ertesitett mar) egy seen_fills.json nevu fajlban
tarolja, amit a workflow visszair a repoba minden futas utan.

Elso futaskor NEM kuld ertesitest a mar meglevo koetesekrol -- csak
"megjegyzi" oket, es mostantol csak az UJ koeteseket jelzi.

Szukseges kornyezeti valtozok (GitHub Secrets-kent beallitva):
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID
"""

import os
import json
import requests

TRADER_ADDRESS = "0x0fb66804703a2ff1f56233ec542f2c849e6fbaae"
STATE_FILE = "seen_fills.json"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def get_user_fills():
    payload = {"type": "userFills", "user": TRADER_ADDRESS}
    resp = requests.post(HL_INFO_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fill_key(fill):
    return [fill.get("tid"), fill.get("oid"), fill.get("time"), fill.get("hash")]


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(tuple(x) for x in json.load(f))
    return None  # None = meg nem volt inditva, ez lesz az elso futas


def save_seen(seen_set):
    with open(STATE_FILE, "w") as f:
        json.dump([list(x) for x in seen_set], f)


def send_telegram_message(text):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    requests.post(TELEGRAM_SEND_URL, data=payload, timeout=15)


def format_fill(fill):
    coin = fill.get("coin", "?")
    side_raw = fill.get("side")
    side = "VETEL" if side_raw == "B" else "ELADAS" if side_raw == "A" else side_raw
    direction = fill.get("dir", "")
    px = fill.get("px")
    sz = fill.get("sz")
    closed_pnl = fill.get("closedPnl")

    pnl_line = ""
    try:
        pnl_val = float(closed_pnl)
        if pnl_val != 0:
            jel = "+" if pnl_val > 0 else ""
            pnl_line = f"Realizalt PnL: {jel}{pnl_val:.2f} USDC\n"
    except (TypeError, ValueError):
        pass

    return (
        f"\u26a1 <b>Uj koetes: {coin}</b>\n"
        f"Tipus: {direction or side}\n"
        f"Ar: {px}\n"
        f"Meret: {sz}\n"
        f"{pnl_line}"
        f'<a href="https://app.hyperliquid.xyz/explorer/address/{TRADER_ADDRESS}">Trader profilja</a>'
    )


def main():
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        raise SystemExit("Hianyzo TELEGRAM_BOT_TOKEN vagy TELEGRAM_CHAT_ID kornyezeti valtozo")

    fills = get_user_fills()
    seen = load_seen()

    if seen is None:
        seen_set = set(tuple(fill_key(f)) for f in fills)
        save_seen(seen_set)
        print(f"Elso futas: {len(seen_set)} meglevo koetes elmentve, ertesites nem kuldve.")
        return

    new_fills = [f for f in fills if tuple(fill_key(f)) not in seen]
    new_fills.sort(key=lambda f: f.get("time", 0))

    for f in new_fills:
        send_telegram_message(format_fill(f))
        seen.add(tuple(fill_key(f)))

    if new_fills:
        save_seen(seen)
        print(f"{len(new_fills)} uj koetesrol kuldve ertesites.")
    else:
        print("Nincs uj koetes ebben a futasban.")


if __name__ == "__main__":
    main()
