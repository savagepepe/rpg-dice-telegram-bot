"""
RPG Dice Bot per Telegram (versione Docker/cloud)
- Stile fantasy
- Macro: /d4, /d6, /d8, /d10, /d12, /d20
  Ogni macro lancia: 1dX! 1d6! (dadi separati, non sommati)
- Comando generico: /dadi <espressione>
- Supporto esplosioni (!)
- Immagine risultato in stile fantasy
"""

import logging
import os
import random
import re
import io
from telegram import Update
from telegram.ext import Application, CommandHandler
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Manca TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN_RE = re.compile(
    r"""
    ^\s*
    (?P<qty>\d+)?
    d
    (?P<faces>\d+)
    (?P<mod>[+-]\d+)?
    (?P<explode>!)?
    \s*$
    """,
    re.VERBOSE,
)

def parse_expression(expr: str):
    tokens = expr.strip().split()
    parsed = []
    for t in tokens:
        m = TOKEN_RE.match(t)
        if not m:
            raise ValueError(f"Token non valido: {t}")
        qty = int(m.group("qty") or "1")
        faces = int(m.group("faces"))
        mod_str = m.group("mod")
        mod = int(mod_str) if mod_str else 0
        explode = bool(m.group("explode"))
        parsed.append({
            "qty": qty,
            "faces": faces,
            "mod": mod,
            "explode": explode,
            "raw": t,
        })
    return parsed

def roll_single_die(faces: int, explode: bool):
    rolls = []
    totale = 0
    while True:
        r = random.randint(1, faces)
        rolls.append(r)
        totale += r
        if not explode:
            break
        if r != faces:
            break
    return totale, rolls

def roll_token(token: dict):
    qty = token["qty"]
    faces = token["faces"]
    mod = token["mod"]
    explode = token["explode"]

    dettagli = []
    totale_dadi = 0

    for _ in range(qty):
        subtotale, rolls = roll_single_die(faces, explode)
        totale_dadi += subtotale
        dettagli.append({
            "rolls": rolls,
            "subtotale": subtotale,
        })

    totale = totale_dadi + mod

    return {
        "totale": totale,
        "dettagli": dettagli,
        "mod": mod,
        "faces": faces,
        "qty": qty,
        "explode": explode,
        "raw": token["raw"],
    }

def roll_expression(expr: str):
    tokens = parse_expression(expr)
    risultati = []
    for t in tokens:
        risultati.append(roll_token(t))
    return risultati

def draw_fantasy_result(results: list[dict]) -> bytes:
    width, height = 800, 600
    bg_color = (20, 20, 30)
    border_color = (200, 160, 60)
    text_color = (230, 230, 230)
    accent_color = (220, 140, 60)
    fortuna_color = (60, 120, 220)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    border_w = 10
    draw.rectangle(
        [0, 0, width - 1, height - 1],
        outline=border_color,
        width=border_w,
    )

    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        header_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
        text_font = ImageFont.truetype("DejaVuSans.ttf", 22)
        small_font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    title = "Risultato Tiri"
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2, 30), title, fill=text_color, font=title_font)

    y = 90

    for i, res in enumerate(results, start=1):
        is_fortuna = (
            res["faces"] == 6
            and res["qty"] == 1
            and res["mod"] == 0
            and "d6" in res["raw"].lower()
        )

        label = "Dado Fortuna" if is_fortuna else "Dado Tiro"
        color = fortuna_color if is_fortuna else accent_color

        box_x1, box_y1 = 40, y
        box_x2, box_y2 = width - 40, y + 140

        draw.rectangle(
            [box_x1, box_y1, box_x2, box_y2],
            fill=(30, 30, 45),
            outline=color,
            width=3,
        )

        draw.text((box_x1 + 20, box_y1 + 15), label, fill=color, font=header_font)
        formula = res["raw"]
        draw.text((box_x1 + 20, box_y1 + 55), f"Formula: {formula}", fill=text_color, font=text_font)

        details_y = box_y1 + 95
        for j, det in enumerate(res["dettagli"], start=1):
            rolls_str = ", ".join(str(r) for r in det["rolls"])
            explode_mark = " (esplode)" if res["explode"] else ""
            dado_text = f"Dado {j}: [{rolls_str}] = {det['subtotale']}{explode_mark}"
            dado_color = fortuna_color if is_fortuna else text_color
            draw.text((box_x1 + 30, details_y), dado_text, fill=dado_color, font=small_font)
            details_y += 25

        mod_str = ""
        if res["mod"] != 0:
            mod_str = f" {'+' if res['mod'] > 0 else ''}{res['mod']}"
        totale_text = f"Totale: {res['totale']}{mod_str}"
        totale_color = fortuna_color if is_fortuna else accent_color
        draw.text((box_x1 + 20, box_y2 - 35), totale_text, fill=totale_color, font=header_font)

        y = box_y2 + 30
        if y + 140 > height:
            break

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

async def start(update: Update, context):
    await update.message.reply_text(
        "Ciao! Sono il tuo bot RPG per lanci di dadi in stile fantasy.\n\n"
        "Macro disponibili:\n"
        "/d4  → 1d4! 1d6!\n"
        "/d6  → 1d6! 1d6!\n"
        "/d8  → 1d8! 1d6!\n"
        "/d10 → 1d10! 1d6!\n"
        "/d12 → 1d12! 1d6!\n"
        "/d20 → 1d20! 1d6!\n\n"
        "Puoi anche usare:\n"
        "/dadi 1d20+5 1d6!\n"
        "/dadi 2d8+3 1d6!\n"
        "/dadi 1d6! 1d4!\n\n"
        "I dadi con ! esplodono. Il 1d6! è il 'Dado Fortuna' (in blu)."
    )

async def help_cmd(update: Update, context):
    await update.message.reply_text(
        "Comandi:\n"
        "/start – Benvenuto\n"
        "/aiuto – Guida\n"
        "/dadi <espressione> – Lancio libero\n"
        "/d4, /d6, /d8, /d10, /d12, /d20 – Macro\n\n"
        "Esempi:\n"
        "/dadi 1d20+5 1d6!\n"
        "/dadi 2d8+3 1d6!"
    )

async def macro_handler(update: Update, context):
    comando = update.message.text.strip().lower()
    if not comando.startswith("/d"):
        return
    dado_part = comando[2:]
    if dado_part not in ("4", "6", "8", "10", "12", "20"):
        return
    expr = f"1d{dado_part}! 1d6!"
    await lancia_e_invia_immagine(update, expr, macro_name=comando[1:])

async def dadi_handler(update: Update, context):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: /dadi <espressione>\n"
            "Esempi:\n"
            "/dadi 1d20+5 1d6!\n"
            "/dadi 2d8+3 1d6!\n"
            "/dadi 1d6! 1d4!"
        )
        return
    expr = " ".join(args)
    await lancia_e_invia_immagine(update, expr)

async def lancia_e_invia_immagine(update: Update, expr: str, macro_name: str | None = None):
    try:
        risultati = roll_expression(expr)
    except ValueError as e:
        await update.message.reply_text(f"Errore nell'espressione: {e}")
        return

    img_bytes = draw_fantasy_result(risultati)
    caption = f"Tiro: {expr}"
    if macro_name:
        caption = f"Macro: {macro_name}\n{expr}"

    await update.message.reply_photo(photo=img_bytes, caption=caption)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("aiuto", help_cmd))
    app.add_handler(CommandHandler("dadi", dadi_handler))
    for dado in ("d4", "d6", "d8", "d10", "d12", "d20"):
        app.add_handler(CommandHandler(dado, macro_handler))
    logging.info("Bot RPG avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()