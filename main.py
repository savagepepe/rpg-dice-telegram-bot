"""
RPG Dice Bot per Telegram (versione Railway/Docker)
- Stile fantasy medievale
- Macro: /d4, /d6, /d8, /d10, /d12, /d20
  Ogni macro lancia: 1dX! 1d6! (dadi separati, non sommati)
- Comando generico: /dadi <espressione>
- Supporto esplosioni (!)
- Immagine risultato:
  - Dimensioni 650x380
  - Due colonne: sinistra = dado tiro, destra = dado fortuna (1d6)
  - Cornice dorata medievale (doppio bordo)
  - Titolo "Risultato Tiri" in alto, bilanciato
  - Etichette "Dado Tiro" / "Dado Fortuna" bilanciate sopra ogni dado
  - Sfondo NERO
  - Sagoma del dado in trasparenza, colore SEPPIA MOLTO CHIARO
  - Sagoma regolata per NON COPRIRE le altre scritte (titolo, etichette, dettagli)
  - Numero del risultato AL CENTRO della sagoma (orizzontale e verticale)
  - Font: DEFAULT di Pillow
  - Dimensione numero: REGOLABILE (default 80)
  - Colore risultato:
      - rosso se il primo lancio è 1
      - verde se c'è¶¶ almeno un'esplosione
      - BIANCO se neutro
  - Dettaglio lanci sotto, bilanciato
"""

import logging
import os
import random
import re
import io
import math
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
        "primo_lancio": dettagli[0]["rolls"][0] if dettagli and dettagli[0]["rolls"] else None,
    }

def roll_expression(expr: str):
    tokens = parse_expression(expr)
    risultati = []
    for t in tokens:
        risultati.append(roll_token(t))
    return risultati


# =========================
# DISEGNO SAGOME DADI
# =========================

def draw_d4_shape(draw, cx, cy, size, color):
    h = size * math.sqrt(3) / 2
    points = [
        (cx, cy - h * 2/3),
        (cx - size/2, cy + h/3),
        (cx + size/2, cy + h/3),
    ]
    draw.polygon(points, fill=color)

def draw_d6_shape(draw, cx, cy, size, color):
    half = size / 2
    draw.rectangle(
        [cx - half, cy - half, cx + half, cy + half],
        fill=color,
    )

def draw_d8_shape(draw, cx, cy, size, color):
    half = size / 2
    points = [
        (cx, cy - half),
        (cx + half, cy),
        (cx, cy + half),
        (cx - half, cy),
    ]
    draw.polygon(points, fill=color)

def draw_d10_shape(draw, cx, cy, size, color):
    w = size / 2
    h = size * 0.8
    points = [
        (cx, cy - h),
        (cx + w, cy),
        (cx, cy + h),
        (cx - w, cy),
    ]
    draw.polygon(points, fill=color)

def draw_d12_shape(draw, cx, cy, size, color):
    r = size / 2
    points = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=color)

def draw_d20_shape(draw, cx, cy, size, color):
    r = size / 2
    points = []
    for i in range(6):
        angle = math.radians(-90 + i * 60)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=color)

def draw_d100_shape(draw, cx, cy, size, color):
    r = size / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

def draw_die_shape(draw, faces, cx, cy, size, color):
    if faces == 4:
        draw_d4_shape(draw, cx, cy, size, color)
    elif faces == 6:
        draw_d6_shape(draw, cx, cy, size, color)
    elif faces == 8:
        draw_d8_shape(draw, cx, cy, size, color)
    elif faces == 10:
        draw_d10_shape(draw, cx, cy, size, color)
    elif faces == 12:
        draw_d12_shape(draw, cx, cy, size, color)
    elif faces == 20:
        draw_d20_shape(draw, cx, cy, size, color)
    elif faces == 100:
        draw_d100_shape(draw, cx, cy, size, color)
    else:
        draw_d100_shape(draw, cx, cy, size, color)


# =========================
# GENERAZIONE IMMAGINE
# =========================

def draw_fantasy_result(results: list[dict]) -> bytes:
    """
    results: lista di dict come restituiti da roll_expression.
    Genera un'immagine "scheda risultato":
      - 650x380
      - due colonne: sinistra = primo token (dado tiro), destra = secondo (fortuna)
      - cornice dorata medievale (doppio bordo)
      - titolo "Risultato Tiri" in alto, bilanciato
      - etichette "Dado Tiro" / "Dado Fortuna" bilanciate sopra ogni dado
      - sfondo NERO
      - sagoma dado colore SEPPIA MOLTO CHIARO in trasparenza
      - sagoma regolata per NON COPRIRE titolo/etichette/dettagli
      - risultato AL CENTRO della sagoma (orizzontale e verticale)
      - FONT: DEFAULT di Pillow
      - DIMENSIONE NUMERO: REGOLABILE (default 80)
      - colore risultato: rosso (primo lancio = 1), verde (esplosioni), BIANCO (neutro)
      - dettaglio lanci sotto, bilanciato
    """
    width, height = 650, 380

    # =========================
    # PARAMETRO DA REGOLARE:
    # =========================
    RESULT_FONT_SIZE = 80  # Cambia questo valore per ingrandire/rimpicciolire il numero
    # =========================

    # Sfondo NERO
    bg_color = (10, 10, 12)
    # Sagoma dado: colore SEPPIA MOLTO CHIARO
    shape_base = (230, 215, 180)
    shape_alpha = 80
    shape_color = shape_base + (shape_alpha,)

    # Colori
    text_color = (210, 200, 180)
    oro_color = (180, 150, 60)
    rosso_color = (200, 60, 60)
    verde_color = (60, 180, 60)
    neutro_color = (255, 255, 255)  # BIANCO

    img = Image.new("RGBA", (width, height), bg_color + (255,))
    draw = ImageDraw.Draw(img)

    # Font DEFAULT di Pillow
    title_font = ImageFont.load_default()
    label_font = ImageFont.load_default()
    detail_font = ImageFont.load_default()
    result_font_base = ImageFont.load_default(size=RESULT_FONT_SIZE)

    # Cornice dorata “medievale” (doppio bordo)
    border_color = oro_color
    draw.rectangle([0, 0, width - 1, height - 1], outline=border_color, width=6)
    inset = 10
    draw.rectangle([inset, inset, width - 1 - inset, height - 1 - inset], outline=border_color, width=2)

    # Titolo "Risultato Tiri" in alto, bilanciato
    title = "Risultato Tiri"
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2, 8), title, fill=text_color, font=title_font)

    # Colonne
    columns = []
    if len(results) >= 2:
        columns = [
            (results[0], "Dado Tiro", width * 0.25),
            (results[1], "Dado Fortuna", width * 0.75),
        ]
    elif len(results) == 1:
        columns = [
            (results[0], "Dado Tiro", width * 0.25),
        ]

    for res, label, cx in columns:
        # Centro verticale leggermente più basso per dare spazio sopra/sotto
        cy = height * 0.58

        # Sagoma dado (seppia molto chiaro) - PIÙ¹ PICCOLA e senza coprire le scritte
        # Prima: height * 0.40, ora: height * 0.32
        die_size = height * 0.32
        draw_die_shape(draw, res["faces"], cx, cy, die_size, shape_color)

        # Font numero con dimensione regolabile
        result_font = result_font_base

        # Colore risultato
        primo_lancio = res.get("primo_lancio")
        has_explode = res["explode"] and any(len(d["rolls"]) > 1 for d in res["dettagli"])

        if primo_lancio == 1:
            result_color = rosso_color
        elif has_explode:
            result_color = verde_color
        else:
            result_color = neutro_color  # BIANCO

        totale_str = str(res["totale"])
        # Centro esatto della sagoma: (cx, cy)
        bbox = draw.textbbox((0, 0), totale_str, font=result_font)
        rw = bbox[2] - bbox[0]
        rh = bbox[3] - bbox[1]

        # Numero centrato sia in orizzontale che in verticale rispetto al centro della sagoma
        x_num = cx - rw / 2
        y_num = cy - rh / 2
        draw.text((x_num, y_num), totale_str, fill=result_color, font=result_font)

        # Etichetta "Dado Tiro" / "Dado Fortuna" bilanciata sopra il dado
        lw = draw.textlength(label, font=label_font)
        draw.text((cx - lw / 2, 32), label, fill=text_color, font=label_font)

        # Dettaglio lanci sotto, bilanciato
        details_lines = []
        for j, det in enumerate(res["dettagli"], start=1):
            rolls_str = ", ".join(str(r) for r in det["rolls"])
            explode_mark = " (esplode)" if res["explode"] and len(det["rolls"]) > 1 else ""
            line = f"Dado {j}: [{rolls_str}] = {det['subtotale']}{explode_mark}"
            details_lines.append(line)

        if res["mod"] != 0:
            mod_sign = "+" if res["mod"] > 0 else ""
            details_lines.append(f"Mod: {mod_sign}{res['mod']} | Tot: {res['totale']}")

        # Dettagli posizionati sotto la sagoma, con margine
        y_detail = cy + die_size * 0.80
        for line in details_lines:
            dw = draw.textlength(line, font=detail_font)
            draw.text((cx - dw / 2, y_detail), line, fill=text_color, font=detail_font)
            y_detail += 18

    # Converti in RGB
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# =========================
# HANDLER TELEGRAM
# =========================

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
        "I dadi con ! esplodono. Il 1d6! è il 'Dado Fortuna'."
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