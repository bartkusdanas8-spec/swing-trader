"""
╔══════════════════════════════════════════════════════════════════════╗
║            ULTIMATE SWING SCANNER BOT  v5.0                        ║
║   MACD(D/W/M) + 4H EMA + Volume + RS + Divergence                 ║
║   Multi-user | Free vs Pro | Crypto payments | Best alerts         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, asyncio, logging, json, time, random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import yfinance as yf
import pytz

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)
from telegram.constants import ParseMode

# ══════════════════════════════════════════════
#  CONFIG  — set via Railway environment vars
# ══════════════════════════════════════════════
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN")
OWNER_CHAT_ID     = int(os.environ.get("CHAT_ID", "0"))

# ── YOUR PAYMENT DETAILS ──────────────────────
OWNER_USERNAME    = os.environ.get("OWNER_USERNAME", "@YourUsername")
USDT_TRC20        = os.environ.get("USDT_WALLET",   "YOUR_USDT_TRC20_WALLET")
BTC_WALLET        = os.environ.get("BTC_WALLET",    "YOUR_BTC_WALLET")
ETH_WALLET        = os.environ.get("ETH_WALLET",    "YOUR_ETH_WALLET")
SOL_WALLET        = os.environ.get("SOL_WALLET",    "YOUR_SOL_WALLET")
PRO_PRICE         = os.environ.get("PRO_PRICE",     "29")   # USD/month

SCAN_INTERVAL     = 4 * 60 * 60   # 4 hours
FREE_MAX          = 3              # max results free tier
PRO_MAX           = 25             # max results pro tier
DATA_FILE         = Path("/tmp/users.json")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  USER DATABASE
# ══════════════════════════════════════════════
def load_db() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {}

def save_db(db: dict):
    DATA_FILE.write_text(json.dumps(db, indent=2))

def get_user(db: dict, cid: int) -> dict:
    key = str(cid)
    if key not in db:
        db[key] = {
            "chat_id":   cid,
            "tier":      "free",
            "joined":    datetime.utcnow().isoformat(),
            "pro_until": None,
            "mode":      "full",
            "username":  "",
            "name":      "",
            "scans":     0,
        }
        save_db(db)
    return db[key]

def is_pro(u: dict) -> bool:
    if u["tier"] != "pro":
        return False
    if u["pro_until"] is None:
        return True
    return datetime.utcnow() < datetime.fromisoformat(u["pro_until"])

def is_owner(cid: int) -> bool:
    return cid == OWNER_CHAT_ID

# ══════════════════════════════════════════════
#  TICKER UNIVERSE  (~900 liquid stocks)
# ══════════════════════════════════════════════
TICKERS = sorted(set([
    # S&P 500 core
    "MMM","ABT","ABBV","ACN","ADBE","AMD","AFL","GOOGL","GOOG","MO","AMZN",
    "AEP","AXP","AIG","AMT","AMP","AMGN","APH","ADI","AAPL","AMAT","ANET",
    "T","ADSK","ADP","AZO","BAC","BK","BDX","BRK-B","BIIB","BLK","BX","BA",
    "BSX","BMY","AVGO","CDNS","COF","KMX","CCL","CAT","SCHW","CHTR","CVX",
    "CMG","CB","CI","CTAS","CSCO","C","CLX","CME","KO","CTSH","CL","CMCSA",
    "COP","STZ","COST","CCI","CSX","CMI","CVS","DHI","DHR","DRI","DE","DAL",
    "DVN","DXCM","DLR","DFS","DG","DLTR","D","DPZ","DOW","DTE","DUK","DD",
    "ETN","EBAY","ECL","EIX","EW","EA","ELV","LLY","EMR","ENPH","EOG","EQIX",
    "EQR","ESS","EL","ETSY","EXC","EXPE","XOM","FDS","FICO","FAST","FDX",
    "FIS","FITB","FSLR","FI","FLT","F","FTNT","FCX","GE","GD","GIS","GM",
    "GPC","GILD","GS","HAL","HIG","HCA","HSIC","HSY","HES","HPE","HLT","HD",
    "HON","HRL","HPQ","HUBB","HUM","IBM","IDXX","ITW","INTC","ICE","INTU",
    "ISRG","IRM","JNJ","JCI","JPM","K","KDP","KEY","KMB","KMI","KLAC","KHC",
    "KR","LHX","LRCX","LVS","LEN","LIN","LMT","L","LOW","LULU","MTB","MPC",
    "MAR","MMC","MA","MKC","MCD","MCK","MDT","MRK","META","MET","MGM","MCHP",
    "MU","MSFT","MRNA","MCO","MS","MSI","MSCI","NDAQ","NEE","NKE","NSC","NOC",
    "NCLH","NVDA","NXPI","ORLY","OXY","ODFL","ON","OKE","ORCL","PCAR","PANW",
    "PH","PAYX","PYPL","PEP","PFE","PM","PSX","PNC","COST","PPG","PG","PGR",
    "PLD","PRU","PSA","PWR","QCOM","RTX","O","REGN","RSG","RMD","ROK","ROP",
    "ROST","SPGI","CRM","SBAC","SLB","SRE","NOW","SHW","SPG","SBUX","STT",
    "STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TGT","TSLA",
    "TXN","TMO","TJX","TSCO","TT","TDG","TRV","TFC","TSN","USB","UBER","UNP",
    "UAL","UPS","URI","UNH","VLO","VTR","VZ","VRTX","VICI","V","VMC","WBA",
    "WMT","DIS","WM","WAT","WFC","WELL","WDC","WY","WMB","WYNN","XEL","YUM",
    "ZBRA","ZBH","ZTS","GPC","GDDY","GL","GNRC","GRMN","IT","GEV","GEHC",
    "AXON","BALL","BKR","BBWI","BAX","BG","CAH","CCL","CARR","CBOE","CBRE",
    "CDW","CE","COR","CNC","CF","CRL","CHD","CINF","CFG","CME","CAG","ED",
    "CEG","COO","CPRT","GLW","CPAY","CTVA","CSGP","CTRA","DHR","DVA","DAY",
    "XRAY","FANG","DFS","DOV","EMN","EG","EVRG","ES","EXPD","EXR","FFIV",
    "FRT","FMC","FTV","FOXA","FOX","BEN","GRMN","HAS","DOC","HEI","HOLX",
    "HWM","HBAN","HII","IEX","INCY","IR","PODD","IVZ","INVH","IQV","JBHT",
    "JBL","JKHY","J","JNPR","KVUE","KIM","LW","LDOS","LYV","LKQ","LYB",
    "MRO","MKTX","MLM","MAS","MTCH","MOH","TAP","MDLZ","MPWR","MNST","MOS",
    "NWS","NWSA","NI","NDSN","NTRS","NRG","NUE","NVR","PKG","PNR","PCG",
    "PNW","POOL","PPL","PFG","PEG","PTC","PHM","QRVO","RL","RJF","RF","RVTY",
    "ROL","RCL","SNA","SO","LUV","SWK","STX","SJM","SOLV","SWKS","TPR",
    "TRGP","TEL","TDY","TFX","TER","TXT","TYL","UDR","ULTA","UHS","VTRS",
    "VST","WRB","GWW","WAB","WBD","WST","WRK","WHR","WTW","XYL",
    # NASDAQ / Growth
    "ASML","BIDU","BKNG","MELI","MRVL","NFLX","NTES","OKTA","PDD","TEAM",
    "WDAY","ZM","ZS","JD","ILMN","SIRI","BMRN","INCY","SGEN","MRVL","SPLK",
    "TCOM","VRSN","VRSK","FISV","CERN","CHKP","ATVI","ALXN",
    # High momentum / growth
    "SQ","COIN","HOOD","SOFI","PLTR","CRWD","DDOG","NET","SNOW","MDB",
    "HUBS","TWLO","DOCN","GTLB","CFLT","BRZE","BILL","APPN","LYFT","DASH",
    "SNAP","PINS","SPOT","RBLX","U","SHOP","RIVN","NIO","XPEV","LI","CHPT",
    "BLNK","EVGO","PLUG","BABA","SE","GRAB","NU","NVO","BNTX","HIMS","TDOC",
    "DOCS","IBKR","AFRM","UPST","ACHR","JOBY","RKLB","LUNR","ASTS","MARA",
    "RIOT","CLSK","HUT","CORZ","DELL","PSTG","AMKR","COHU","ONTO","MKSI",
    "KLIC","ICHR","AI","BBAI","SOUN","IONQ","RGTI","QUBT","QBTS","MSTR",
    "HOOD","NU","AFRM","UPST","LC","OPEN","RDFN","Z","HIMS","CELH","RXRX",
    "ARWR","NTLA","BEAM","EDIT","CRSP","PCVX","ROIV","INSM","NVAX","SRPT",
    "SMCI","AOSL","DIOD","FORM","ONTO","AMKR","WOLF","MKSI","AEHR","ACMR",
    "TSM","ASML","AMAT","LAM","KLAC","NVDA","AMD","INTC","QCOM","AVGO",
    "TXN","MCHP","ADI","NXPI","SWKS","QRVO","MRVL","SLAB","MPWR","WOLF",
    # ETFs
    "SPY","QQQ","IWM","DIA","MDY","IJR","IVV","VOO","VTI",
    "SMH","SOXX","XLK","XLF","XLE","XLV","XLI","XLB","XLU","XLP","XLY",
    "ARKK","ARKG","ARKW","ARKF","GLD","SLV","GDX","GDXJ","TLT","IEF",
    "SOXL","TQQQ","UPRO","LABU","BOTZ","ROBO","AIQ",
    # Energy
    "XOM","CVX","COP","SLB","HAL","OXY","MPC","VLO","PSX","DVN","PXD",
    "EOG","FANG","HES","COP","MRO","APA","NOG","CTRA","SM","RRC","EQT",
    # Biotech
    "LLY","NVO","MRNA","BNTX","ABBV","JNJ","PFE","AMGN","GILD","REGN",
    "VRTX","BIIB","ILMN","TDOC","HIMS","ACAD","ALNY","BMRN","EXAS","FATE",
    # Financials
    "GS","JPM","BAC","C","WFC","MS","BLK","SCHW","IBKR","AXP","V","MA",
    "PYPL","FIS","FI","GPN","FISV","COF","DFS","SYF","AIG","MET","PRU",
    # Consumer
    "AMZN","WMT","TGT","COST","HD","LOW","NKE","LULU","ETSY","ABNB","UBER",
    "DASH","LYFT","SNAP","PINS","RBLX","SPOT","DIS","NFLX","PARA","WBD",
    "MCD","SBUX","YUM","CMG","DPZ","QSR","TXRH",
]))

def get_stock_list():
    log.info(f"Ticker universe: {len(TICKERS)}")
    return list(TICKERS)

# ══════════════════════════════════════════════
#  DATA FETCHING — retry + validation
# ══════════════════════════════════════════════
def safe_fetch(ticker_obj, period, interval, min_bars, retries=2):
    for attempt in range(retries + 1):
        try:
            df = ticker_obj.history(period=period, interval=interval,
                                    auto_adjust=True)
            if df is None or df.empty or len(df) < min_bars:
                if attempt < retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                return None
            df = df.dropna(subset=["Close"])
            return df if len(df) >= min_bars else None
        except Exception as e:
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
            else:
                log.debug(f"fetch {interval}: {e}")
    return None

def build_4h(df_1h):
    if df_1h is None or len(df_1h) < 24:
        return None
    try:
        df = df_1h.resample("4h").agg({
            "Open":"first","High":"max",
            "Low":"min","Close":"last","Volume":"sum"
        }).dropna(subset=["Close"])
        return df if len(df) >= 30 else None
    except Exception:
        return None

def fetch_data(symbol):
    try:
        t     = yf.Ticker(symbol)
        df_1h = safe_fetch(t, "60d",  "1h",  48)
        df_4h = build_4h(df_1h)
        df_1d = safe_fetch(t, "2y",   "1d",  100)
        df_1w = safe_fetch(t, "5y",   "1wk", 52)
        df_1m = safe_fetch(t, "10y",  "1mo", 24)
        if any(x is None for x in [df_4h, df_1d, df_1w, df_1m]):
            return None
        return {"4h": df_4h, "1d": df_1d, "1wk": df_1w, "1mo": df_1m}
    except Exception as e:
        log.debug(f"fetch_data {symbol}: {e}")
        return None

# ══════════════════════════════════════════════
#  INDICATORS
# ══════════════════════════════════════════════
def ema(s, p): return s.ewm(span=p, adjust=False).mean()

def macd(close):
    m   = ema(close,12) - ema(close,26)
    sig = ema(m, 9)
    return m, sig, m - sig

def rsi(close, p=14):
    d = close.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - 100/(1 + g/(l+1e-9))

def atr(high, low, close, p=14):
    tr = pd.concat([
        high-low,
        (high-close.shift()).abs(),
        (low-close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def all_emas(close):
    return {n: ema(close,p) for n,p in
            [("e9",9),("e21",21),("e50",50),("e100",100),("e200",200)]}

def vol_ratio(vol, p=20):
    avg = vol.rolling(p).mean().iloc[-1]
    return round(vol.iloc[-1]/(avg+1e-9), 2)

def rs_vs_spy(close, spy, bars=50):
    if len(close)<bars or spy is None or len(spy)<bars: return 1.0
    return round((close.iloc[-1]/close.iloc[-bars]) /
                 (spy.iloc[-1]/spy.iloc[-bars]+1e-9), 2)

# ══════════════════════════════════════════════
#  SIGNAL CHECKS — RELAXED for more signals
# ══════════════════════════════════════════════
def macd_bullish(m, sig, hist):
    """MACD bull: line > signal AND histogram positive AND growing last bar."""
    if len(hist) < 3: return False
    return (m.iloc[-1] > sig.iloc[-1] and
            hist.iloc[-1] > 0 and
            hist.iloc[-1] > hist.iloc[-2])

def macd_bearish(m, sig, hist):
    if len(hist) < 3: return False
    return (m.iloc[-1] < sig.iloc[-1] and
            hist.iloc[-1] < 0 and
            hist.iloc[-1] < hist.iloc[-2])

def ema_bull(close, e):
    p = close.iloc[-1]
    return (p > e["e21"].iloc[-1] > e["e50"].iloc[-1] and
            e["e21"].iloc[-1] > e["e21"].iloc[-4])

def ema_bear(close, e):
    p = close.iloc[-1]
    return (p < e["e21"].iloc[-1] < e["e50"].iloc[-1] and
            e["e21"].iloc[-1] < e["e21"].iloc[-4])

def price_near_ema(close, e):
    p = close.iloc[-1]
    for name, key in [("EMA21","e21"),("EMA50","e50")]:
        ev = e[key].iloc[-1]
        if abs(p-ev)/ev*100 < 4.0:
            return name
    return None

def not_pumped(close, e, pct=12.0):
    """Price must be within pct% of EMA21 — relaxed to 12%."""
    p   = close.iloc[-1]
    e21 = e["e21"].iloc[-1]
    return abs(p-e21)/e21*100 < pct

def divergence_bull(close, m_line, lb=15):
    if len(close) < lb+2: return False
    return (close.iloc[-1] < close.iloc[-lb:-1].min() and
            m_line.iloc[-1] > m_line.iloc[-lb:-1].min())

def divergence_bear(close, m_line, lb=15):
    if len(close) < lb+2: return False
    return (close.iloc[-1] > close.iloc[-lb:-1].max() and
            m_line.iloc[-1] < m_line.iloc[-lb:-1].max())

def calc_sl_tp_long(price, e, atr_v):
    e50  = e["e50"].iloc[-1]
    sl   = round(min(e50*0.993, price-1.5*atr_v), 2)
    risk = max(price-sl, 0.01)
    return sl, round(price+1.5*risk,2), round(price+3*risk,2), round(1.5*risk/risk,2)

def calc_sl_tp_short(price, e, atr_v):
    e50  = e["e50"].iloc[-1]
    sl   = round(max(e50*1.007, price+1.5*atr_v), 2)
    risk = max(sl-price, 0.01)
    return sl, round(price-1.5*risk,2), round(price-3*risk,2), round(1.5*risk/risk,2)

def earnings_days(symbol):
    try:
        cal = yf.Ticker(symbol).calendar
        if cal is not None and not cal.empty and "Earnings Date" in cal.index:
            for d in cal.loc["Earnings Date"]:
                if pd.notna(d):
                    days = (pd.Timestamp(d).date()-datetime.utcnow().date()).days
                    if days >= 0: return days
    except Exception: pass
    return None

# ══════════════════════════════════════════════
#  ANALYSE ONE TIMEFRAME
# ══════════════════════════════════════════════
def analyse(df):
    try:
        c  = df["Close"].dropna()
        h  = df["High"].dropna()
        lo = df["Low"].dropna()
        v  = df["Volume"].dropna() if "Volume" in df.columns else None
        if len(c) < 50: return None
        m, sig, hist = macd(c)
        e            = all_emas(c)
        atr_v        = atr(h, lo, c).iloc[-1]
        vr           = vol_ratio(v) if v is not None and len(v)>20 else 1.0
        return {
            "bull":    macd_bullish(m, sig, hist),
            "bear":    macd_bearish(m, sig, hist),
            "ml":      m,
            "hist":    hist,
            "ema_bull": ema_bull(c, e),
            "ema_bear": ema_bear(c, e),
            "no_pump": not_pumped(c, e),
            "near":    price_near_ema(c, e),
            "rsi":     round(rsi(c).iloc[-1], 1),
            "atr":     atr_v,
            "emas":    e,
            "close":   c,
            "vr":      vr,
            "div_b":   divergence_bull(c, m),
            "div_s":   divergence_bear(c, m),
        }
    except Exception as ex:
        log.debug(f"analyse: {ex}")
        return None

# ══════════════════════════════════════════════
#  SCORE TICKER
# ══════════════════════════════════════════════
def score_ticker(symbol, spy_close=None, mode="full"):
    data = fetch_data(symbol)
    if not data: return None

    t4  = analyse(data["4h"])
    t1d = analyse(data["1d"])
    t1w = analyse(data["1wk"])
    t1m = analyse(data["1mo"])

    if not all([t4, t1d, t1w, t1m]): return None

    price = round(t4["close"].iloc[-1], 2)
    atr_v = t4["atr"]
    rs    = rs_vs_spy(t1d["close"], spy_close)

    # ── LONG ──────────────────────────────────
    # Core: MACD bull on all 3 higher TFs
    macd_3b = t1d["bull"] and t1w["bull"] and t1m["bull"]

    # Full mode: also needs 4H EMA aligned
    # MACD-only: just needs the 3TF MACD
    long_pass = macd_3b and t4["no_pump"] and (
        mode == "macd_only" or t4["ema_bull"]
    )

    if long_pass:
        sl, tp1, tp2, rr = calc_sl_tp_long(price, t4["emas"], atr_v)
        if sl >= price: return None
        earn  = earnings_days(symbol)
        near  = t4["near"] or "—"
        score = sum([
            t1d["bull"]*2, t1w["bull"]*2, t1m["bull"]*2,
            t4["bull"],                    # 4H MACD bonus
            t4["ema_bull"] if mode=="full" else 0,
            near != "—",                   # pullback to EMA
            t4["vr"] > 1.2,               # volume
            t1d["div_b"],                  # divergence
            rs > 1.05,                     # beats SPY
            t4["rsi"] < 55,               # not overbought
        ])
        return dict(
            signal="BUY", ticker=symbol, price=price,
            score=score, sl=sl, tp1=tp1, tp2=tp2, rr=rr,
            rsi=t4["rsi"], vr=t4["vr"], rs=rs,
            div=t1d["div_b"], near=near,
            earn=earn, macd4h=t4["bull"], mode=mode
        )

    # ── SHORT ──────────────────────────────────
    macd_3s = t1d["bear"] and t1w["bear"] and t1m["bear"]

    short_pass = macd_3s and t4["no_pump"] and (
        mode == "macd_only" or t4["ema_bear"]
    )

    if short_pass:
        sl, tp1, tp2, rr = calc_sl_tp_short(price, t4["emas"], atr_v)
        if sl <= price: return None
        earn  = earnings_days(symbol)
        near  = t4["near"] or "—"
        score = sum([
            t1d["bear"]*2, t1w["bear"]*2, t1m["bear"]*2,
            t4["bear"],
            t4["ema_bear"] if mode=="full" else 0,
            near != "—",
            t4["vr"] > 1.2,
            t1d["div_s"],
            rs < 0.95,
            t4["rsi"] > 45,
        ])
        return dict(
            signal="SHORT", ticker=symbol, price=price,
            score=score, sl=sl, tp1=tp1, tp2=tp2, rr=rr,
            rsi=t4["rsi"], vr=t4["vr"], rs=rs,
            div=t1d["div_s"], near=near,
            earn=earn, macd4h=t4["bear"], mode=mode
        )

    return None

# ══════════════════════════════════════════════
#  FORMAT ALERT  — best looking possible
# ══════════════════════════════════════════════
def fmt(r: dict, is_free=False) -> str:
    buy    = r["signal"] == "BUY"
    top    = "🟢 LONG SETUP 📈" if buy else "🔴 SHORT SETUP 📉"
    sl_lbl = "SL below EMA50" if buy else "SL above EMA50"
    tp_dir = "above" if buy else "below"

    stars = "⭐" * min(r["score"], 10)
    conf  = (
        "🔥 VERY HIGH" if r["score"] >= 8 else
        "✅ HIGH"       if r["score"] >= 6 else
        "🔵 MEDIUM"    if r["score"] >= 4 else
        "⚪ LOW"
    )

    rsi_tag = (
        "🟢 Oversold"    if (buy  and r["rsi"]<40) else
        "🔴 Overbought"  if (not buy and r["rsi"]>60) else
        "🔵 Neutral"
    )
    vol_tag = (
        "🔥 HIGH"   if r["vr"]>1.5 else
        "✅ Good"   if r["vr"]>1.1 else
        "⚪ Normal"
    )
    rs_tag = (
        f"🚀 {r['rs']}x vs SPY" if r["rs"]>1.2 else
        f"✅ {r['rs']}x vs SPY" if r["rs"]>1.0 else
        f"⚠️ {r['rs']}x vs SPY"
    )

    earn_line = ""
    if r["earn"] is not None:
        if   r["earn"] <= 3:  earn_line = f"\n🚨 *EARNINGS IN {r['earn']} DAYS — SKIP*"
        elif r["earn"] <= 7:  earn_line = f"\n⚠️ *Earnings in {r['earn']} days — reduce size*"
        elif r["earn"] <= 14: earn_line = f"\n📅 Earnings in {r['earn']} days"

    mode_tag  = "MACD" if r["mode"]=="macd_only" else "FULL"
    macd4h    = "✅ Confirmed" if r["macd4h"] else "⏳ Pending"
    div_tag   = "✅ YES — strong signal" if r["div"] else "—"
    near_tag  = r["near"] if r["near"] != "—" else "Extended"

    lock = "\n\n🔒 _Upgrade to PRO for full details_ → /upgrade" if is_free else ""

    msg = (
        f"{'━'*22}\n"
        f"{top}\n"
        f"{'━'*22}\n"
        f"📌 *{r['ticker']}*   `[{mode_tag}]`\n"
        f"💰 *Price:* ${r['price']}\n\n"
        f"*📊 TRADE LEVELS*\n"
        f"🎯 Entry:       `${r['price']}`\n"
        f"🛑 {sl_lbl}:  `${r['sl']}`\n"
        f"💵 TP1 ({tp_dir} entry): `${r['tp1']}`\n"
        f"🏆 TP2 ({tp_dir} entry): `${r['tp2']}`\n"
        f"📐 Risk/Reward: `1:{r['rr']}`\n\n"
        f"*📈 INDICATORS (4H)*\n"
        f"├ RSI:        {r['rsi']}  {rsi_tag}\n"
        f"├ Volume:     {vol_tag}  ({r['vr']}× avg)\n"
        f"├ Near EMA:   {near_tag}\n"
        f"├ 4H MACD:    {macd4h}\n"
        f"├ Divergence: {div_tag}\n"
        f"└ RS vs SPY:  {rs_tag}\n\n"
        f"*⚡ CONFIDENCE:* {conf}\n"
        f"{stars}  ({r['score']}/10)"
        f"{earn_line}{lock}\n"
        f"{'━'*22}"
    )
    return msg

# ══════════════════════════════════════════════
#  SCAN ENGINE
# ══════════════════════════════════════════════
async def run_full_scan(app, manual_cid=None):
    log.info("Scan starting...")
    spy_close = None
    try:
        spy_close = yf.Ticker("SPY").history(
            period="1y", interval="1d")["Close"].dropna()
        log.info(f"SPY loaded: {len(spy_close)} bars")
    except Exception:
        log.warning("SPY fetch failed")

    tickers = get_stock_list()
    buys, shorts, errors = [], [], 0

    for i, sym in enumerate(tickers):
        try:
            res = score_ticker(sym, spy_close, mode="full")
            if res:
                (buys if res["signal"]=="BUY" else shorts).append(res)
                log.info(f"{res['signal']} {sym} sc={res['score']} rr={res['rr']}")
        except Exception as e:
            errors += 1
            log.debug(f"{sym}: {e}")

        # Rate limit: pause every 40 tickers
        if i > 0 and i % 40 == 0:
            await asyncio.sleep(2 + random.uniform(0,1))
            log.info(f"Progress: {i}/{len(tickers)} | B:{len(buys)} S:{len(shorts)}")

    buys.sort(  key=lambda x: (x["score"], x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    log.info(f"Scan complete. Buys:{len(buys)} Shorts:{len(shorts)} Err:{errors}")

    db = load_db()
    if manual_cid:
        # Only send to the person who triggered manual scan
        u = get_user(db, manual_cid)
        await send_report(app.bot, u, buys, shorts, len(tickers), errors)
    else:
        # Auto scan — send to all registered users
        for uid, udata in db.items():
            try:
                await send_report(app.bot, udata, buys, shorts, len(tickers), errors)
                await asyncio.sleep(0.5)
            except Exception as e:
                log.warning(f"Deliver to {uid}: {e}")

async def send_report(bot, user, buys, shorts, total, errors=0):
    cid     = user["chat_id"]
    pro     = is_pro(user)
    max_r   = PRO_MAX if pro else FREE_MAX
    is_free = not pro
    et      = datetime.now(pytz.timezone("America/New_York"))
    tier    = "⭐ PRO" if pro else "🆓 FREE"

    # Header
    header = (
        f"{'━'*22}\n"
        f"📊 *SWING SCANNER REPORT*\n"
        f"{'━'*22}\n"
        f"🕐 {et.strftime('%a %b %d  %H:%M ET')}\n"
        f"🏷 Tier: *{tier}*\n"
        f"🔍 Scanned: *{total}* stocks\n"
        f"🟢 *{min(len(buys),max_r)}* Longs   🔴 *{min(len(shorts),max_r)}* Shorts\n"
        f"{'━'*22}"
    )
    try:
        await bot.send_message(cid, header, parse_mode=ParseMode.MARKDOWN)
    except Exception: return
    await asyncio.sleep(0.4)

    # Longs
    if buys[:max_r]:
        await bot.send_message(cid,
            f"🟢 *TOP LONG SETUPS*  —  {len(buys[:max_r])} found",
            parse_mode=ParseMode.MARKDOWN)
        for r in buys[:max_r]:
            try:
                await bot.send_message(cid, fmt(r, is_free),
                                       parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.35)
            except Exception as e:
                log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,
            "🟢 *No long setups this scan*\n"
            "_Market may be extended or choppy — strategy filters are strict ✅_",
            parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(0.8)

    # Shorts
    if shorts[:max_r]:
        await bot.send_message(cid,
            f"🔴 *TOP SHORT SETUPS*  —  {len(shorts[:max_r])} found",
            parse_mode=ParseMode.MARKDOWN)
        for r in shorts[:max_r]:
            try:
                await bot.send_message(cid, fmt(r, is_free),
                                       parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.35)
            except Exception as e:
                log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,
            "🔴 *No short setups this scan*",
            parse_mode=ParseMode.MARKDOWN)

    # Footer
    if is_free:
        footer = (
            f"{'━'*22}\n"
            f"🔒 *FREE TIER*\n"
            f"You saw {FREE_MAX} of {len(buys)} longs, {len(shorts)} shorts\n\n"
            f"⭐ *Upgrade to PRO — ${PRO_PRICE}/month*\n"
            f"✅ All {PRO_MAX} results per scan\n"
            f"✅ Full indicator details\n"
            f"✅ Divergence + RS vs SPY\n"
            f"✅ Priority access\n\n"
            f"👉 /upgrade to see payment options\n"
            f"{'━'*22}\n"
            f"_Not financial advice._"
        )
    else:
        footer = (
            f"{'━'*22}\n"
            f"📋 *TRADE RULES*\n"
            f"🟢 LONG → SL below EMA50 → TP1 close 50% → TP2 trail\n"
            f"🔴 SHORT → SL above EMA50 → TP1 cover 50% → TP2 trail\n"
            f"⚠️ Skip trades with earnings < 7 days\n"
            f"📊 Always check the chart before entering\n"
            f"{'━'*22}\n"
            f"_Not financial advice. Manage your own risk._"
        )
    await bot.send_message(cid, footer, parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  USER COMMANDS
# ══════════════════════════════════════════════
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
        f"{'━'*22}\n"
        f"🚀 *ULTIMATE SWING SCANNER*\n"
        f"{'━'*22}\n\n"
        f"Welcome, *{u['name']}*! 👋\n"
        f"Your Tier: *{tier}*\n"
        f"Your ID: `{cid}`\n\n"
        f"*📋 COMMANDS*\n"
        f"━━━━━━━━━━━━\n"
        f"/scan — Run scan now\n"
        f"/mode — Switch MACD / Full\n"
        f"/status — Your account info\n"
        f"/upgrade — Get PRO access\n"
        f"/help — How to use signals\n"
        f"/signals — What each field means\n\n"
        f"*🔄 AUTO SCAN*\n"
        f"Every 4 hours automatically\n\n"
        f"*📊 STRATEGY*\n"
        f"MACD bull on Daily+Weekly+Monthly\n"
        f"4H EMA stack + Volume + RS filters\n"
        f"Entry, SL, TP1, TP2 auto-calculated\n"
        f"{'━'*22}\n"
        f"{'⭐ PRO: 25 results, full details' if pro else f'🔒 FREE: {FREE_MAX} results — /upgrade for full access'}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)

    if is_pro(u):
        exp = u.get("pro_until") or "Lifetime"
        await update.message.reply_text(
            f"✅ *You already have PRO access!*\nExpires: `{exp}`",
            parse_mode=ParseMode.MARKDOWN)
        return

    kb = [
        [InlineKeyboardButton("💰 Pay with USDT (TRC20)", callback_data="pay_usdt")],
        [InlineKeyboardButton("₿ Pay with Bitcoin",       callback_data="pay_btc")],
        [InlineKeyboardButton("Ξ Pay with Ethereum",      callback_data="pay_eth")],
        [InlineKeyboardButton("◎ Pay with Solana",        callback_data="pay_sol")],
    ]
    await update.message.reply_text(
        f"{'━'*22}\n"
        f"⭐ *UPGRADE TO PRO*\n"
        f"{'━'*22}\n\n"
        f"*${PRO_PRICE}/month*\n\n"
        f"✅ *{PRO_MAX} setups per scan* (vs {FREE_MAX} free)\n"
        f"✅ Full indicator details\n"
        f"✅ Divergence detection\n"
        f"✅ RS vs SPY analysis\n"
        f"✅ Earnings warnings\n"
        f"✅ MACD + Full strategy modes\n"
        f"✅ Priority signal delivery\n\n"
        f"👇 *Choose your payment method:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def callback_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    cid = q.from_user.id

    wallets = {
        "pay_usdt": ("💰 USDT TRC20", USDT_TRC20, "USDT"),
        "pay_btc":  ("₿ Bitcoin",     BTC_WALLET,  "BTC"),
        "pay_eth":  ("Ξ Ethereum",    ETH_WALLET,  "ETH"),
        "pay_sol":  ("◎ Solana",      SOL_WALLET,  "SOL"),
    }
    label, wallet, coin = wallets.get(q.data, ("?","?","?"))

    await q.edit_message_text(
        f"{'━'*22}\n"
        f"{label} *PAYMENT*\n"
        f"{'━'*22}\n\n"
        f"💵 Amount: *${PRO_PRICE} USD* worth of {coin}\n\n"
        f"📋 Send to this address:\n"
        f"`{wallet}`\n\n"
        f"*After paying:*\n"
        f"DM {OWNER_USERNAME} with:\n"
        f"1️⃣ Screenshot of payment\n"
        f"2️⃣ Your Telegram ID: `{cid}`\n\n"
        f"✅ Access activated within 1 hour\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    pro = is_pro(u)
    et  = datetime.now(pytz.timezone("America/New_York"))
    wday = et.weekday()
    mkt  = "🟢 OPEN" if (wday<5 and 9<=et.hour<16) else "🔴 CLOSED"
    mode = "MACD Only" if u.get("mode")=="macd_only" else "Full Strategy"
    exp  = u.get("pro_until") or ("Lifetime" if pro else "—")

    await update.message.reply_text(
        f"{'━'*22}\n"
        f"📡 *YOUR ACCOUNT*\n"
        f"{'━'*22}\n\n"
        f"👤 Name: {u.get('name','—')}\n"
        f"🏷 Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"{'📅 Pro until: '+exp if pro else '👉 /upgrade to go PRO'}\n\n"
        f"📊 Scan Mode: *{mode}*\n"
        f"📬 Results: *{'Up to '+str(PRO_MAX) if pro else str(FREE_MAX)+' (FREE)'}*\n"
        f"🏛 Market: {mkt}\n"
        f"🕐 NY Time: {et.strftime('%H:%M ET')}\n\n"
        f"Use /mode to change strategy\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db   = load_db()
    cid  = update.effective_chat.id
    u    = get_user(db, cid)
    curr = "MACD Only" if u.get("mode")=="macd_only" else "Full Strategy"
    kb   = [[
        InlineKeyboardButton("📡 MACD Only",     callback_data="m_macd"),
        InlineKeyboardButton("🔬 Full Strategy", callback_data="m_full"),
    ]]
    await update.message.reply_text(
        f"*Scan Mode* — Current: *{curr}*\n\n"
        f"📡 *MACD Only*\n"
        f"MACD bullish on Daily+Weekly+Monthly\n"
        f"More signals, faster confirmation\n\n"
        f"🔬 *Full Strategy*\n"
        f"MACD + 4H EMA stack aligned\n"
        f"Stricter, higher quality setups",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def callback_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q  = update.callback_query
    await q.answer()
    db = load_db()
    u  = get_user(db, q.from_user.id)
    u["mode"] = "macd_only" if q.data=="m_macd" else "full"
    save_db(db)
    label = "📡 MACD Only" if u["mode"]=="macd_only" else "🔬 Full Strategy"
    await q.edit_message_text(
        f"✅ Mode set to *{label}*\n\nSend /scan to run now.",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db   = load_db()
    cid  = update.effective_chat.id
    u    = get_user(db, cid)
    u["scans"] = u.get("scans", 0) + 1
    save_db(db)
    mode  = u.get("mode", "full")
    ticks = get_stock_list()
    label = "📡 MACD Only" if mode=="macd_only" else "🔬 Full Strategy"

    await update.message.reply_text(
        f"🔍 *Scan Started*\n\n"
        f"Mode: *{label}*\n"
        f"Stocks: *{len(ticks)}*\n"
        f"⏱ Est. time: ~15 mins\n\n"
        f"_I'll send results when done..._",
        parse_mode=ParseMode.MARKDOWN
    )

    spy_close = None
    try:
        spy_close = yf.Ticker("SPY").history(
            period="1y",interval="1d")["Close"].dropna()
    except Exception: pass

    buys, shorts, errors = [], [], 0
    for i, sym in enumerate(ticks):
        try:
            res = score_ticker(sym, spy_close, mode=mode)
            if res:
                (buys if res["signal"]=="BUY" else shorts).append(res)
        except Exception:
            errors += 1
        if i > 0 and i % 40 == 0:
            await asyncio.sleep(2)

    buys.sort(  key=lambda x: (x["score"],x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"],x["rr"]), reverse=True)

    await send_report(context.bot, u, buys, shorts, len(ticks), errors)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{'━'*22}\n"
        f"📋 *HOW TO USE SIGNALS*\n"
        f"{'━'*22}\n\n"
        f"🟢 *LONG TRADES*\n"
        f"1. Enter at or near the shown price\n"
        f"2. Set SL immediately — below EMA50\n"
        f"3. TP1 → close 50-60% of position\n"
        f"4. TP2 → trail stop, let it run\n\n"
        f"🔴 *SHORT TRADES*\n"
        f"1. Short at or near the shown price\n"
        f"2. Set SL immediately — above EMA50\n"
        f"3. TP1 → cover 50-60% of short\n"
        f"4. TP2 → trail stop downward\n\n"
        f"📏 *R:R RATIO*\n"
        f"Only sends trades ≥ 1:1.5 R:R\n\n"
        f"⚠️ *RULES*\n"
        f"• Skip trades with earnings < 7 days\n"
        f"• Always glance at the chart first\n"
        f"• Never risk more than 2% per trade\n"
        f"• Move SL to breakeven after TP1 hits\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{'━'*22}\n"
        f"📊 *SIGNAL GUIDE*\n"
        f"{'━'*22}\n\n"
        f"*RSI*\n"
        f"< 40 = oversold (good for longs)\n"
        f"> 60 = overbought (good for shorts)\n\n"
        f"*Volume*\n"
        f"🔥 HIGH = 1.5x+ avg — strong move\n"
        f"✅ Good = 1.1x+ avg — decent\n"
        f"⚪ Normal = average volume\n\n"
        f"*Near EMA*\n"
        f"EMA21/EMA50 = ideal pullback entry\n"
        f"Extended = price far from EMAs\n\n"
        f"*4H MACD*\n"
        f"✅ Confirmed = all 4 TFs aligned\n"
        f"⏳ Pending = 3/4 TFs aligned\n\n"
        f"*Divergence*\n"
        f"YES = price & MACD disagree\n"
        f"Strong reversal signal bonus\n\n"
        f"*RS vs SPY*\n"
        f"🚀 > 1.2x = beating market strongly\n"
        f"✅ > 1.0x = beating market\n"
        f"⚠️ < 1.0x = lagging market\n\n"
        f"*⭐ Confidence Score*\n"
        f"8-10 = 🔥 Very High — best setups\n"
        f"6-7  = ✅ High — good setups\n"
        f"4-5  = 🔵 Medium — ok setups\n"
        f"{'━'*22}",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════
#  ADMIN COMMANDS  (owner only)
# ══════════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db    = load_db()
    total = len(db)
    pros  = sum(1 for u in db.values() if is_pro(u))
    await update.message.reply_text(
        f"{'━'*22}\n"
        f"🔧 *ADMIN PANEL*\n"
        f"{'━'*22}\n\n"
        f"👥 Total users: *{total}*\n"
        f"⭐ PRO: *{pros}*\n"
        f"🆓 FREE: *{total-pros}*\n\n"
        f"*Commands:*\n"
        f"/addpro `<id> <days>` — Grant PRO\n"
        f"/rmpro `<id>` — Remove PRO\n"
        f"/broadcast `<msg>` — Message all\n"
        f"/userlist — See all users",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_addpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addpro <user_id> <days>"); return
    try:
        tid  = int(args[0])
        days = int(args[1])
    except ValueError:
        await update.message.reply_text("Invalid. Example: /addpro 123456 30"); return
    db   = load_db()
    u    = get_user(db, tid)
    u["tier"]      = "pro"
    u["pro_until"] = (datetime.utcnow()+timedelta(days=days)).isoformat()
    save_db(db)
    await update.message.reply_text(
        f"✅ PRO granted to `{tid}` for *{days} days*\nExpires: `{u['pro_until']}`",
        parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(tid,
            f"🎉 *Your account is now PRO!*\n\n"
            f"✅ Valid for {days} days\n"
            f"✅ {PRO_MAX} results per scan\n"
            f"✅ Full indicator details\n\n"
            f"Send /scan to run your first Pro scan! 🚀",
            parse_mode=ParseMode.MARKDOWN)
    except Exception: pass

async def cmd_rmpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /rmpro <user_id>"); return
    try: tid = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID."); return
    db = load_db()
    u  = get_user(db, tid)
    u["tier"] = "free"
    u["pro_until"] = None
    save_db(db)
    await update.message.reply_text(
        f"✅ PRO removed from `{tid}`.", parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>"); return
    msg  = " ".join(context.args)
    db   = load_db()
    sent, fail = 0, 0
    for uid, ud in db.items():
        try:
            await context.bot.send_message(ud["chat_id"],
                f"📢 *Announcement*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except Exception: fail += 1
        await asyncio.sleep(0.1)
    await update.message.reply_text(f"Broadcast: {sent} sent, {fail} failed.")

async def cmd_userlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db    = load_db()
    lines = [f"*USER LIST* ({len(db)} total)\n"]
    for uid, u in list(db.items())[:50]:
        tier = "PRO⭐" if is_pro(u) else "free"
        name = u.get("username") or u.get("name") or "—"
        lines.append(f"`{uid}` | {name} | {tier}")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════
#  SCHEDULED SCAN
# ══════════════════════════════════════════════
async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    log.info("Scheduled scan triggered")
    await run_full_scan(context.application)

# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════
def main():
    if TELEGRAM_TOKEN == "YOUR_TOKEN":
        raise ValueError("Set TELEGRAM_TOKEN env var!")
    if OWNER_CHAT_ID == 0:
        raise ValueError("Set CHAT_ID env var!")

    log.info("Starting Ultimate Swing Scanner v5.0...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # User commands
    for cmd, fn in [
        ("start",   cmd_start),
        ("scan",    cmd_scan),
        ("mode",    cmd_mode),
        ("status",  cmd_status),
        ("upgrade", cmd_upgrade),
        ("help",    cmd_help),
        ("signals", cmd_signals),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_pay,  pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(callback_mode, pattern="^m_"))

    # Admin
    for cmd, fn in [
        ("admin",     cmd_admin),
        ("addpro",    cmd_addpro),
        ("rmpro",     cmd_rmpro),
        ("broadcast", cmd_broadcast),
        ("userlist",  cmd_userlist),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    # Auto scan every 4 hours
    app.job_queue.run_repeating(
        scheduled_scan, interval=SCAN_INTERVAL, first=120)

    log.info("Bot polling started v5.0 ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
