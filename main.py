"""
RPG Dice Bot per Telegram (versione Railway/Docker)
- Solo testo, niente immagine
- Macro: /d4, /d6, /d8, /d10, /d12, /d20
  Ogni macro lancia: 1dX! 1d6! (dadi separati, non sommati)
- Comando generico: /dadi <espressione>
- Supporto esplosioni (!)
- Risultati mostrati come messaggio di testo formattato
- Indicazioni:
  - se il dado esplode: "(esplode)" accanto al totale
  - se il primo lancio è 1: "(1)" accanto al totale
  - se SIA dado tiro SIA dado fortuna hanno primo lancio = 1:
    appare una scritta "🔴 FALLIMENTO CRITICO 🔴" sotto i risultati
- Nuova funzione:
  - /iniziativa nome1 nome2 nome3 ...
    - estrae una carta a testa da un mazzo poker + 2 jolly
    - SENZA ripetere carte già usate, finché±± non esce almeno un jolly
    - quando esce almeno un jolly, il mazzo usato viene resettato automaticamente
    - /iniziativa riavvio → azzera manualmente il mazzo usato
    - ordine semi: Cuori ♥️ > Quadri ♦️ > Fiori ♣️ > Picche ♠️
    - mostra: nome – valore + emoji seme (es. A ♥️, K ♠️, Jolly 🃏)
"""

import logging
import os
import random
import re
from telegram import Update
from telegram.ext import Application, CommandHandler

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


def format_result(results: list[dict]) -> str:
    """
    Formatta i risultati come messaggio di testo con:
      - indicazione (esplode) se il dado esplode
      - indicazione (1) se il primo lancio è 1
      - se SIA dado tiro SIA dado fortuna hanno primo lancio = 1:
        aggiunge "🔴 FALLIMENTO CRITICO 🔴" sotto i risultati
    Usa la formattazione Markdown di Telegram.
    """
    lines = []

    primo_tiro_1 = False
    primo_fortuna_1 = False

    if len(results) >= 1:
        res_tiro = results[0]
        lines.append(f"Dado Tiro ({res_tiro['raw']}):")
        for j, det in enumerate(res_tiro["dettagli"], start=1):
            rolls_str = ", ".join(str(r) for r in det["rolls"])
            explode_mark = " (esplode)" if res_tiro["explode"] and len(det["rolls"]) > 1 else ""
            lines.append(f"  Dado {j}: [{rolls_str}] = {det['subtotale']}{explode_mark}")
        if res_tiro["mod"] != 0:
            mod_sign = "+" if res_tiro["mod"] > 0 else ""
            lines.append(f"  Modificatore: {mod_sign}{res_tiro['mod']}")

        primo_lancio = res_tiro.get("primo_lancio")
        has_explode = res_tiro["explode"] and any(len(d["rolls"]) > 1 for d in res_tiro["dettagli"])

        if primo_lancio == 1:
            primo_tiro_1 = True
            lines.append(f"  *Totale tiro: {res_tiro['totale']} (1)*")
        elif has_explode:
            lines.append(f"  *Totale tiro: {res_tiro['totale']} (esplode)*")
        else:
            lines.append(f"  *Totale tiro: {res_tiro['totale']}*")

        lines.append("")

    if len(results) >= 2:
        res_fortuna = results[1]
        lines.append(f"Dado Fortuna ({res_fortuna['raw']}):")
        for j, det in enumerate(res_fortuna["dettagli"], start=1):
            rolls_str = ", ".join(str(r) for r in det["rolls"])
            explode_mark = " (esplode)" if res_fortuna["explode"] and len(det["rolls"]) > 1 else ""
            lines.append(f"  Dado {j}: [{rolls_str}] = {det['subtotale']}{explode_mark}")
        if res_fortuna["mod"] != 0:
            mod_sign = "+" if res_fortuna["mod"] > 0 else ""
            lines.append(f"  Modificatore: {mod_sign}{res_fortuna['mod']}")

        primo_lancio = res_fortuna.get("primo_lancio")
        has_explode = res_fortuna["explode"] and any(len(d["rolls"]) > 1 for d in res_fortuna["dettagli"])

        if primo_lancio == 1:
            primo_fortuna_1 = True
            lines.append(f"  *Totale fortuna: {res_fortuna['totale']} (1)*")
        elif has_explode:
            lines.append(f"  *Totale fortuna: {res_fortuna['totale']} (esplode)*")
        else:
            lines.append(f"  *Totale fortuna: {res_fortuna['totale']}*")

    # Se entrambi i primi lanci sono 1 → Fallimento critico
    if primo_tiro_1 and primo_fortuna_1:
        lines.append("")
        lines.append("*🔴 FALLIMENTO CRITICO 🔴*")

    return "\n".join(lines)


# =========================
# INIZIATIVA CON CARTE (MEMORIA IN RAM)
# =========================

# Mazzo da poker + 2 jolly
# Valori: A, 2–10, J, Q, K, Jolly
# Semi: ♠️ ♥️ ♦️ ♣️
# Ordine di valore (dal più alto al più basso):
#   Jolly, A, K, Q, J, 10, 9, 8, 7, 6, 5, 4, 3, 2
# Ordine di seme (a parità±¹ di valore): Cuori ♥️ > Quadri ♦️ > Fiori ♣️ > Picche ♠️

VALORI_CARTE = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SEMI_CON_PUNTEGGIO = [
    ("♠️", 0),  # Picche
    ("♣️", 1),  # Fiori
    ("♦️", 2),  # Quadri
    ("♥️", 3),  # Cuori
]

# Variabili globali per la memoria del mazzo usato
MAZZO_USATO = set()  # insieme di tuple (valore, seme) già estratte
MAZZO_RESETTATO_PER_JOLLY = True  # True = il mazzo è "pulito", non è ancora uscito jolly dall'ultimo reset

def crea_mazzo_completo():
    """
    Crea l'elenco completo di tutte le carte del mazzo (poker + 2 jolly).
    Ogni carta è una tupla (valore, seme).
    """
    mazzo = []
    for valore in VALORI_CARTE:
        for seme, _ in SEMI_CON_PUNTEGGIO:
            mazzo.append((valore, seme))
    # Aggiungo 2 jolly
    mazzo.append(("Jolly", "🃏"))
    mazzo.append(("Jolly", "🃏"))
    return mazzo

def ordine_valore_carta(valore: str) -> int:
    if valore == "Jolly":
        return 100
    if valore == "A":
        return 14
    if valore == "K":
        return 13
    if valore == "Q":
        return 12
    if valore == "J":
        return 11
    try:
        return int(valore)
    except ValueError:
        return 0

def ordine_seme(seme: str) -> int:
    for s, punteggio in SEMI_CON_PUNTEGGIO:
        if s == seme:
            return punteggio
    return 0

def resetta_mazzo():
    """
    Resetta il mazzo usato (chiamato quando esce almeno un jolly o con /iniziativa riavvio).
    """
    global MAZZO_USATO, MAZZO_RESETTATO_PER_JOLLY
    MAZZO_USATO = set()
    MAZZO_RESETTATO_PER_JOLLY = True

def estrai_carta_per_iniziativa(nomi: list[str]):
    """
    Dato un elenco di nomi, estrae una carta a testa da un mazzo poker + 2 jolly,
    SENZA ripetere carte già usate (memorizzate in MAZZO_USATO),
    finché±± non esce almeno un jolly.
    Quando esce almeno un jolly, il mazzo usato viene resettato automaticamente.
    Restituisce una lista di tuple:
      [(nome, valore, seme), ...]
    già ordinata per valore e seme.
    """
    global MAZZO_USATO, MAZZO_RESETTATO_PER_JOLLY

    mazzo_completo = crea_mazzo_completo()

    # Carte disponibili = tutte quelle non ancora in MAZZO_USATO
    carte_disponibili = [c for c in mazzo_completo if c not in MAZZO_USATO]

    # Se per qualche motivo non ci sono abbastanza carte, resetto
    if len(carte_disponibili) < len(nomi):
        resetta_mazzo()
        carte_disponibili = crea_mazzo_completo()

    random.shuffle(carte_disponibili)

    estrazioni = []
    jolly_estratto = False

    for nome in nomi:
        if not carte_disponibili:
            # Se finiscono le carte, resetto e continuo
            resetta_mazzo()
            carte_disponibili = crea_mazzo_completo()
            random.shuffle(carte_disponibili)

        carta = carte_disponibili.pop()
        valore, seme = carta
        estrazioni.append((nome, valore, seme))

        # Segno la carta come usata
        MAZZO_USATO.add(carta)

        # Se è un jolly, segno che è uscito un jolly
        if valore == "Jolly":
            jolly_estratto = True

    # Se è uscito almeno un jolly, resetto il mazzo usato per il prossimo turno
    if jolly_estratto:
        resetta_mazzo()

    # Ordino per valore (decrescente) e, a parità±¹, per seme (decrescente)
    estrazioni.sort(
        key=lambda x: (ordine_valore_carta(x[1]), ordine_seme(x[2])),
        reverse=True
    )
    return estrazioni


def format_iniziativa(estrazioni: list[tuple[str, str, str]]) -> str:
    lines = []
    for i, (nome, valore, seme) in enumerate(estrazioni, start=1):
        lines.append(f"{i}. {nome} – {valore} {seme}")
    return "\n".join(lines)


# =========================
# HANDLER TELEGRAM
# =========================

async def start(update: Update, context):
    await update.message.reply_text(
        "Ciao! Sono il tuo bot RPG per lanci di dadi e iniziative (solo testo).\n\n"
        "Dadi:\n"
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
        "Iniziativa:\n"
        "/iniziativa nome1 nome2 nome3 ...\n"
        "Estrae una carta a testa (poker + 2 jolly) senza ripetere carte già usate.\n"
        "Quando esce almeno un jolly, il mazzo usato viene resettato automaticamente.\n"
        "/iniziativa riavvio → azzera manualmente il mazzo usato.\n"
        "Ordine semi: Cuori ♥️ > Quadri ♦️ > Fiori ♣️ > Picche ♠️\n\n"
        "I dadi con ! esplodono. Il 1d6! è il 'Dado Fortuna'.\n"
        "Se entrambi i dadi fanno 1 al primo lancio, appare 'FALLIMENTO CRITICO'."
    )

async def help_cmd(update: Update, context):
    await update.message.reply_text(
        "Comandi:\n"
        "/start – Benvenuto\n"
        "/aiuto – Questa guida\n"
        "/dadi <espressione> – Lancio libero\n"
        "/d4, /d6, /d8, /d10, /d12, /d20 – Macro\n"
        "/iniziativa nome1 nome2 ... – Estrazione carte per iniziativa\n"
        "/iniziativa riavvio – Azzera il mazzo usato\n\n"
        "Esempi:\n"
        "/dadi 1d20+5 1d6!\n"
        "/iniziativa Alice Bob Carlo\n"
        "/iniziativa riavvio"
    )

async def macro_handler(update: Update, context):
    comando = update.message.text.strip().lower()
    if not comando.startswith("/d"):
        return
    dado_part = comando[2:]
    if dado_part not in ("4", "6", "8", "10", "12", "20"):
        return
    expr = f"1d{dado_part}! 1d6!"
    await lancia_e_invia_testo(update, expr, macro_name=comando[1:])

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
    await lancia_e_invia_testo(update, expr)

async def lancia_e_invia_testo(update: Update, expr: str, macro_name: str | None = None):
    try:
        risultati = roll_expression(expr)
    except ValueError as e:
        await update.message.reply_text(f"Errore nell'espressione: {e}")
        return

    testo = format_result(risultati)
    caption = f"Tiro: {expr}"
    if macro_name:
        caption = f"Macro: {macro_name}\n{expr}"

    messaggio = f"{caption}\n\n{testo}"
    await update.message.reply_text(messaggio, parse_mode="Markdown")

async def iniziativa_handler(update: Update, context):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: /iniziativa nome1 nome2 nome3 ...\n"
            "Esempio: /iniziativa Alice Bob Carlo\n"
            "Per azzerare il mazzo: /iniziativa riavvio"
        )
        return

    # Se il primo argomento è "riavvio", resetto il mazzo
    if args[0].lower() == "riavvio":
        resetta_mazzo()
        await update.message.reply_text(
            "*Iniziativa:* mazzo usato azzerato.\n"
            "La prossima estrazione ripartirà±¹ da un mazzo pulito.",
            parse_mode="Markdown"
        )
        return

    nomi = args
    estrazioni = estrai_carta_per_iniziativa(nomi)
    testo = format_iniziativa(estrazioni)

    messaggio = f"*Iniziativa:*\n{testo}"
    await update.message.reply_text(messaggio, parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("aiuto", help_cmd))
    app.add_handler(CommandHandler("dadi", dadi_handler))
    app.add_handler(CommandHandler("iniziativa", iniziativa_handler))
    for dado in ("d4", "d6", "d8", "d10", "d12", "d20"):
        app.add_handler(CommandHandler(dado, macro_handler))
    logging.info("Bot RPG avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()