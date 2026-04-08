"""
SWING SCANNER BOT v7.0 — MACD ONLY
Scans 1000+ stocks, Daily + Weekly + Monthly MACD
"""

import os, asyncio, logging, json, time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# ══════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN")
OWNER_CHAT_ID  = int(os.environ.get("CHAT_ID", "0"))
SOL_WALLET     = os.environ.get("SOL_WALLET",  "YOUR_SOLANA_WALLET")
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "@YourUsername")
PRO_PRICE      = os.environ.get("PRO_PRICE", "29")

SCAN_INTERVAL  = 4 * 60 * 60
FREE_MAX       = 3
PRO_MAX        = 25
DATA_FILE      = Path("/tmp/users.json")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  USER DATABASE
# ══════════════════════════════════════════════
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
        db[key] = {"chat_id": cid, "tier": "free",
                   "joined": datetime.utcnow().isoformat(),
                   "pro_until": None, "username": "", "name": ""}
        save_db(db)
    return db[key]

def is_pro(u):
    if u["tier"] != "pro": return False
    if u["pro_until"] is None: return True
    return datetime.utcnow() < datetime.fromisoformat(u["pro_until"])

def is_owner(cid): return cid == OWNER_CHAT_ID

# ══════════════════════════════════════════════
#  1000+ TICKERS
# ══════════════════════════════════════════════
TICKERS = sorted(set([
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","LLY",
    "JPM","V","MA","UNH","XOM","JNJ","WMT","PG","HD","MRK","CVX","ABBV",
    "BAC","COST","KO","PEP","ADBE","CSCO","CRM","TMO","ACN","MCD","ABT",
    "DHR","LIN","TXN","NFLX","CMCSA","NKE","AMD","PM","UPS","MS","BMY",
    "RTX","INTU","SPGI","HON","AMGN","SBUX","LOW","GE","CAT","GS","BLK",
    "AMAT","ELV","ISRG","GILD","MDT","ADP","LRCX","SYK","REGN","VRTX",
    "ADI","PANW","KLAC","SNPS","CDNS","MCHP","NXPI","FTNT","CRWD","NOW",
    "MMM","ABT","AFL","AES","AIG","AMT","AMP","AME","APH","ANSS","AON",
    "APA","APTV","ANET","AJG","AIZ","T","ADSK","ADP","AZO","AVB","AVY",
    "AXON","BKR","BALL","BK","BBWI","BAX","BDX","BRK-B","BBY","BIIB",
    "BX","BA","BSX","BR","BRO","BLDR","BG","CZR","CPT","CPB","COF","CAH",
    "KMX","CCL","CARR","CAT","CBOE","CBRE","CDW","CE","COR","CNC","CF",
    "CRL","SCHW","CHTR","CMG","CB","CHD","CI","CINF","CTAS","C","CFG",
    "CLX","CME","CMS","CTSH","CL","CAG","COP","ED","STZ","CEG","COO",
    "CPRT","GLW","CTVA","CSGP","CTRA","CCI","CSX","CMI","CVS","DHI","DRI",
    "DVA","DE","DAL","DVN","DXCM","DLR","DFS","DG","DLTR","D","DPZ","DOW",
    "DTE","DUK","DD","ETN","EBAY","ECL","EIX","EW","EA","EMR","ENPH","EOG",
    "EQT","EFX","EQIX","EQR","ESS","EL","ETSY","EXC","EXPE","XOM","FDS",
    "FICO","FAST","FDX","FIS","FITB","FSLR","FI","FLT","F","FTNT","FCX",
    "GD","GIS","GM","GPC","GPN","GL","GDDY","HAL","HIG","HCA","HSY","HES",
    "HPE","HLT","HD","HRL","HPQ","HUBB","HUM","IBM","IDXX","ITW","INTC",
    "ICE","IRM","JCI","JNPR","K","KDP","KEY","KMB","KMI","KHC","KR","LHX",
    "LH","LW","LVS","LEN","LMT","L","LULU","MTB","MPC","MAR","MMC","MAS",
    "MTCH","MKC","MCK","MET","MGM","MU","MAA","MRNA","MCO","MSI","MSCI",
    "NDAQ","NEE","NSC","NOC","NCLH","NVDA","NXPI","ORLY","OXY","ODFL","ON",
    "OKE","ORCL","PCAR","PKG","PH","PAYX","PYPL","PEP","PFE","PM","PSX",
    "PNC","PPG","PGR","PLD","PRU","PSA","PWR","QCOM","RTX","O","REGN","RSG",
    "RMD","ROK","ROP","ROST","SBAC","SLB","SRE","SHW","SPG","SBUX","STT",
    "STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TGT","TXN",
    "TMO","TJX","TSCO","TT","TDG","TRV","TFC","TSN","USB","UBER","UNP",
    "UAL","UPS","URI","UNH","VLO","VZ","VRTX","VICI","VMC","WBA","WMT",
    "DIS","WM","WAT","WFC","WELL","WDC","WMB","WYNN","XEL","YUM","ZBH",
    "ZTS","GPC","GDDY","GL","GNRC","GRMN","IT","GEHC","AXON","BKR","BALL",
    "BBWI","BAX","BG","CAH","CCL","CARR","CBOE","CBRE","CDW","CE","COR",
    "CNC","CF","CRL","CHD","CINF","CFG","CME","CAG","ED","CEG","COO","CPRT",
    "GLW","CTVA","CSGP","CTRA","CCI","DHR","DVA","DAY","XRAY","FANG","DFS",
    "DOV","EMN","EG","EVRG","ES","EXPD","EXR","FFIV","FRT","FMC","FTV",
    "FOXA","FOX","BEN","HAS","DOC","HEI","HOLX","HWM","HBAN","HII","IEX",
    "INCY","IR","PODD","IVZ","INVH","IQV","JBHT","JBL","JKHY","KVUE","KIM",
    "LDOS","LYV","LKQ","LYB","MRO","MKTX","MLM","MOH","TAP","MDLZ","MPWR",
    "MNST","MOS","NWS","NWSA","NI","NDSN","NTRS","NRG","NUE","NVR","PKG",
    "PNR","PCG","PNW","POOL","PPL","PFG","PEG","PTC","PHM","QRVO","RL",
    "RJF","RF","RVTY","ROL","RCL","SNA","SO","LUV","SWK","STX","SJM",
    "SOLV","SWKS","TPR","TRGP","TEL","TDY","TFX","TER","TXT","TYL","UDR",
    "ULTA","UHS","VTRS","VST","WRB","GWW","WAB","WBD","WST","WRK","WHR",
    "WTW","XYL","ASML","BIDU","BKNG","MELI","MRVL","NFLX","NTES","OKTA",
    "PDD","TEAM","WDAY","ZM","ZS","JD","ILMN","SIRI","BMRN","INCY","SPLK",
    "TCOM","VRSN","VRSK","FISV","ATVI","SHOP","SE","GRAB","NU","NVO","BNTX",
    "SQ","COIN","HOOD","SOFI","PLTR","CRWD","DDOG","NET","SNOW","MDB",
    "HUBS","TWLO","DOCN","GTLB","CFLT","BRZE","BILL","APPN","LYFT","DASH",
    "SNAP","PINS","SPOT","RBLX","U","RIVN","NIO","XPEV","LI","CHPT","BLNK",
    "EVGO","PLUG","BABA","TDOC","DOCS","IBKR","AFRM","UPST","ACHR","JOBY",
    "RKLB","LUNR","ASTS","MARA","RIOT","CLSK","HUT","CORZ","DELL","PSTG",
    "AI","BBAI","SOUN","IONQ","RGTI","MSTR","CELH","RXRX","TSM","WOLF",
    "AEHR","SMCI","HIMS","TDOC","DOCU","TWLO","ZI","PCTY","COUP","APPF",
    "NCNO","JAMF","WK","PCOR","INST","BRZE","TASK","UPWK","FIVR","RELY",
    "OPEN","RDFN","Z","COMP","OPAD","IBP","BECN","TREX","BLDR","MHO","MTH",
    "TPH","TMHC","KBH","MDC","LGIH","GRBK","CCS","CVCO","UCP","NWHM",
    "GS","JPM","BAC","C","WFC","MS","BLK","SCHW","IBKR","AXP","FIS","FI",
    "GPN","FISV","COF","DFS","SYF","AIG","MET","PRU","AFL","ALL","TRV","CB",
    "XOM","CVX","COP","SLB","HAL","OXY","MPC","VLO","PSX","DVN","EOG",
    "HES","MRO","APA","EQT","RRC","SM","NOG","CTRA","PXD","FANG","MTDR",
    "LLY","NVO","MRNA","BNTX","ABBV","JNJ","PFE","AMGN","GILD","REGN",
    "VRTX","BIIB","ILMN","HIMS","ALNY","BMRN","INCY","SRPT","NVAX","EXAS",
    "ACAD","FATE","BEAM","EDIT","CRSP","NTLA","ARWR","PCVX","ROIV","INSM",
    "SPY","QQQ","IWM","DIA","SMH","SOXX","XLK","XLF","XLE","XLV","XLI",
    "XLB","XLU","XLP","XLY","ARKK","ARKG","ARKW","ARKF","GLD","SLV","GDX",
    "GDXJ","TLT","IEF","SHY","SOXL","TQQQ","UPRO","LABU","BOTZ","AIQ",
    "NKE","LULU","UAA","ONON","DECK","CROX","SKX","PVH","RL","TPR","VFC",
    "MCD","SBUX","YUM","CMG","DPZ","QSR","WEN","TXRH","EAT","DRI","JACK",
    "DIS","NFLX","PARA","WBD","FOXA","FOX","LYV","SPOT","RBLX","U","EA",
    "TTWO","ATVI","NTDOY","MGAM","DKNG","RSI","PENN","CZAR","MGM","WYNN",
    "BA","LMT","RTX","NOC","GD","HII","TDG","HEI","TXT","KTOS","AXON",
    "CAT","DE","EMR","ETN","HON","ROK","ITW","PH","GE","MMM","DOV","AME",
    "FCX","NEM","GOLD","AEM","WPM","PAAS","HL","AG","CDE","EXK","SILV",
    "ALB","SQM","LAC","PLL","LTHM","LICY","ALTM","NOVS","MP","MTRN","REE",
    "UUUU","DNN","UEC","CCJ","NXE","URG","LTBR","BWXT","BWX","GEV","OKLO",
    "F","GM","STLA","RACE","MBLY","APTV","LEA","BWA","MGA","VC","ADNT",
    "AMT","CCI","SBAC","EQIX","DLR","IRM","CONE","LAMR","OUT","UNIT",
    "PLD","PSA","EXR","AVB","EQR","ESS","MAA","UDR","CPT","AIV","NNN",
    "BX","KKR","APO","ARES","CG","BAM","OWL","STEP","HLNE","GCMG","ARCC",
    "MAIN","GAIN","PSEC","GSBD","BXSL","FSK","OBDC","TPVG","PFLT","SLRC",
    "AMZN","WMT","TGT","COST","HD","LOW","ETSY","W","OSTK","CHWY","CHEWY",
    "NFLX","DIS","PARA","WBD","T","VZ","CMCSA","CHTR","DISH","SIRI","LUMN",
    "TSM","ASML","AMAT","LRCX","KLAC","NVDA","AMD","INTC","QCOM","AVGO",
    "TXN","MCHP","ADI","NXPI","SWKS","QRVO","MRVL","SLAB","MPWR","WOLF",
    "ONTO","MKSI","KLIC","ICHR","AMKR","COHU","AEHR","ACMR","CAMT","FORM",
    "PLXS","SANM","FLEX","JBL","CLS","BHE","SCSC","ARW","AVT","WCC","NSIT",
])) 

log.info(f"Loaded {len(TICKERS)} tickers")

# ══════════════════════════════════════════════
#  MACD CALCULATION
# ══════════════════════════════════════════════
def calc_macd(close):
    e12  = close.ewm(span=12, adjust=False).mean()
    e26  = close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig  = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def is_macd_bull(close):
    """
    BULLISH = MACD line is above signal line.
    Simple. No histogram requirement. Just the cross.
    """
    if len(close) < 30: return False
    m, sig, _ = calc_macd(close)
    return m.iloc[-1] > sig.iloc[-1]

def is_macd_bear(close):
    """BEARISH = MACD line is below signal line."""
    if len(close) < 30: return False
    m, sig, _ = calc_macd(close)
    return m.iloc[-1] < sig.iloc[-1]

def hist_strength(close):
    """How strong is the histogram (momentum)."""
    if len(close) < 30: return 0
    _, _, hist = calc_macd(close)
    return round(hist.iloc[-1], 4)

# ══════════════════════════════════════════════
#  FETCH DATA — simple and fast
# ══════════════════════════════════════════════
def fetch_ticker(symbol):
    try:
        t   = yf.Ticker(symbol)
        d1  = t.history(period="1y",   interval="1d",  auto_adjust=True)
        wk  = t.history(period="5y",   interval="1wk", auto_adjust=True)
        mo  = t.history(period="10y",  interval="1mo", auto_adjust=True)
        if len(d1) < 30 or len(wk) < 30 or len(mo) < 14:
            return None
        return {"1d": d1, "1wk": wk, "1mo": mo}
    except Exception as e:
        log.debug(f"{symbol}: {e}")
        return None

# ══════════════════════════════════════════════
#  SCAN ONE TICKER
# ══════════════════════════════════════════════
def check_ticker(symbol):
    data = fetch_ticker(symbol)
    if not data: return None

    c1d = data["1d"]["Close"].dropna()
    cwk = data["1wk"]["Close"].dropna()
    cmo = data["1mo"]["Close"].dropna()

    # ── LONG: MACD bull on ALL 3 timeframes ──
    if is_macd_bull(c1d) and is_macd_bull(cwk) and is_macd_bull(cmo):
        price    = round(c1d.iloc[-1], 2)
        h1d      = hist_strength(c1d)
        hwk      = hist_strength(cwk)
        hmo      = hist_strength(cmo)
        # Score: how positive the histograms are
        score    = sum([h1d > 0, hwk > 0, hmo > 0,
                        h1d > h1d*0, hwk > 0, hmo > 0])
        # ATR-based SL/TP
        atr      = data["1d"]["High"].iloc[-14:].max() - data["1d"]["Low"].iloc[-14:].min()
        atr      = atr / 14
        sl       = round(price - 1.5 * atr, 2)
        tp1      = round(price + 1.5 * atr, 2)
        tp2      = round(price + 3.0 * atr, 2)
        return dict(signal="BUY", ticker=symbol, price=price,
                    sl=sl, tp1=tp1, tp2=tp2, rr=1.5,
                    h1d=h1d, hwk=hwk, hmo=hmo)

    # ── SHORT: MACD bear on ALL 3 timeframes ──
    if is_macd_bear(c1d) and is_macd_bear(cwk) and is_macd_bear(cmo):
        price    = round(c1d.iloc[-1], 2)
        h1d      = hist_strength(c1d)
        hwk      = hist_strength(cwk)
        hmo      = hist_strength(cmo)
        atr      = data["1d"]["High"].iloc[-14:].max() - data["1d"]["Low"].iloc[-14:].min()
        atr      = atr / 14
        sl       = round(price + 1.5 * atr, 2)
        tp1      = round(price - 1.5 * atr, 2)
        tp2      = round(price - 3.0 * atr, 2)
        return dict(signal="SHORT", ticker=symbol, price=price,
                    sl=sl, tp1=tp1, tp2=tp2, rr=1.5,
                    h1d=h1d, hwk=hwk, hmo=hmo)

    return None

# ══════════════════════════════════════════════
#  FORMAT ALERT
# ══════════════════════════════════════════════
def fmt(r, is_free=False):
    buy   = r["signal"] == "BUY"
    emoji = "🟢" if buy else "🔴"
    dir_  = "LONG 📈" if buy else "SHORT 📉"

    # MACD alignment visual
    d = "🟩" if (r["h1d"] > 0) else "🟥"
    w = "🟩" if (r["hwk"] > 0) else "🟥"
    m = "🟩" if (r["hmo"] > 0) else "🟥"

    lock = "\n🔒 _Upgrade for more signals → /upgrade_" if is_free else ""

    return (
        f"{'━'*22}\n"
        f"{emoji} *{r['ticker']}*  —  {dir_}\n"
        f"{'━'*22}\n"
        f"💰 Price:  `${r['price']}`\n"
        f"🛑 Stop:   `${r['sl']}`\n"
        f"💵 TP1:    `${r['tp1']}`\n"
        f"🏆 TP2:    `${r['tp2']}`\n"
        f"📐 R:R:    `1:{r['rr']}`\n\n"
        f"*MACD ALIGNMENT*\n"
        f"Daily {d}  Weekly {w}  Monthly {m}\n"
        f"{'━'*22}"
        f"{lock}"
    )

# ══════════════════════════════════════════════
#  RUN SCAN
# ══════════════════════════════════════════════
async def run_scan(bot, user):
    cid    = user["chat_id"]
    pro    = is_pro(user)
    max_r  = PRO_MAX if pro else FREE_MAX
    ticks  = list(TICKERS)

    await bot.send_message(cid,
        f"🔍 *Scanning {len(ticks)} stocks...*\n"
        f"_MACD Daily + Weekly + Monthly_\n"
        f"_Results coming in ~10 mins..._",
        parse_mode=ParseMode.MARKDOWN)

    buys, shorts = [], []

    for i, sym in enumerate(ticks):
        try:
            r = check_ticker(sym)
            if r:
                if r["signal"] == "BUY":
                    buys.append(r)
                else:
                    shorts.append(r)
                log.info(f"✅ {r['signal']} {sym}")
        except Exception as e:
            log.debug(f"ERR {sym}: {e}")

        # Rate limit
        if i > 0 and i % 25 == 0:
            await asyncio.sleep(1)
            if i % 100 == 0:
                log.info(f"Progress {i}/{len(ticks)} | B:{len(buys)} S:{len(shorts)}")

    log.info(f"SCAN DONE — Buys:{len(buys)} Shorts:{len(shorts)}")
    await send_results(bot, user, buys, shorts, len(ticks))

async def send_results(bot, user, buys, shorts, total):
    cid   = user["chat_id"]
    pro   = is_pro(user)
    max_r = PRO_MAX if pro else FREE_MAX
    free  = not pro
    et    = datetime.now(pytz.timezone("America/New_York"))

    # Header
    await bot.send_message(cid,
        f"{'━'*22}\n"
        f"📊 *MACD SCANNER REPORT*\n"
        f"{'━'*22}\n"
        f"🕐 {et.strftime('%a %d %b  %H:%M ET')}\n"
        f"🔍 Scanned: *{total}* stocks\n"
        f"🟢 *{len(buys)}* Buys   🔴 *{len(shorts)}* Shorts\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN)

    # BUY signals
    if buys:
        await bot.send_message(cid,
            f"🟢 *BUY SIGNALS — {len(buys)} found*\n"
            f"_MACD bullish Daily + Weekly + Monthly_",
            parse_mode=ParseMode.MARKDOWN)
        for r in buys[:max_r]:
            try:
                await bot.send_message(cid, fmt(r, free),
                                       parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.2)
            except Exception as e:
                log.warning(f"Send {r['ticker']}: {e}")
        if free and len(buys) > FREE_MAX:
            await bot.send_message(cid,
                f"🔒 *+{len(buys)-FREE_MAX} more buy signals hidden*\n"
                f"Upgrade to PRO → /upgrade",
                parse_mode=ParseMode.MARKDOWN)
    else:
        await bot.send_message(cid,
            "🟢 *No buy signals this scan*\n"
            "_MACD not bullish on all 3 TFs for any stock_",
            parse_mode=ParseMode.MARKDOWN)

    # SHORT signals
    if shorts:
        await bot.send_message(cid,
            f"🔴 *SHORT SIGNALS — {len(shorts)} found*",
            parse_mode=ParseMode.MARKDOWN)
        for r in shorts[:max_r]:
            try:
                await bot.send_message(cid, fmt(r, free),
                                       parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.2)
            except Exception as e:
                log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,
            "🔴 *No short signals this scan*",
            parse_mode=ParseMode.MARKDOWN)

    # Footer
    if free:
        await bot.send_message(cid,
            f"{'━'*22}\n"
            f"🔒 *FREE: {FREE_MAX} signals shown*\n\n"
            f"⭐ *PRO — ${PRO_PRICE}/month*\n"
            f"✅ All {PRO_MAX} signals\n"
            f"👉 /upgrade\n"
            f"{'━'*22}",
            parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    u["username"] = update.effective_user.username or ""
    u["name"]     = update.effective_user.first_name or ""
    save_db(db)
    pro = is_pro(u)

    await update.message.reply_text(
        f"{'━'*22}\n"
        f"🚀 *MACD SWING SCANNER*\n"
        f"{'━'*22}\n\n"
        f"Hey *{u['name']}*! 👋\n"
        f"Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"ID: `{cid}`\n\n"
        f"*STRATEGY*\n"
        f"Scans {len(TICKERS)}+ stocks\n"
        f"MACD bullish on Daily + Weekly + Monthly\n"
        f"When all 3 align → signal sent ✅\n\n"
        f"*COMMANDS*\n"
        f"/scan — Run scan now (~10 mins)\n"
        f"/status — Your account info\n"
        f"/upgrade — Get PRO access\n"
        f"/help — How to trade the signals\n\n"
        f"🔄 Auto scan every 4 hours\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    await run_scan(context.bot, u)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    pro = is_pro(u)
    et  = datetime.now(pytz.timezone("America/New_York"))
    mkt = "🟢 OPEN" if (et.weekday() < 5 and 9 <= et.hour < 16) else "🔴 CLOSED"

    await update.message.reply_text(
        f"{'━'*22}\n"
        f"📡 *STATUS*\n"
        f"{'━'*22}\n\n"
        f"🏷 Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"{'📅 Pro until: '+u['pro_until'] if pro and u['pro_until'] else ''}\n"
        f"📊 Signals per scan: *{PRO_MAX if pro else FREE_MAX}*\n"
        f"🔍 Stocks watched: *{len(TICKERS)}*\n"
        f"🏛 Market: {mkt}\n"
        f"🕐 NY Time: {et.strftime('%H:%M')}\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)

    if is_pro(u):
        await update.message.reply_text(
            f"✅ *You already have PRO!*",
            parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text(
        f"{'━'*22}\n"
        f"⭐ *UPGRADE TO PRO*\n"
        f"{'━'*22}\n\n"
        f"*${PRO_PRICE}/month*\n\n"
        f"✅ {PRO_MAX} signals per scan\n"
        f"✅ Full buy & short details\n"
        f"✅ Entry, SL, TP1, TP2\n"
        f"✅ MACD alignment visual\n\n"
        f"{'━'*22}\n"
        f"💳 *Pay with Solana (SOL)*\n\n"
        f"Send *${PRO_PRICE} USD* in SOL to:\n"
        f"`{SOL_WALLET}`\n\n"
        f"*After payment, DM {OWNER_USERNAME}:*\n"
        f"1️⃣ Payment screenshot\n"
        f"2️⃣ Your Telegram ID: `{cid}`\n\n"
        f"✅ Activated within 1 hour\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{'━'*22}\n"
        f"📋 *HOW TO USE SIGNALS*\n"
        f"{'━'*22}\n\n"
        f"*🟢 BUY (LONG)*\n"
        f"• Enter at or near the price shown\n"
        f"• Set stop loss at SL immediately\n"
        f"• Take 50% profit at TP1\n"
        f"• Let rest run to TP2\n\n"
        f"*🔴 SHORT*\n"
        f"• Short at or near price shown\n"
        f"• Stop loss at SL\n"
        f"• Cover 50% at TP1\n"
        f"• Trail to TP2\n\n"
        f"*📊 MACD BOXES*\n"
        f"🟩 = MACD bullish that timeframe\n"
        f"🟥 = MACD bearish that timeframe\n"
        f"All 3 same = strongest signal\n\n"
        f"*⚠️ RULES*\n"
        f"• Check chart before entering\n"
        f"• Never risk more than 2% capital\n"
        f"• Move SL to breakeven after TP1\n"
        f"{'━'*22}\n"
        f"_Not financial advice._",
        parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db = load_db()
    pros = sum(1 for u in db.values() if is_pro(u))
    await update.message.reply_text(
        f"🔧 *ADMIN*\n\n"
        f"👥 Users: {len(db)}\n"
        f"⭐ PRO: {pros}  🆓 FREE: {len(db)-pros}\n\n"
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
    except:
        await update.message.reply_text("Invalid."); return
    db = load_db()
    u  = get_user(db, tid)
    u["tier"]      = "pro"
    u["pro_until"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
    save_db(db)
    await update.message.reply_text(
        f"✅ PRO granted to `{tid}` for {days} days",
        parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(tid,
            f"🎉 *Your account is now PRO!*\n\n"
            f"✅ {days} days  ✅ {PRO_MAX} signals per scan\n\n"
            f"Send /scan now! 🚀",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cmd_rmpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    if not context.args:
        await update.message.reply_text("Usage: /rmpro <id>"); return
    try: tid = int(context.args[0])
    except:
        await update.message.reply_text("Invalid."); return
    db = load_db()
    u  = get_user(db, tid)
    u["tier"] = "free"; u["pro_until"] = None
    save_db(db)
    await update.message.reply_text(
        f"✅ PRO removed from `{tid}`", parse_mode=ParseMode.MARKDOWN)

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
                f"📢 *Announcement*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except: pass
        await asyncio.sleep(0.1)
    await update.message.reply_text(f"✅ Sent to {sent} users.")

async def cmd_userlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db    = load_db()
    lines = [f"*USERS* ({len(db)})\n"]
    for uid, u in list(db.items())[:50]:
        t = "PRO⭐" if is_pro(u) else "free"
        n = u.get("username") or u.get("name") or "—"
        lines.append(f"`{uid}` @{n} {t}")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  AUTO SCAN EVERY 4H
# ══════════════════════════════════════════════
async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    log.info("Auto scan starting...")
    db = load_db()
    if not db: return

    ticks = list(TICKERS)
    buys, shorts = [], []

    for i, sym in enumerate(ticks):
        try:
            r = check_ticker(sym)
            if r:
                (buys if r["signal"] == "BUY" else shorts).append(r)
        except: pass
        if i > 0 and i % 25 == 0:
            await asyncio.sleep(1)

    log.info(f"Auto scan done: B={len(buys)} S={len(shorts)}")
    for uid, udata in db.items():
        try:
            await send_results(context.bot, udata, buys, shorts, len(ticks))
            await asyncio.sleep(0.3)
        except Exception as e:
            log.warning(f"Deliver {uid}: {e}")

# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════
def main():
    if TELEGRAM_TOKEN == "YOUR_TOKEN":
        raise ValueError("Set TELEGRAM_TOKEN!")
    if OWNER_CHAT_ID == 0:
        raise ValueError("Set CHAT_ID!")

    log.info(f"Starting MACD Scanner v7.0 — {len(TICKERS)} tickers")
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

    app.job_queue.run_repeating(auto_scan, interval=SCAN_INTERVAL, first=90)

    log.info("Bot live ✅ v7.0")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
