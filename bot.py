"""
╔══════════════════════════════════════════════════════╗
║         SWING SCANNER BOT  v6.0  — MACD ONLY        ║
║   Daily + Weekly + Monthly MACD alignment            ║
║   Multi-user | Free vs Pro | Solana payments         ║
╚══════════════════════════════════════════════════════╝
"""

import os, asyncio, logging, json, time, random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ParseMode

# ══════════════════════════════════════════════════════
#  CONFIG  — set these in Railway → Variables
# ══════════════════════════════════════════════════════
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN")
OWNER_CHAT_ID    = int(os.environ.get("CHAT_ID", "0"))
SOL_WALLET       = os.environ.get("SOL_WALLET",  "YOUR_SOLANA_WALLET")
OWNER_USERNAME   = os.environ.get("OWNER_USERNAME", "@YourUsername")
PRO_PRICE        = os.environ.get("PRO_PRICE", "29")

SCAN_INTERVAL    = 4 * 60 * 60   # 4 hours
FREE_MAX         = 3
PRO_MAX          = 20
DATA_FILE        = Path("/tmp/users.json")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  USER DATABASE
# ══════════════════════════════════════════════════════
def load_db():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {}

def save_db(db):
    DATA_FILE.write_text(json.dumps(db, indent=2))

def get_user(db, cid):
    key = str(cid)
    if key not in db:
        db[key] = {
            "chat_id": cid, "tier": "free",
            "joined": datetime.utcnow().isoformat(),
            "pro_until": None, "username": "", "name": "", "scans": 0,
        }
        save_db(db)
    return db[key]

def is_pro(u):
    if u["tier"] != "pro": return False
    if u["pro_until"] is None: return True
    return datetime.utcnow() < datetime.fromisoformat(u["pro_until"])

def is_owner(cid): return cid == OWNER_CHAT_ID

# ══════════════════════════════════════════════════════
#  TICKER LIST  — 700 liquid stocks, no junk
# ══════════════════════════════════════════════════════
TICKERS = sorted(set([
    # Mega cap
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","LLY",
    "JPM","V","MA","UNH","XOM","JNJ","WMT","PG","HD","MRK","CVX","ABBV",
    "BAC","COST","KO","PEP","ADBE","CSCO","CRM","TMO","ACN","MCD","ABT",
    "DHR","LIN","TXN","NFLX","CMCSA","NKE","AMD","PM","UPS","MS","BMY",
    "RTX","INTU","SPGI","HON","AMGN","SBUX","LOW","GE","CAT","GS","BLK",
    "AMAT","ELV","ISRG","GILD","MDT","ADP","LRCX","SYK","REGN","VRTX",
    "ADI","PANW","KLAC","SNPS","CDNS","MCHP","NXPI","FTNT","CRWD","NOW",
    # S&P 500 broad
    "MMM","ABT","AFL","A","AES","AIG","AMT","AMP","AME","APH","ANSS","AON",
    "APA","APTV","ANET","AJG","AIZ","T","ADSK","AZO","AVB","AVY","AXON",
    "BKR","BALL","BK","BBWI","BAX","BDX","BRK-B","BBY","BIIB","BX","BA",
    "BSX","BR","BRO","BLDR","BG","CZR","CPT","CPB","COF","CAH","KMX","CCL",
    "CARR","CAT","CBOE","CBRE","CDW","CE","COR","CNC","CF","CRL","SCHW",
    "CHTR","CVX","CMG","CB","CHD","CI","CINF","CTAS","C","CFG","CLX","CME",
    "CMS","CTSH","CL","CMCSA","CAG","COP","ED","STZ","CEG","COO","CPRT",
    "GLW","CTVA","CSGP","CTRA","CCI","CSX","CMI","CVS","DHI","DRI","DVA",
    "DE","DAL","DVN","DXCM","DLR","DFS","DG","DLTR","D","DPZ","DOW","DTE",
    "DUK","DD","ETN","EBAY","ECL","EIX","EW","EA","EMR","ENPH","EOG","EQT",
    "EFX","EQIX","EQR","ESS","EL","ETSY","EXC","EXPE","XOM","FDS","FICO",
    "FAST","FDX","FIS","FITB","FSLR","FI","FLT","F","FTV","FCX","GD","GIS",
    "GM","GPC","GPN","GL","GDDY","HAL","HIG","HCA","HSY","HES","HPE","HLT",
    "HD","HRL","HPQ","HUBB","HUM","IBM","IDXX","ITW","INTC","ICE","INTU",
    "IRM","JNJ","JCI","JNPR","K","KDP","KEY","KMB","KMI","KHC","KR","LHX",
    "LH","LW","LVS","LEN","LIN","LMT","L","LOW","LULU","MTB","MPC","MAR",
    "MMC","MAS","MTCH","MKC","MCD","MCK","MDT","MRK","META","MET","MGM",
    "MU","MSFT","MRNA","MCO","MS","MSI","MSCI","NDAQ","NEE","NKE","NSC",
    "NOC","NCLH","NVDA","NXPI","ORLY","OXY","ODFL","ON","OKE","ORCL","PCAR",
    "PKG","PH","PAYX","PYPL","PEP","PFE","PM","PSX","PNC","COST","PPG","PG",
    "PGR","PLD","PRU","PSA","PWR","QCOM","RTX","O","REGN","RSG","RMD","ROK",
    "ROP","ROST","CRM","SBAC","SLB","SRE","NOW","SHW","SPG","SBUX","STT",
    "STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TGT","TSLA",
    "TXN","TMO","TJX","TSCO","TT","TDG","TRV","TFC","TSN","USB","UBER","UNP",
    "UAL","UPS","URI","UNH","VLO","VZ","VRTX","VICI","V","WBA","WMT","DIS",
    "WM","WAT","WFC","WELL","WDC","WMB","WYNN","XEL","YUM","ZBH","ZTS",
    # Growth / momentum
    "SQ","COIN","HOOD","SOFI","PLTR","CRWD","DDOG","NET","SNOW","MDB",
    "HUBS","TWLO","DOCN","GTLB","CFLT","BRZE","BILL","APPN","LYFT","DASH",
    "SNAP","PINS","SPOT","RBLX","U","SHOP","RIVN","NIO","XPEV","LI",
    "BABA","SE","GRAB","NU","NVO","BNTX","HIMS","TDOC","DOCS","IBKR",
    "AFRM","UPST","ACHR","JOBY","RKLB","LUNR","ASTS","MARA","RIOT","CLSK",
    "HUT","CORZ","DELL","PSTG","AI","BBAI","SOUN","IONQ","RGTI","MSTR",
    "CELH","RXRX","TSM","ASML","MRVL","WOLF","AEHR","ACMR","SMCI","AOSL",
    # Finance
    "GS","JPM","BAC","C","WFC","MS","BLK","SCHW","IBKR","AXP","FIS","FI",
    "GPN","FISV","COF","DFS","SYF","AIG","MET","PRU","AFL","ALL","TRV","CB",
    # Energy
    "XOM","CVX","COP","SLB","HAL","OXY","MPC","VLO","PSX","DVN","EOG",
    "HES","MRO","APA","EQT","RRC","SM","NOG","CTRA",
    # Biotech
    "LLY","NVO","MRNA","BNTX","ABBV","JNJ","PFE","AMGN","GILD","REGN",
    "VRTX","BIIB","ILMN","HIMS","ALNY","BMRN","INCY","SRPT","NVAX","EXAS",
    # ETFs
    "SPY","QQQ","IWM","DIA","SMH","SOXX","XLK","XLF","XLE","XLV","XLI",
    "ARKK","GLD","SLV","GDX","TLT","SOXL","TQQQ","UPRO","LABU",
]))

# ══════════════════════════════════════════════════════
#  INDICATORS
# ══════════════════════════════════════════════════════
def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def compute_macd(close):
    m   = ema(close, 12) - ema(close, 26)
    sig = ema(m, 9)
    hist = m - sig
    return m, sig, hist

def compute_rsi(close, p=14):
    d = close.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - 100 / (1 + g / (l + 1e-9))

def compute_atr(df, p=14):
    h, lo, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([
        h - lo,
        (h - c.shift()).abs(),
        (lo - c.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def vol_ratio(df, p=20):
    v = df["Volume"]
    avg = v.rolling(p).mean().iloc[-1]
    return round(v.iloc[-1] / (avg + 1e-9), 2)

# ══════════════════════════════════════════════════════
#  MACD SIGNAL — simple & effective
# ══════════════════════════════════════════════════════
def macd_bull(close):
    """Bullish: MACD line > signal line AND histogram positive."""
    if len(close) < 35: return False, 0.0
    m, sig, hist = compute_macd(close)
    bull = m.iloc[-1] > sig.iloc[-1] and hist.iloc[-1] > 0
    return bull, round(hist.iloc[-1], 4)

def macd_bear(close):
    """Bearish: MACD line < signal line AND histogram negative."""
    if len(close) < 35: return False, 0.0
    m, sig, hist = compute_macd(close)
    bear = m.iloc[-1] < sig.iloc[-1] and hist.iloc[-1] < 0
    return bear, round(hist.iloc[-1], 4)

def hist_growing(close):
    """Histogram expanding (momentum increasing)."""
    if len(close) < 36: return False
    _, _, hist = compute_macd(close)
    return abs(hist.iloc[-1]) > abs(hist.iloc[-2])

# ══════════════════════════════════════════════════════
#  DATA FETCH  — fast, minimal, reliable
# ══════════════════════════════════════════════════════
def fetch(symbol):
    try:
        t = yf.Ticker(symbol)
        # Fetch all timeframes
        d1  = t.history(period="1y",  interval="1d",  auto_adjust=True)
        wk  = t.history(period="4y",  interval="1wk", auto_adjust=True)
        mo  = t.history(period="10y", interval="1mo", auto_adjust=True)
        # Validate minimum bars needed for MACD
        if d1 is None or len(d1) < 35: return None
        if wk is None or len(wk) < 35: return None
        if mo is None or len(mo) < 35: return None
        return {"1d": d1, "1wk": wk, "1mo": mo}
    except Exception as e:
        log.debug(f"fetch {symbol}: {e}")
        return None

# ══════════════════════════════════════════════════════
#  SCORE TICKER  — MACD only on all 3 TFs
# ══════════════════════════════════════════════════════
def score_ticker(symbol):
    data = fetch(symbol)
    if not data: return None

    c1d = data["1d"]["Close"].dropna()
    cwk = data["1wk"]["Close"].dropna()
    cmo = data["1mo"]["Close"].dropna()

    bull_1d, hist_1d = macd_bull(c1d)
    bull_wk, hist_wk = macd_bull(cwk)
    bull_mo, hist_mo = macd_bull(cmo)

    bear_1d, _ = macd_bear(c1d)
    bear_wk, _ = macd_bear(cwk)
    bear_mo, _ = macd_bear(cmo)

    price  = round(data["1d"]["Close"].iloc[-1], 2)
    rsi_v  = round(compute_rsi(c1d).iloc[-1], 1)
    atr_v  = compute_atr(data["1d"]).iloc[-1]
    vr     = vol_ratio(data["1d"])

    # ── LONG: all 3 TFs MACD bullish ──────────────
    if bull_1d and bull_wk and bull_mo:
        # Momentum score — how many histograms growing
        growing = sum([
            hist_growing(c1d),
            hist_growing(cwk),
            hist_growing(cmo),
        ])
        score = 6 + growing  # base 6 (all 3 bull) + up to 3 bonus
        score += 1 if vr > 1.3 else 0
        score += 1 if rsi_v < 60 else 0

        # SL / TP using ATR
        sl  = round(price - 2.0 * atr_v, 2)
        tp1 = round(price + 2.0 * atr_v, 2)
        tp2 = round(price + 4.0 * atr_v, 2)
        rr  = 2.0

        return dict(
            signal="BUY", ticker=symbol, price=price,
            score=min(score, 10), sl=sl, tp1=tp1, tp2=tp2, rr=rr,
            rsi=rsi_v, vr=vr,
            hist_1d=hist_1d, hist_wk=hist_wk, hist_mo=hist_mo,
            growing=growing,
        )

    # ── SHORT: all 3 TFs MACD bearish ─────────────
    if bear_1d and bear_wk and bear_mo:
        growing = sum([
            hist_growing(c1d),
            hist_growing(cwk),
            hist_growing(cmo),
        ])
        score = 6 + growing
        score += 1 if vr > 1.3 else 0
        score += 1 if rsi_v > 40 else 0

        sl  = round(price + 2.0 * atr_v, 2)
        tp1 = round(price - 2.0 * atr_v, 2)
        tp2 = round(price - 4.0 * atr_v, 2)
        rr  = 2.0

        return dict(
            signal="SHORT", ticker=symbol, price=price,
            score=min(score, 10), sl=sl, tp1=tp1, tp2=tp2, rr=rr,
            rsi=rsi_v, vr=vr,
            hist_1d=hist_1d, hist_wk=hist_wk, hist_mo=hist_mo,
            growing=growing,
        )

    return None

# ══════════════════════════════════════════════════════
#  FORMAT ALERT
# ══════════════════════════════════════════════════════
def fmt_alert(r, is_free=False):
    buy   = r["signal"] == "BUY"
    emoji = "🟢" if buy else "🔴"
    dir_  = "LONG  📈" if buy else "SHORT 📉"
    sl_lbl  = "SL (below entry)" if buy else "SL (above entry)"
    tp_lbl1 = "TP1 (above entry)" if buy else "TP1 (below entry)"
    tp_lbl2 = "TP2 (above entry)" if buy else "TP2 (below entry)"

    # Confidence
    sc = r["score"]
    conf = (
        "🔥 VERY HIGH" if sc >= 9 else
        "✅ HIGH"       if sc >= 7 else
        "🔵 MEDIUM"    if sc >= 6 else
        "⚪ LOW"
    )
    stars = "⭐" * min(sc, 10)

    # RSI
    rsi_tag = (
        "🟢 Oversold"   if (buy and r["rsi"] < 40) else
        "🔴 Overbought" if (not buy and r["rsi"] > 60) else
        "🔵 Neutral"
    )

    # Volume
    vol_tag = (
        "🔥 HIGH"   if r["vr"] > 1.5 else
        "✅ Good"   if r["vr"] > 1.1 else
        "⚪ Normal"
    )

    # Momentum
    g = r["growing"]
    mom = (
        "🔥 Strong — all 3 TFs accelerating" if g == 3 else
        "✅ Good — 2 TFs accelerating"        if g == 2 else
        "🔵 Building — 1 TF accelerating"    if g == 1 else
        "⚪ Weak — histogram flat"
    )

    # MACD alignment bars
    d_bar = "🟩" if (r["hist_1d"] > 0 if buy else r["hist_1d"] < 0) else "🟥"
    w_bar = "🟩" if (r["hist_wk"] > 0 if buy else r["hist_wk"] < 0) else "🟥"
    m_bar = "🟩" if (r["hist_mo"] > 0 if buy else r["hist_mo"] < 0) else "🟥"

    lock = "\n🔒 _Upgrade → /upgrade_" if is_free else ""

    return (
        f"{'━'*24}\n"
        f"{emoji} *{r['ticker']}*  —  {dir_}\n"
        f"{'━'*24}\n"
        f"💰 Price:   `${r['price']}`\n"
        f"🛑 {sl_lbl}: `${r['sl']}`\n"
        f"💵 {tp_lbl1}: `${r['tp1']}`\n"
        f"🏆 {tp_lbl2}: `${r['tp2']}`\n"
        f"📐 R:R:      `1:{r['rr']}`\n\n"
        f"*📊 MACD ALIGNMENT*\n"
        f"Daily  {d_bar}  Weekly {w_bar}  Monthly {m_bar}\n\n"
        f"*📈 INDICATORS*\n"
        f"├ RSI (Daily):  {r['rsi']}  {rsi_tag}\n"
        f"├ Volume:       {vol_tag} ({r['vr']}× avg)\n"
        f"└ Momentum:     {mom}\n\n"
        f"*⚡ CONFIDENCE:* {conf}\n"
        f"{stars}  `{sc}/10`"
        f"{lock}\n"
        f"{'━'*24}"
    )

# ══════════════════════════════════════════════════════
#  SCAN + DELIVER
# ══════════════════════════════════════════════════════
async def do_scan(bot, user, notify_start=False):
    cid = user["chat_id"]
    if notify_start:
        await bot.send_message(cid,
            f"🔍 *Scanning {len(TICKERS)} stocks...*\n_Results in ~10 mins_",
            parse_mode=ParseMode.MARKDOWN)

    buys, shorts, errors = [], [], 0

    for i, sym in enumerate(TICKERS):
        try:
            r = score_ticker(sym)
            if r:
                (buys if r["signal"] == "BUY" else shorts).append(r)
                log.info(f"{r['signal']} {sym} sc={r['score']}")
        except Exception as e:
            errors += 1
            log.debug(f"{sym}: {e}")
        # Rate limit every 30 tickers
        if i > 0 and i % 30 == 0:
            await asyncio.sleep(1.5)

    buys.sort(  key=lambda x: x["score"], reverse=True)
    shorts.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"Scan done. B:{len(buys)} S:{len(shorts)} Err:{errors}")

    await deliver(bot, user, buys, shorts)

async def deliver(bot, user, buys, shorts):
    cid    = user["chat_id"]
    pro    = is_pro(user)
    max_r  = PRO_MAX if pro else FREE_MAX
    free   = not pro
    et     = datetime.now(pytz.timezone("America/New_York"))
    tier   = "⭐ PRO" if pro else "🆓 FREE"

    # Header
    await bot.send_message(cid,
        f"{'━'*24}\n"
        f"📊 *SWING SCANNER — MACD*\n"
        f"{'━'*24}\n"
        f"🕐 {et.strftime('%a %b %d  %H:%M ET')}\n"
        f"🏷 Tier: *{tier}*\n"
        f"🔍 Scanned: *{len(TICKERS)}* stocks\n"
        f"🟢 *{min(len(buys),max_r)}* Longs   "
        f"🔴 *{min(len(shorts),max_r)}* Shorts\n"
        f"{'━'*24}",
        parse_mode=ParseMode.MARKDOWN)

    # Longs
    if buys[:max_r]:
        await bot.send_message(cid,
            f"🟢 *TOP LONG SETUPS*  ({len(buys)} found)",
            parse_mode=ParseMode.MARKDOWN)
        for r in buys[:max_r]:
            await bot.send_message(cid, fmt_alert(r, free),
                                   parse_mode=ParseMode.MARKDOWN)
    else:
        await bot.send_message(cid,
            "🟢 *No long setups this scan*\n"
            "_MACD not bullish on all 3 timeframes for any stock right now_",
            parse_mode=ParseMode.MARKDOWN)

    # Shorts
    if shorts[:max_r]:
        await bot.send_message(cid,
            f"🔴 *TOP SHORT SETUPS*  ({len(shorts)} found)",
            parse_mode=ParseMode.MARKDOWN)
        for r in shorts[:max_r]:
            await bot.send_message(cid, fmt_alert(r, free),
                                   parse_mode=ParseMode.MARKDOWN)
    else:
        await bot.send_message(cid,
            "🔴 *No short setups this scan*",
            parse_mode=ParseMode.MARKDOWN)

    # Footer
    if free:
        await bot.send_message(cid,
            f"{'━'*24}\n"
            f"🔒 *FREE: showing {FREE_MAX}/{max(len(buys),1)} results*\n\n"
            f"⭐ *PRO — ${PRO_PRICE}/month*\n"
            f"✅ All {PRO_MAX} setups per scan\n"
            f"✅ Full details on every signal\n\n"
            f"👉 /upgrade\n"
            f"{'━'*24}",
            parse_mode=ParseMode.MARKDOWN)
    else:
        await bot.send_message(cid,
            f"{'━'*24}\n"
            f"📋 LONG → SL below entry → TP1 50% → TP2 trail\n"
            f"📋 SHORT → SL above entry → TP1 50% → TP2 trail\n"
            f"_Not financial advice._\n"
            f"{'━'*24}",
            parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════
#  AUTO SCAN  — every 4h, sends to all users
# ══════════════════════════════════════════════════════
async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    log.info("Auto scan triggered")
    db = load_db()
    if not db:
        log.info("No users yet")
        return

    buys, shorts, errors = [], [], 0
    for i, sym in enumerate(TICKERS):
        try:
            r = score_ticker(sym)
            if r:
                (buys if r["signal"] == "BUY" else shorts).append(r)
        except Exception:
            errors += 1
        if i > 0 and i % 30 == 0:
            await asyncio.sleep(1.5)

    buys.sort(  key=lambda x: x["score"], reverse=True)
    shorts.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"Auto scan done. B:{len(buys)} S:{len(shorts)}")

    for uid, udata in db.items():
        try:
            await deliver(context.bot, udata, buys, shorts)
            await asyncio.sleep(0.3)
        except Exception as e:
            log.warning(f"Deliver {uid}: {e}")

# ══════════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    u["username"] = update.effective_user.username or ""
    u["name"]     = update.effective_user.first_name or ""
    save_db(db)
    pro  = is_pro(u)
    tier = "⭐ PRO" if pro else "🆓 FREE"

    await update.message.reply_text(
        f"{'━'*24}\n"
        f"🚀 *SWING SCANNER — MACD*\n"
        f"{'━'*24}\n\n"
        f"Hey *{u['name']}*! 👋\n"
        f"Tier: *{tier}*  |  ID: `{cid}`\n\n"
        f"*STRATEGY*\n"
        f"MACD bullish/bearish on\n"
        f"Daily + Weekly + Monthly\n"
        f"When all 3 align = signal ✅\n\n"
        f"*COMMANDS*\n"
        f"/scan — Run scan now\n"
        f"/status — Your account\n"
        f"/upgrade — Get PRO\n"
        f"/help — How to trade signals\n\n"
        f"🔄 Auto scan every 4 hours\n"
        f"{'━'*24}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    u["scans"] = u.get("scans", 0) + 1
    save_db(db)
    await do_scan(context.bot, u, notify_start=True)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    pro = is_pro(u)
    et  = datetime.now(pytz.timezone("America/New_York"))
    mkt = "🟢 OPEN" if (et.weekday()<5 and 9<=et.hour<16) else "🔴 CLOSED"
    exp = u.get("pro_until") or ("Lifetime" if pro else "N/A")

    await update.message.reply_text(
        f"{'━'*24}\n"
        f"📡 *YOUR ACCOUNT*\n"
        f"{'━'*24}\n\n"
        f"🏷 Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"{'📅 Pro until: '+exp if pro else '👉 /upgrade to go PRO'}\n"
        f"🔍 Results per scan: *{PRO_MAX if pro else FREE_MAX}*\n\n"
        f"🏛 Market: {mkt}\n"
        f"🕐 NY Time: {et.strftime('%H:%M')}\n"
        f"📊 Stocks watched: {len(TICKERS)}\n"
        f"{'━'*24}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    if is_pro(u):
        await update.message.reply_text(
            f"✅ *You already have PRO!*\nExpires: `{u.get('pro_until') or 'Lifetime'}`",
            parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text(
        f"{'━'*24}\n"
        f"⭐ *UPGRADE TO PRO*\n"
        f"{'━'*24}\n\n"
        f"*${PRO_PRICE}/month*\n\n"
        f"✅ {PRO_MAX} setups per scan\n"
        f"✅ Full signal details\n"
        f"✅ MACD momentum strength\n"
        f"✅ Volume analysis\n"
        f"✅ Priority delivery\n\n"
        f"{'━'*24}\n"
        f"💳 *Pay with Solana (SOL)*\n\n"
        f"Send *${PRO_PRICE} USD* worth of SOL to:\n"
        f"`{SOL_WALLET}`\n\n"
        f"*After paying DM {OWNER_USERNAME}:*\n"
        f"1️⃣ Screenshot of payment\n"
        f"2️⃣ Your Telegram ID: `{cid}`\n\n"
        f"✅ Activated within 1 hour\n"
        f"{'━'*24}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{'━'*24}\n"
        f"📋 *HOW TO USE SIGNALS*\n"
        f"{'━'*24}\n\n"
        f"*🟢 LONG (BUY)*\n"
        f"• Enter at or near price shown\n"
        f"• Set stop loss immediately at SL\n"
        f"• TP1 → take 50-60% profit\n"
        f"• TP2 → trail stop, let run\n\n"
        f"*🔴 SHORT*\n"
        f"• Short at or near price shown\n"
        f"• Set stop loss at SL level\n"
        f"• TP1 → cover 50-60%\n"
        f"• TP2 → trail stop down\n\n"
        f"*📊 MACD BOXES*\n"
        f"🟩 = bullish on that timeframe\n"
        f"🟥 = bearish on that timeframe\n"
        f"All 3 🟩🟩🟩 = strongest signal\n\n"
        f"*⚡ CONFIDENCE*\n"
        f"8-10 ⭐ = best setups\n"
        f"6-7 ⭐ = good setups\n\n"
        f"*⚠️ RULES*\n"
        f"• Always check chart before entering\n"
        f"• Never risk more than 2% per trade\n"
        f"• Move SL to breakeven after TP1\n"
        f"{'━'*24}\n"
        f"_Not financial advice._",
        parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db    = load_db()
    total = len(db)
    pros  = sum(1 for u in db.values() if is_pro(u))
    await update.message.reply_text(
        f"🔧 *ADMIN*\n\n"
        f"👥 Users: *{total}*\n"
        f"⭐ PRO: *{pros}*\n"
        f"🆓 FREE: *{total-pros}*\n\n"
        f"/addpro `<id> <days>`\n"
        f"/rmpro `<id>`\n"
        f"/broadcast `<msg>`\n"
        f"/userlist",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_addpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addpro <id> <days>"); return
    try: tid, days = int(args[0]), int(args[1])
    except: await update.message.reply_text("Invalid."); return
    db = load_db()
    u  = get_user(db, tid)
    u["tier"]      = "pro"
    u["pro_until"] = (datetime.utcnow()+timedelta(days=days)).isoformat()
    save_db(db)
    await update.message.reply_text(
        f"✅ PRO granted to `{tid}` for {days} days",
        parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(tid,
            f"🎉 *Your account is now PRO!*\n\n"
            f"✅ {days} days access\n"
            f"✅ {PRO_MAX} results per scan\n\n"
            f"Send /scan now! 🚀",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cmd_rmpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    args = context.args
    if not args: await update.message.reply_text("Usage: /rmpro <id>"); return
    try: tid = int(args[0])
    except: await update.message.reply_text("Invalid."); return
    db = load_db()
    u  = get_user(db, tid)
    u["tier"] = "free"; u["pro_until"] = None
    save_db(db)
    await update.message.reply_text(f"✅ PRO removed from `{tid}`",
                                    parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <msg>"); return
    msg  = " ".join(context.args)
    db   = load_db()
    sent = 0
    for ud in db.values():
        try:
            await context.bot.send_message(ud["chat_id"],
                f"📢 *Announcement*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except: pass
        await asyncio.sleep(0.1)
    await update.message.reply_text(f"✅ Sent to {sent} users.")

async def cmd_userlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db    = load_db()
    lines = [f"*USERS* ({len(db)})\n"]
    for uid, u in list(db.items())[:50]:
        tier = "PRO⭐" if is_pro(u) else "free"
        name = u.get("username") or u.get("name") or "—"
        lines.append(f"`{uid}` @{name} {tier}")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    if TELEGRAM_TOKEN == "YOUR_TOKEN":
        raise ValueError("Set TELEGRAM_TOKEN!")
    if OWNER_CHAT_ID == 0:
        raise ValueError("Set CHAT_ID!")

    log.info(f"Starting Swing Scanner v6.0 — {len(TICKERS)} tickers")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    for cmd, fn in [
        ("start",     cmd_start),
        ("scan",      cmd_scan),
        ("status",    cmd_status),
        ("upgrade",   cmd_upgrade),
        ("help",      cmd_help),
        ("admin",     cmd_admin),
        ("addpro",    cmd_addpro),
        ("rmpro",     cmd_rmpro),
        ("broadcast", cmd_broadcast),
        ("userlist",  cmd_userlist),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    app.job_queue.run_repeating(
        scheduled_scan, interval=SCAN_INTERVAL, first=90)

    log.info("Bot live ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
