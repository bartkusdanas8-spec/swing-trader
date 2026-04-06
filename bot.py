"""
╔══════════════════════════════════════════════════════════════════════╗
║           SWING SCANNER PRO  v6.0                                  ║
║   Per-user private chat | Step-by-step onboarding                  ║
║   MACD(D/W/M) + 4H EMA + Stoch + Volume + RS + Divergence         ║
║   Multi-user | Free vs Pro | Crypto payments                       ║
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
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters,
    ConversationHandler
)
from telegram.constants import ParseMode

# ══════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN")
OWNER_CHAT_ID   = int(os.environ.get("CHAT_ID", "0"))
OWNER_USERNAME  = os.environ.get("OWNER_USERNAME", "@YourUsername")
USDT_TRC20      = os.environ.get("USDT_WALLET",  "YOUR_USDT_WALLET")
BTC_WALLET      = os.environ.get("BTC_WALLET",   "YOUR_BTC_WALLET")
ETH_WALLET      = os.environ.get("ETH_WALLET",   "YOUR_ETH_WALLET")
SOL_WALLET      = os.environ.get("SOL_WALLET",   "YOUR_SOL_WALLET")
PRO_PRICE       = os.environ.get("PRO_PRICE",    "29")

SCAN_INTERVAL   = 4 * 60 * 60
FREE_MAX        = 3
PRO_MAX         = 25
BOT_NAME        = "Swing Scanner Pro"
DATA_FILE       = Path("/tmp/users.json")

# Conversation states
ASK_NAME, ASK_EXPERIENCE, ASK_MODE, ONBOARD_DONE = range(4)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  DATABASE  — each user has their own record
# ══════════════════════════════════════════════════════
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
            "chat_id":    cid,
            "tier":       "free",
            "joined":     datetime.utcnow().isoformat(),
            "pro_until":  None,
            "mode":       "full",
            "username":   "",
            "name":       "",
            "first_name": "",
            "experience": "",
            "onboarded":  False,
            "scans":      0,
            "last_scan":  None,
            "auto_scan":  True,
        }
        save_db(db)
    return db[key]

def is_pro(u: dict) -> bool:
    if u.get("tier") != "pro":
        return False
    if u.get("pro_until") is None:
        return True
    try:
        return datetime.utcnow() < datetime.fromisoformat(u["pro_until"])
    except Exception:
        return False

def is_owner(cid: int) -> bool:
    return cid == OWNER_CHAT_ID

# ══════════════════════════════════════════════════════
#  TICKER UNIVERSE
# ══════════════════════════════════════════════════════
TICKERS = sorted(set([
    # S&P 500
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
    "PH","PAYX","PYPL","PEP","PFE","PM","PSX","PNC","PPG","PG","PGR",
    "PLD","PRU","PSA","PWR","QCOM","RTX","O","REGN","RSG","RMD","ROK","ROP",
    "ROST","SPGI","CRM","SBAC","SLB","SRE","NOW","SHW","SPG","SBUX","STT",
    "STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TGT","TSLA",
    "TXN","TMO","TJX","TSCO","TT","TDG","TRV","TFC","TSN","USB","UBER","UNP",
    "UAL","UPS","URI","UNH","VLO","VTR","VZ","VRTX","VICI","V","VMC","WBA",
    "WMT","DIS","WM","WAT","WFC","WELL","WDC","WY","WMB","WYNN","XEL","YUM",
    "ZBRA","ZBH","ZTS","GDDY","GL","GNRC","GRMN","IT","GEV","GEHC",
    "AXON","BALL","BKR","BBWI","BAX","BG","CAH","CARR","CBOE","CBRE",
    "CDW","CE","COR","CNC","CF","CRL","CHD","CINF","CFG","CAG","ED",
    "CEG","COO","CPRT","GLW","CPAY","CTVA","CSGP","CTRA","DVA",
    "XRAY","FANG","DOV","EMN","EG","EVRG","ES","EXPD","EXR","FFIV",
    "FRT","FMC","FTV","FOXA","FOX","BEN","HAS","DOC","HEI","HOLX",
    "HWM","HBAN","HII","IEX","INCY","IR","PODD","IVZ","INVH","IQV","JBHT",
    "JBL","JKHY","J","JNPR","KVUE","KIM","LW","LDOS","LYV","LKQ","LYB",
    "MRO","MKTX","MLM","MAS","MTCH","MOH","TAP","MDLZ","MPWR","MNST","MOS",
    "NWS","NWSA","NI","NDSN","NTRS","NRG","NUE","NVR","PKG","PNR","PCG",
    "PNW","POOL","PPL","PFG","PEG","PTC","PHM","QRVO","RL","RJF","RF","RVTY",
    "ROL","RCL","SNA","SO","LUV","SWK","STX","SJM","SOLV","SWKS","TPR",
    "TRGP","TEL","TDY","TFX","TER","TXT","TYL","UDR","ULTA","UHS","VTRS",
    "VST","WRB","GWW","WAB","WBD","WST","WHR","WTW","XYL",
    # NASDAQ / Growth
    "ASML","BIDU","BKNG","MELI","MRVL","NFLX","NTES","OKTA","PDD","TEAM",
    "WDAY","ZM","ZS","JD","ILMN","BMRN","SGEN","SPLK","TCOM","VRSN","VRSK",
    # High momentum
    "SQ","COIN","HOOD","SOFI","PLTR","CRWD","DDOG","NET","SNOW","MDB",
    "HUBS","TWLO","DOCN","GTLB","CFLT","BRZE","BILL","APPN","LYFT","DASH",
    "SNAP","PINS","SPOT","RBLX","U","SHOP","RIVN","NIO","XPEV","LI",
    "PLUG","BABA","SE","GRAB","NU","BNTX","HIMS","TDOC","DOCS","IBKR",
    "AFRM","UPST","ACHR","JOBY","RKLB","LUNR","ASTS","MARA","RIOT","CLSK",
    "CORZ","DELL","PSTG","AMKR","ONTO","AI","BBAI","SOUN","IONQ","MSTR",
    "LC","CELH","RXRX","ARWR","NTLA","BEAM","CRSP","INSM","SRPT",
    "TSM","LAM","KLAC","SLAB","WOLF","AEHR","ACMR",
    # ETFs
    "SPY","QQQ","IWM","DIA","MDY","IJR","IVV","VOO","VTI",
    "SMH","SOXX","XLK","XLF","XLE","XLV","XLI","XLB","XLU","XLP","XLY",
    "ARKK","ARKG","ARKW","GLD","SLV","GDX","GDXJ","TLT","IEF",
    "SOXL","TQQQ","UPRO","BOTZ","ROBO","AIQ",
    # Energy
    "APA","NOG","SM","RRC","EQT",
    # Biotech
    "NVO","ACAD","ALNY","EXAS","NVAX","PCVX","ROIV",
    # Financials extra
    "GPN","AIG",
    # Consumer extra
    "ABNB","PARA","WBD","QSR","TXRH",
]))

def get_stock_list():
    tickers = list(TICKERS)
    log.info(f"Ticker universe: {len(tickers)}")
    return tickers

# ══════════════════════════════════════════════════════
#  DATA FETCHING
# ══════════════════════════════════════════════════════
def safe_fetch(ticker_obj, period, interval, min_bars, retries=2):
    for attempt in range(retries + 1):
        try:
            df = ticker_obj.history(period=period, interval=interval, auto_adjust=True)
            if df is None or df.empty or len(df) < min_bars:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return None
            return df.dropna(subset=["Close"])
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
            else:
                log.debug(f"fetch {interval}: {e}")
    return None

def build_4h(df_1h):
    if df_1h is None or len(df_1h) < 24:
        return None
    try:
        df = df_1h.resample("4h").agg({
            "Open": "first", "High": "max",
            "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna(subset=["Close"])
        return df if len(df) >= 30 else None
    except Exception:
        return None

def fetch_data(symbol):
    try:
        t     = yf.Ticker(symbol)
        df_1h = safe_fetch(t, "60d",  "1h",   48)
        df_4h = build_4h(df_1h)
        df_1d = safe_fetch(t, "2y",   "1d",  100)
        df_1w = safe_fetch(t, "5y",   "1wk",  52)
        df_1m = safe_fetch(t, "10y",  "1mo",  24)
        if any(x is None for x in [df_4h, df_1d, df_1w, df_1m]):
            return None
        return {"4h": df_4h, "1d": df_1d, "1wk": df_1w, "1mo": df_1m}
    except Exception as e:
        log.debug(f"fetch_data {symbol}: {e}")
        return None

# ══════════════════════════════════════════════════════
#  INDICATORS
# ══════════════════════════════════════════════════════
def ema(s, p): return s.ewm(span=p, adjust=False).mean()

def macd(close):
    m   = ema(close, 12) - ema(close, 26)
    sig = ema(m, 9)
    return m, sig, m - sig

def stoch(high, low, close, k=14, d=3):
    ll = low.rolling(k).min()
    hh = high.rolling(k).max()
    pct_k = 100 * (close - ll) / (hh - ll + 1e-9)
    pct_d = pct_k.rolling(d).mean()
    return pct_k, pct_d

def rsi(close, p=14):
    d = close.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - 100 / (1 + g / (l + 1e-9))

def atr(high, low, close, p=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def all_emas(close):
    return {n: ema(close, p) for n, p in
            [("e9",9),("e21",21),("e50",50),("e100",100),("e200",200)]}

def vol_ratio(vol, p=20):
    avg = vol.rolling(p).mean().iloc[-1]
    return round(vol.iloc[-1] / (avg + 1e-9), 2)

def rs_vs_spy(close, spy, bars=50):
    if len(close) < bars or spy is None or len(spy) < bars:
        return 1.0
    return round(
        (close.iloc[-1] / close.iloc[-bars]) /
        (spy.iloc[-1] / spy.iloc[-bars] + 1e-9), 2
    )

# ══════════════════════════════════════════════════════
#  SIGNAL LOGIC
# ══════════════════════════════════════════════════════
def macd_bullish(m, sig, hist):
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
        if abs(p - ev) / ev * 100 < 4.0:
            return name
    return None

def not_pumped(close, e, pct=12.0):
    p   = close.iloc[-1]
    e21 = e["e21"].iloc[-1]
    return abs(p - e21) / e21 * 100 < pct

def stoch_bull_entry(k, d):
    # Stoch crossed up from oversold
    if len(k) < 3: return False
    return k.iloc[-1] < 40 and k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]

def stoch_bear_entry(k, d):
    if len(k) < 3: return False
    return k.iloc[-1] > 60 and k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]

def divergence_bull(close, m_line, lb=15):
    if len(close) < lb + 2: return False
    return (close.iloc[-1] < close.iloc[-lb:-1].min() and
            m_line.iloc[-1] > m_line.iloc[-lb:-1].min())

def divergence_bear(close, m_line, lb=15):
    if len(close) < lb + 2: return False
    return (close.iloc[-1] > close.iloc[-lb:-1].max() and
            m_line.iloc[-1] < m_line.iloc[-lb:-1].max())

def calc_sl_tp_long(price, e, atr_v):
    e50  = e["e50"].iloc[-1]
    sl   = round(min(e50 * 0.993, price - 1.5 * atr_v), 2)
    risk = max(price - sl, 0.01)
    return sl, round(price + 1.5 * risk, 2), round(price + 3 * risk, 2), round(1.5 * risk / risk, 2)

def calc_sl_tp_short(price, e, atr_v):
    e50  = e["e50"].iloc[-1]
    sl   = round(max(e50 * 1.007, price + 1.5 * atr_v), 2)
    risk = max(sl - price, 0.01)
    return sl, round(price - 1.5 * risk, 2), round(price - 3 * risk, 2), round(1.5 * risk / risk, 2)

def earnings_days(symbol):
    try:
        cal = yf.Ticker(symbol).calendar
        if cal is not None and not cal.empty and "Earnings Date" in cal.index:
            for d in cal.loc["Earnings Date"]:
                if pd.notna(d):
                    days = (pd.Timestamp(d).date() - datetime.utcnow().date()).days
                    if days >= 0: return days
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════
#  ANALYSE ONE TIMEFRAME
# ══════════════════════════════════════════════════════
def analyse(df):
    try:
        c  = df["Close"].dropna()
        h  = df["High"].dropna()
        lo = df["Low"].dropna()
        v  = df["Volume"].dropna() if "Volume" in df.columns else None
        if len(c) < 50: return None
        m, sig, hist = macd(c)
        e            = all_emas(c)
        k, d         = stoch(h, lo, c)
        atr_v        = atr(h, lo, c).iloc[-1]
        vr           = vol_ratio(v) if v is not None and len(v) > 20 else 1.0
        return {
            "bull":      macd_bullish(m, sig, hist),
            "bear":      macd_bearish(m, sig, hist),
            "ml":        m,
            "hist":      hist,
            "ema_bull":  ema_bull(c, e),
            "ema_bear":  ema_bear(c, e),
            "no_pump":   not_pumped(c, e),
            "near":      price_near_ema(c, e),
            "rsi":       round(rsi(c).iloc[-1], 1),
            "stoch_k":   round(k.iloc[-1], 1),
            "stoch_d":   round(d.iloc[-1], 1),
            "stoch_bull":stoch_bull_entry(k, d),
            "stoch_bear":stoch_bear_entry(k, d),
            "atr":       atr_v,
            "emas":      e,
            "close":     c,
            "vr":        vr,
            "div_b":     divergence_bull(c, m),
            "div_s":     divergence_bear(c, m),
        }
    except Exception as ex:
        log.debug(f"analyse: {ex}")
        return None

# ══════════════════════════════════════════════════════
#  SCORE TICKER
# ══════════════════════════════════════════════════════
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

    # ── LONG ──────────────────────────────────────────
    macd_3b = t1d["bull"] and t1w["bull"] and t1m["bull"]
    long_pass = macd_3b and t4["no_pump"] and (
        mode == "macd_only" or t4["ema_bull"]
    )

    if long_pass:
        sl, tp1, tp2, rr = calc_sl_tp_long(price, t4["emas"], atr_v)
        if sl >= price: return None
        earn  = earnings_days(symbol)
        near  = t4["near"] or "—"
        score = sum([
            t1d["bull"] * 2,
            t1w["bull"] * 2,
            t1m["bull"] * 2,
            t4["bull"],
            t4["ema_bull"] if mode == "full" else 0,
            near != "—",
            t4["stoch_bull"],       # Stoch crossup from oversold
            t4["vr"] > 1.2,
            t1d["div_b"],
            rs > 1.05,
            t4["rsi"] < 55,
        ])
        return dict(
            signal="BUY", ticker=symbol, price=price,
            score=score, sl=sl, tp1=tp1, tp2=tp2, rr=rr,
            rsi=t4["rsi"], stoch_k=t4["stoch_k"], stoch_d=t4["stoch_d"],
            vr=t4["vr"], rs=rs, div=t1d["div_b"], near=near,
            earn=earn, macd4h=t4["bull"], mode=mode
        )

    # ── SHORT ──────────────────────────────────────────
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
            t1d["bear"] * 2,
            t1w["bear"] * 2,
            t1m["bear"] * 2,
            t4["bear"],
            t4["ema_bear"] if mode == "full" else 0,
            near != "—",
            t4["stoch_bear"],
            t4["vr"] > 1.2,
            t1d["div_s"],
            rs < 0.95,
            t4["rsi"] > 45,
        ])
        return dict(
            signal="SHORT", ticker=symbol, price=price,
            score=score, sl=sl, tp1=tp1, tp2=tp2, rr=rr,
            rsi=t4["rsi"], stoch_k=t4["stoch_k"], stoch_d=t4["stoch_d"],
            vr=t4["vr"], rs=rs, div=t1d["div_s"], near=near,
            earn=earn, macd4h=t4["bear"], mode=mode
        )

    return None

# ══════════════════════════════════════════════════════
#  FORMAT ALERT
# ══════════════════════════════════════════════════════
def fmt(r: dict, is_free=False) -> str:
    buy    = r["signal"] == "BUY"
    arrow  = "📈" if buy else "📉"
    colour = "🟢" if buy else "🔴"
    action = "LONG" if buy else "SHORT"
    sl_lbl = "below EMA50" if buy else "above EMA50"
    tp_dir = "▲" if buy else "▼"

    score  = min(r["score"], 10)
    bar    = "█" * score + "░" * (10 - score)
    conf   = (
        "🔥 VERY HIGH" if score >= 8 else
        "✅ HIGH"       if score >= 6 else
        "🔵 MEDIUM"    if score >= 4 else
        "⚪ LOW"
    )

    rsi_v   = r["rsi"]
    rsi_tag = (
        "🟢 Oversold"   if (buy and rsi_v < 35) else
        "🔴 Overbought" if (not buy and rsi_v > 65) else
        "🔵 Neutral"
    )

    sk, sd  = r.get("stoch_k", 50), r.get("stoch_d", 50)
    if buy:
        stoch_tag = "🟢 Oversold ✅" if sk < 30 else ("🔵 Resetting" if sk < 50 else "⚪ Neutral")
    else:
        stoch_tag = "🔴 Overbought ✅" if sk > 70 else ("🔵 Resetting" if sk > 50 else "⚪ Neutral")

    vol_tag = (
        "🔥 HIGH"   if r["vr"] > 1.5 else
        "✅ Good"   if r["vr"] > 1.1 else
        "⚪ Normal"
    )
    rs_tag  = (
        f"🚀 {r['rs']}x" if r["rs"] > 1.2 else
        f"✅ {r['rs']}x" if r["rs"] > 1.0 else
        f"⚠️ {r['rs']}x"
    )

    earn_line = ""
    if r.get("earn") is not None:
        if   r["earn"] <= 3:  earn_line = f"\n🚨 *EARNINGS IN {r['earn']} DAYS — CAUTION*"
        elif r["earn"] <= 7:  earn_line = f"\n⚠️ *Earnings in {r['earn']} days — reduce size*"
        elif r["earn"] <= 14: earn_line = f"\n📅 Earnings in {r['earn']} days"

    mode_tag = "MACD" if r.get("mode") == "macd_only" else "FULL"
    macd4h   = "✅ Yes" if r.get("macd4h") else "⏳ Pending"
    div_tag  = "✅ YES" if r.get("div") else "—"
    near_tag = r.get("near", "—") if r.get("near") != "—" else "Extended"

    if is_free:
        # Free users: show setup but hide full details
        return (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{colour} *{action} SETUP*  {arrow}  `[{mode_tag}]`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{r['ticker']}*\n"
            f"💰 Price: `${r['price']}`\n\n"
            f"🎯 Entry:  `${r['price']}`\n"
            f"🛑 SL {sl_lbl}:  `${r['sl']}`\n"
            f"💵 TP1: `${r['tp1']}`\n"
            f"🏆 TP2: `🔒 PRO`\n"
            f"📐 R:R: `🔒 PRO`\n\n"
            f"⚡ Confidence: {conf}\n"
            f"`{bar}` {score}/10\n"
            f"{earn_line}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 _Full details, TP2, R:R, Stoch, Volume, RS → /upgrade_"
        )
    else:
        return (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{colour} *{action} SETUP*  {arrow}  `[{mode_tag}]`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{r['ticker']}*\n"
            f"💰 Price: `${r['price']}`\n\n"
            f"*📊 TRADE LEVELS*\n"
            f"🎯 Entry:          `${r['price']}`\n"
            f"🛑 SL ({sl_lbl}): `${r['sl']}`\n"
            f"💵 TP1 {tp_dir}:         `${r['tp1']}`\n"
            f"🏆 TP2 {tp_dir}:         `${r['tp2']}`\n"
            f"📐 Risk/Reward:    `1:{r['rr']}`\n\n"
            f"*📈 INDICATORS (4H)*\n"
            f"├ RSI:        `{rsi_v}`  {rsi_tag}\n"
            f"├ Stoch %K/D: `{sk}/{sd}`  {stoch_tag}\n"
            f"├ Volume:     {vol_tag} `({r['vr']}× avg)`\n"
            f"├ Near EMA:   `{near_tag}`\n"
            f"├ 4H MACD:    {macd4h}\n"
            f"├ Divergence: {div_tag}\n"
            f"└ RS vs SPY:  {rs_tag}\n\n"
            f"*⚡ CONFIDENCE:* {conf}\n"
            f"`{bar}` {score}/10"
            f"{earn_line}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

# ══════════════════════════════════════════════════════
#  ONBOARDING CONVERSATION
# ══════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)
    u["username"] = update.effective_user.username or ""
    save_db(db)

    if u.get("onboarded"):
        # Already onboarded — show main menu
        await show_main_menu(update, context, u)
        return ConversationHandler.END

    # Step 1 — Welcome + ask name
    tg_name = update.effective_user.first_name or "Trader"
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 *Welcome to {BOT_NAME}!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hey {tg_name}! 👋\n\n"
        f"I'm your personal swing trading scanner. I scan *{len(TICKERS)} stocks* every 4 hours using:\n\n"
        f"📡 MACD on Daily + Weekly + Monthly\n"
        f"📊 4H EMA stack + Stochastic\n"
        f"📈 Volume + RS vs SPY + Divergence\n\n"
        f"Let me set up your account in *3 quick steps* 👇\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Step 1 of 3*\n\n"
        f"What's your *first name*? ✍️",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_NAME

async def onboard_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or len(name) > 30:
        await update.message.reply_text("Please enter a valid name (max 30 chars):")
        return ASK_NAME

    context.user_data["onboard_name"] = name

    kb = ReplyKeyboardMarkup(
        [["🆕 Beginner (< 1 year)", "📊 Intermediate (1-3 years)"],
         ["🏆 Advanced (3+ years)", "💼 Professional trader"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        f"Nice to meet you, *{name}!* 👋\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Step 2 of 3*\n\n"
        f"What's your trading experience?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )
    return ASK_EXPERIENCE

async def onboard_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exp = update.message.text.strip()
    context.user_data["onboard_exp"] = exp

    kb = ReplyKeyboardMarkup(
        [["🔬 Full Strategy (MACD + EMA + Stoch)", "📡 MACD Only (more signals)"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Step 3 of 3*\n\n"
        f"Which scan mode do you want?\n\n"
        f"🔬 *Full Strategy*\n"
        f"MACD ✓ + 4H EMA stack ✓ + Stoch ✓\n"
        f"_Stricter — higher quality setups_\n\n"
        f"📡 *MACD Only*\n"
        f"MACD bullish on all 3 timeframes\n"
        f"_More signals — good for beginners_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )
    return ASK_MODE

async def onboard_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    mode   = "macd_only" if "MACD Only" in choice else "full"

    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)

    name = context.user_data.get("onboard_name", update.effective_user.first_name or "Trader")
    exp  = context.user_data.get("onboard_exp", "—")

    u["first_name"] = name
    u["name"]       = name
    u["experience"] = exp
    u["mode"]       = mode
    u["onboarded"]  = True
    save_db(db)

    mode_label = "📡 MACD Only" if mode == "macd_only" else "🔬 Full Strategy"
    pro         = is_pro(u)

    kb = ReplyKeyboardMarkup(
        [["🔍 Run Scan Now", "📊 My Status"],
         ["⭐ Upgrade to PRO", "❓ Help"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *You're all set, {name}!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *Your Setup:*\n"
        f"├ Name: *{name}*\n"
        f"├ Experience: *{exp}*\n"
        f"├ Scan Mode: *{mode_label}*\n"
        f"├ Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"└ Auto Scan: *Every 4 hours ✅*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*📋 COMMANDS*\n"
        f"/scan — Run a scan now\n"
        f"/status — Your account\n"
        f"/mode — Change scan mode\n"
        f"/upgrade — Get PRO access\n"
        f"/help — How to trade signals\n"
        f"/signals — What each indicator means\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{'🆓 FREE: You get 3 signals per scan — /upgrade for full access' if not pro else f'⭐ PRO: You get {PRO_MAX} signals per scan!'}\n\n"
        f"_Type /scan to run your first scan!_ 🚀",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )
    return ConversationHandler.END

async def onboard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Setup cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ══════════════════════════════════════════════════════
#  MAIN MENU  (for returning users)
# ══════════════════════════════════════════════════════
async def show_main_menu(update, context, u):
    name = u.get("first_name") or u.get("name") or "Trader"
    pro  = is_pro(u)
    tier = "⭐ PRO" if pro else "🆓 FREE"
    mode = "📡 MACD Only" if u.get("mode") == "macd_only" else "🔬 Full Strategy"

    kb = ReplyKeyboardMarkup(
        [["🔍 Run Scan Now", "📊 My Status"],
         ["⭐ Upgrade to PRO", "❓ Help"]],
        resize_keyboard=True
    )

    et  = datetime.now(pytz.timezone("America/New_York"))
    wday = et.weekday()
    mkt  = "🟢 OPEN" if (wday < 5 and 9 <= et.hour < 16) else "🔴 CLOSED"

    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 *{BOT_NAME}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Welcome back, *{name}!* 👋\n\n"
        f"🏷 Tier: *{tier}*\n"
        f"📊 Mode: *{mode}*\n"
        f"🏛 Market: {mkt}\n"
        f"🕐 NY Time: {et.strftime('%H:%M ET')}\n\n"
        f"*📋 COMMANDS*\n"
        f"/scan — Run scan now\n"
        f"/status — Your account\n"
        f"/mode — Change scan mode\n"
        f"/upgrade — Get PRO\n"
        f"/help — Signal guide\n"
        f"/signals — Indicator guide\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )

# ══════════════════════════════════════════════════════
#  KEYBOARD BUTTON HANDLER
# ══════════════════════════════════════════════════════
async def handle_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔍 Run Scan Now":
        await cmd_scan(update, context)
    elif text == "📊 My Status":
        await cmd_status(update, context)
    elif text == "⭐ Upgrade to PRO":
        await cmd_upgrade(update, context)
    elif text == "❓ Help":
        await cmd_help(update, context)

# ══════════════════════════════════════════════════════
#  SCAN ENGINE
# ══════════════════════════════════════════════════════
async def run_full_scan(app, manual_cid=None):
    log.info("Scan starting...")
    spy_close = None
    try:
        spy_close = yf.Ticker("SPY").history(period="1y", interval="1d")["Close"].dropna()
        log.info(f"SPY loaded: {len(spy_close)} bars")
    except Exception:
        log.warning("SPY fetch failed")

    tickers = get_stock_list()
    buys, shorts, errors = [], [], 0

    for i, sym in enumerate(tickers):
        try:
            res = score_ticker(sym, spy_close, mode="full")
            if res:
                (buys if res["signal"] == "BUY" else shorts).append(res)
                log.info(f"{res['signal']} {sym} sc={res['score']} rr={res['rr']}")
        except Exception as e:
            errors += 1
            log.debug(f"{sym}: {e}")

        if i > 0 and i % 40 == 0:
            await asyncio.sleep(2 + random.uniform(0, 1))
            log.info(f"Progress: {i}/{len(tickers)} | B:{len(buys)} S:{len(shorts)}")

    buys.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    log.info(f"Scan done. Buys:{len(buys)} Shorts:{len(shorts)} Errors:{errors}")

    db = load_db()
    if manual_cid:
        u = get_user(db, manual_cid)
        await send_report(app.bot, u, buys, shorts, len(tickers), errors)
    else:
        for uid, udata in db.items():
            if not udata.get("auto_scan", True):
                continue
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
    name    = user.get("first_name") or user.get("name") or "Trader"

    header = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *{BOT_NAME} — SCAN REPORT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {name}  |  🏷 {tier}\n"
        f"🕐 {et.strftime('%a %b %d  %H:%M ET')}\n"
        f"🔍 Scanned: *{total}* stocks\n"
        f"🟢 *{min(len(buys), max_r)}* Longs  ·  🔴 *{min(len(shorts), max_r)}* Shorts\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await bot.send_message(cid, header, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        return
    await asyncio.sleep(0.4)

    # Longs
    if buys[:max_r]:
        await bot.send_message(cid,
            f"🟢 *TOP LONG SETUPS — {len(buys[:max_r])} found*",
            parse_mode=ParseMode.MARKDOWN)
        for r in buys[:max_r]:
            try:
                await bot.send_message(cid, fmt(r, is_free), parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.4)
            except Exception as e:
                log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,
            "🟢 *No long setups this scan*\n"
            "_Strategy filters are strict — no garbage trades ✅_\n"
            "_Setups will appear when market conditions align_",
            parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(0.8)

    # Shorts
    if shorts[:max_r]:
        await bot.send_message(cid,
            f"🔴 *TOP SHORT SETUPS — {len(shorts[:max_r])} found*",
            parse_mode=ParseMode.MARKDOWN)
        for r in shorts[:max_r]:
            try:
                await bot.send_message(cid, fmt(r, is_free), parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.4)
            except Exception as e:
                log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,
            "🔴 *No short setups this scan*",
            parse_mode=ParseMode.MARKDOWN)

    # Footer
    if is_free:
        footer = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 *FREE TIER*  |  {name}\n"
            f"You saw *{FREE_MAX}* of *{len(buys)}* longs & *{len(shorts)}* shorts\n\n"
            f"⭐ *Upgrade to PRO — ${PRO_PRICE}/month*\n"
            f"✅ All {PRO_MAX} setups per scan\n"
            f"✅ Full Stoch + Volume + RS details\n"
            f"✅ TP2 + full R:R shown\n"
            f"✅ Divergence detection\n"
            f"✅ Earnings warnings\n\n"
            f"👉 /upgrade — see payment options\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Not financial advice. Manage your risk._"
        )
    else:
        footer = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 *TRADE RULES*  |  {name}\n"
            f"🟢 LONG → SL below EMA50 → TP1 (50%) → TP2 trail\n"
            f"🔴 SHORT → SL above EMA50 → TP1 (50%) → TP2 trail\n"
            f"⚠️ Skip trades with earnings < 7 days\n"
            f"📊 Always confirm chart before entering\n"
            f"💡 Never risk more than 2% per trade\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Not financial advice. Manage your own risk._"
        )
    await bot.send_message(cid, footer, parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════
#  USER COMMANDS
# ══════════════════════════════════════════════════════
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db   = load_db()
    cid  = update.effective_chat.id
    u    = get_user(db, cid)

    if not u.get("onboarded"):
        await update.message.reply_text(
            "Please complete setup first! Send /start 👋",
            parse_mode=ParseMode.MARKDOWN)
        return

    u["scans"]     = u.get("scans", 0) + 1
    u["last_scan"] = datetime.utcnow().isoformat()
    save_db(db)

    name  = u.get("first_name") or u.get("name") or "Trader"
    mode  = u.get("mode", "full")
    ticks = get_stock_list()
    label = "📡 MACD Only" if mode == "macd_only" else "🔬 Full Strategy"

    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 *Scan Started, {name}!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Mode: *{label}*\n"
        f"📈 Stocks: *{len(ticks)}*\n"
        f"⏱ Est. time: *~15 mins*\n\n"
        f"Checking MACD on D+W+M → 4H EMA + Stoch...\n\n"
        f"_I'll send results when done_ 📬",
        parse_mode=ParseMode.MARKDOWN
    )

    spy_close = None
    try:
        spy_close = yf.Ticker("SPY").history(period="1y", interval="1d")["Close"].dropna()
    except Exception:
        pass

    buys, shorts, errors = [], [], 0
    for i, sym in enumerate(ticks):
        try:
            res = score_ticker(sym, spy_close, mode=mode)
            if res:
                (buys if res["signal"] == "BUY" else shorts).append(res)
        except Exception:
            errors += 1
        if i > 0 and i % 40 == 0:
            await asyncio.sleep(2)

    buys.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)

    await send_report(context.bot, u, buys, shorts, len(ticks), errors)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db   = load_db()
    cid  = update.effective_chat.id
    u    = get_user(db, cid)
    pro  = is_pro(u)
    name = u.get("first_name") or u.get("name") or "Trader"
    et   = datetime.now(pytz.timezone("America/New_York"))
    wday = et.weekday()
    mkt  = "🟢 OPEN" if (wday < 5 and 9 <= et.hour < 16) else "🔴 CLOSED"
    mode = "📡 MACD Only" if u.get("mode") == "macd_only" else "🔬 Full Strategy"
    exp  = u.get("pro_until") or ("Lifetime" if pro else "—")
    last = u.get("last_scan", "Never")
    if last != "Never":
        try:
            last = datetime.fromisoformat(last).strftime("%b %d %H:%M UTC")
        except Exception:
            pass

    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *YOUR ACCOUNT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Name: *{name}*\n"
        f"🎓 Experience: *{u.get('experience', '—')}*\n"
        f"🏷 Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"{'📅 Pro until: `'+exp+'`' if pro else '👉 /upgrade to go PRO'}\n\n"
        f"📊 Scan Mode: *{mode}*\n"
        f"📬 Signals: *{'Up to '+str(PRO_MAX) if pro else str(FREE_MAX)+' (FREE)'}* per scan\n"
        f"🔢 Total Scans: *{u.get('scans', 0)}*\n"
        f"🕐 Last Scan: *{last}*\n\n"
        f"🏛 Market: {mkt}\n"
        f"🕐 NY Time: {et.strftime('%H:%M ET')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Use /mode to change strategy",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db   = load_db()
    cid  = update.effective_chat.id
    u    = get_user(db, cid)
    curr = "📡 MACD Only" if u.get("mode") == "macd_only" else "🔬 Full Strategy"
    kb   = [[
        InlineKeyboardButton("📡 MACD Only",     callback_data="m_macd"),
        InlineKeyboardButton("🔬 Full Strategy", callback_data="m_full"),
    ]]
    await update.message.reply_text(
        f"*Scan Mode* — Current: *{curr}*\n\n"
        f"📡 *MACD Only*\n"
        f"MACD bullish on Daily+Weekly+Monthly\n"
        f"More signals — good for active traders\n\n"
        f"🔬 *Full Strategy*\n"
        f"MACD + 4H EMA stack + Stochastic\n"
        f"Stricter — highest quality setups",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def callback_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q  = update.callback_query
    await q.answer()
    db = load_db()
    u  = get_user(db, q.from_user.id)
    u["mode"] = "macd_only" if q.data == "m_macd" else "full"
    save_db(db)
    label = "📡 MACD Only" if u["mode"] == "macd_only" else "🔬 Full Strategy"
    await q.edit_message_text(
        f"✅ Mode set to *{label}*\n\nSend /scan to run now.",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db  = load_db()
    cid = update.effective_chat.id
    u   = get_user(db, cid)

    if is_pro(u):
        exp = u.get("pro_until") or "Lifetime"
        await update.message.reply_text(
            f"✅ *You already have PRO access!*\n📅 Expires: `{exp}`",
            parse_mode=ParseMode.MARKDOWN)
        return

    kb = [
        [InlineKeyboardButton("💰 USDT TRC20",   callback_data="pay_usdt")],
        [InlineKeyboardButton("₿  Bitcoin",       callback_data="pay_btc")],
        [InlineKeyboardButton("Ξ  Ethereum",      callback_data="pay_eth")],
        [InlineKeyboardButton("◎  Solana",        callback_data="pay_sol")],
    ]
    name = u.get("first_name") or u.get("name") or "Trader"
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ *UPGRADE TO PRO*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hey {name}! Here's what you unlock:\n\n"
        f"🔓 *{PRO_MAX} setups per scan* (vs {FREE_MAX} free)\n"
        f"🔓 Full Stoch + Volume + RS details\n"
        f"🔓 TP2 + full Risk/Reward shown\n"
        f"🔓 Divergence detection\n"
        f"🔓 Earnings date warnings\n"
        f"🔓 MACD + Full strategy modes\n\n"
        f"💵 *${PRO_PRICE}/month*\n\n"
        f"👇 *Choose payment:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def callback_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    cid = q.from_user.id
    db  = load_db()
    u   = get_user(db, cid)
    name = u.get("first_name") or u.get("name") or "Trader"

    wallets = {
        "pay_usdt": ("💰 USDT TRC20", USDT_TRC20, "USDT"),
        "pay_btc":  ("₿ Bitcoin",     BTC_WALLET,  "BTC"),
        "pay_eth":  ("Ξ Ethereum",    ETH_WALLET,  "ETH"),
        "pay_sol":  ("◎ Solana",      SOL_WALLET,  "SOL"),
    }
    label, wallet, coin = wallets.get(q.data, ("?", "?", "?"))

    await q.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{label} *PAYMENT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 For: *{name}*\n"
        f"💵 Amount: *${PRO_PRICE} USD* in {coin}\n\n"
        f"📋 *Send to:*\n"
        f"`{wallet}`\n\n"
        f"*After paying, DM {OWNER_USERNAME} with:*\n"
        f"1️⃣ Screenshot of payment\n"
        f"2️⃣ Your Telegram ID: `{cid}`\n\n"
        f"✅ Access activated within 1 hour\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db   = load_db()
    cid  = update.effective_chat.id
    u    = get_user(db, cid)
    name = u.get("first_name") or u.get("name") or "Trader"
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *HOW TO TRADE SIGNALS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟢 *LONG TRADES*\n"
        f"1. Open chart — confirm candle looks good\n"
        f"2. Enter at or near the shown price\n"
        f"3. Set SL immediately — below EMA50\n"
        f"4. TP1 → close 50-60% of position\n"
        f"5. TP2 → trail stop, let it run\n\n"
        f"🔴 *SHORT TRADES*\n"
        f"1. Open chart — confirm rejection candle\n"
        f"2. Short at or near the shown price\n"
        f"3. Set SL immediately — above EMA50\n"
        f"4. TP1 → cover 50-60% of short\n"
        f"5. TP2 → trail stop downward\n\n"
        f"⚠️ *RULES*\n"
        f"• Skip trades with earnings < 7 days\n"
        f"• Never risk more than 2% per trade\n"
        f"• Move SL to breakeven after TP1 hits\n"
        f"• Always check volume before entering\n\n"
        f"📊 *YOUR STRATEGY FLOW*\n"
        f"Monthly MACD bull ✅\n"
        f"  → Weekly MACD bull ✅\n"
        f"  → Daily MACD bull ✅\n"
        f"  → 4H EMA stack aligned ✅\n"
        f"  → Stoch oversold crossup ✅\n"
        f"  → ENTRY 🎯\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Not financial advice, {name}. Manage your risk._",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *INDICATOR GUIDE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*RSI (4H)*\n"
        f"< 35 = oversold → good for longs\n"
        f"> 65 = overbought → good for shorts\n\n"
        f"*Stochastic %K/%D (4H)*\n"
        f"< 30 = oversold zone — look for crossup\n"
        f"> 70 = overbought zone — look for crossdown\n"
        f"Crossup below 30 = strongest entry signal\n\n"
        f"*Volume*\n"
        f"🔥 HIGH = 1.5x+ avg — strong conviction\n"
        f"✅ Good = 1.1x+ avg — decent\n"
        f"⚪ Normal = average volume\n\n"
        f"*Near EMA*\n"
        f"EMA21 = ideal pullback entry\n"
        f"EMA50 = stronger support, better R:R\n"
        f"Extended = price far from EMAs — wait\n\n"
        f"*Divergence*\n"
        f"Price lower low + MACD higher low = bull div\n"
        f"Strong reversal signal — high probability\n\n"
        f"*RS vs SPY*\n"
        f"🚀 > 1.2x = beating market strongly\n"
        f"✅ > 1.0x = beating market\n"
        f"⚠️ < 1.0x = lagging — skip if possible\n\n"
        f"*Confidence Score*\n"
        f"8-10 = 🔥 All filters aligned — best setup\n"
        f"6-7  = ✅ Strong — good setup\n"
        f"4-5  = 🔵 Medium — ok, check chart carefully\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db    = load_db()
    total = len(db)
    pros  = sum(1 for u in db.values() if is_pro(u))
    onboarded = sum(1 for u in db.values() if u.get("onboarded"))
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 *ADMIN PANEL*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total users: *{total}*\n"
        f"✅ Onboarded: *{onboarded}*\n"
        f"⭐ PRO: *{pros}*\n"
        f"🆓 FREE: *{total - pros}*\n\n"
        f"*Commands:*\n"
        f"/addpro `<id> <days>` — Grant PRO\n"
        f"/rmpro `<id>` — Remove PRO\n"
        f"/broadcast `<msg>` — Message all users\n"
        f"/userlist — List all users",
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
    db = load_db()
    u  = get_user(db, tid)
    u["tier"]      = "pro"
    u["pro_until"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
    save_db(db)
    await update.message.reply_text(
        f"✅ PRO granted to `{tid}` for *{days} days*",
        parse_mode=ParseMode.MARKDOWN)
    try:
        name = u.get("first_name") or u.get("name") or "Trader"
        await context.bot.send_message(tid,
            f"🎉 *Your account is now PRO, {name}!*\n\n"
            f"✅ Valid for {days} days\n"
            f"✅ {PRO_MAX} results per scan\n"
            f"✅ Full indicator details unlocked\n\n"
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
    await update.message.reply_text(f"✅ PRO removed from `{tid}`.", parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>"); return
    msg = " ".join(context.args)
    db  = load_db()
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
        tier  = "PRO⭐" if is_pro(u) else "free"
        name  = u.get("first_name") or u.get("username") or u.get("name") or "—"
        scans = u.get("scans", 0)
        lines.append(f"`{uid}` | {name} | {tier} | {scans} scans")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════
#  SCHEDULED SCAN
# ══════════════════════════════════════════════════════
async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    log.info("Scheduled scan triggered")
    await run_full_scan(context.application)

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    if TELEGRAM_TOKEN == "YOUR_TOKEN":
        raise ValueError("Set TELEGRAM_TOKEN env var!")
    if OWNER_CHAT_ID == 0:
        raise ValueError("Set CHAT_ID env var!")

    log.info(f"Starting {BOT_NAME} v6.0...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Onboarding conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            ASK_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_name)],
            ASK_EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_experience)],
            ASK_MODE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_mode)],
        },
        fallbacks=[CommandHandler("cancel", onboard_cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)

    # Keyboard button handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(
            "^(🔍 Run Scan Now|📊 My Status|⭐ Upgrade to PRO|❓ Help)$"
        ),
        handle_keyboard
    ))

    # User commands
    for cmd, fn in [
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

    # Auto scan every 4 hours (first scan after 3 mins)
    app.job_queue.run_repeating(scheduled_scan, interval=SCAN_INTERVAL, first=180)

    log.info(f"{BOT_NAME} v6.0 polling started ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
