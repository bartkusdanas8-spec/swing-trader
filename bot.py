"""
╔══════════════════════════════════════════════════════════════════════╗
║          ULTIMATE SWING SCANNER BOT v4.0                           ║
║  Multi-user | Free vs Pro | MACD(D/W/M) + 4H EMA + Filters        ║
║  Bulletproof data fetching | Retry logic | Rate limiting           ║
╚══════════════════════════════════════════════════════════════════════╝

FREE TIER  → MACD-only scan, delayed 2h, max 5 results, watermark
PRO TIER   → Full strategy, real-time, 20 results, no watermark
OWNER      → Everything, admin commands, broadcast, user management
"""

import os, asyncio, logging, json, time, random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import yfinance as yf
import pytz

from telegram import (
    Bot, Update,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler,
    ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)
from telegram.constants import ParseMode

# ════════════════════════════════════════════════════════════════
#  CONFIG  — set via Railway environment variables
# ════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_CHAT_ID  = int(os.environ.get("CHAT_ID", "0"))

PRO_MONTHLY_PRICE = "$29/month"
PRO_PAYMENT_INFO  = (
    "Send payment to:\n"
    "PayPal: your@email.com\n"
    "USDT (TRC20): YourWalletAddress\n\n"
    "After payment DM @YourUsername with proof and your Telegram ID.\n"
    "Access activated within 1 hour."
)

SCAN_INTERVAL = 4 * 60 * 60
FREE_DELAY_H  = 2
FREE_MAX      = 5
PRO_MAX       = 20

DATA_FILE = Path("/tmp/users.json")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
#  USER DATABASE  (flat JSON, no external DB needed)
# ════════════════════════════════════════════════════════════════
def load_users() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {}

def save_users(users: dict):
    DATA_FILE.write_text(json.dumps(users, indent=2))

def get_user(users: dict, cid: int) -> dict:
    key = str(cid)
    if key not in users:
        users[key] = {
            "chat_id":   cid,
            "tier":      "free",
            "joined":    datetime.utcnow().isoformat(),
            "pro_until": None,
            "scan_mode": "full",
            "username":  "",
            "scans":     0,
        }
        save_users(users)
    return users[key]

def is_pro(user: dict) -> bool:
    if user["tier"] == "pro":
        if user["pro_until"] is None:
            return True
        expiry = datetime.fromisoformat(user["pro_until"])
        return datetime.utcnow() < expiry
    return False

def is_owner(cid: int) -> bool:
    return cid == OWNER_CHAT_ID


# ════════════════════════════════════════════════════════════════
#  TICKER LIST  (~900 liquid tickers)
# ════════════════════════════════════════════════════════════════
def get_stock_list():
    sp500 = [
        "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB",
        "AKAM","ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN",
        "AMCR","AEE","AAL","AEP","AXP","AIG","AMT","AWK","AMP","AME","AMGN",
        "APH","ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET",
        "AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
        "BAC","BK","BBWI","BAX","BDX","BRK-B","BBY","BIIB","BLK","BX","BA",
        "BSX","BMY","AVGO","BR","BRO","BLDR","BG","CDNS","CZR","CPT","CPB",
        "COF","CAH","KMX","CCL","CARR","CAT","CBOE","CBRE","CDW","CE","COR",
        "CNC","CDAY","CF","CRL","SCHW","CHTR","CVX","CMG","CB","CHD","CI",
        "CINF","CTAS","CSCO","C","CFG","CLX","CME","CMS","KO","CTSH","CL",
        "CMCSA","CAG","COP","ED","STZ","CEG","COO","CPRT","GLW","CPAY","CTVA",
        "CSGP","COST","CTRA","CCI","CSX","CMI","CVS","DHI","DHR","DRI","DVA",
        "DE","DAL","DVN","DXCM","FANG","DLR","DFS","DG","DLTR","D","DPZ",
        "DOV","DOW","DTE","DUK","DD","EMN","ETN","EBAY","ECL","EIX","EW",
        "EA","ELV","LLY","EMR","ENPH","ETR","EOG","EQT","EFX","EQIX","EQR",
        "ESS","EL","ETSY","EG","EVRG","ES","EXC","EXPE","EXPD","EXR","XOM",
        "FFIV","FDS","FICO","FAST","FRT","FDX","FIS","FITB","FSLR","FE","FI",
        "FLT","FMC","F","FTNT","FTV","FOXA","FOX","BEN","FCX","GRMN","IT",
        "GE","GEHC","GEN","GNRC","GD","GIS","GM","GPC","GILD","GPN","GL",
        "GDDY","GS","HAL","HIG","HAS","HCA","DOC","HSIC","HSY","HES","HPE",
        "HLT","HOLX","HD","HON","HRL","HST","HWM","HPQ","HUBB","HUM","HBAN",
        "HII","IBM","IEX","IDXX","ITW","INCY","IR","PODD","INTC","ICE","IFF",
        "IP","IPG","INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT","JBL","JKHY",
        "J","JNJ","JCI","JPM","JNPR","K","KVUE","KDP","KEY","KEYS","KMB",
        "KIM","KMI","KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS","LDOS",
        "LEN","LIN","LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MRO",
        "MPC","MKTX","MAR","MMC","MLM","MAS","MA","MTCH","MKC","MCD","MCK",
        "MDT","MRK","META","MET","MTD","MGM","MCHP","MU","MSFT","MAA","MRNA",
        "MHK","MOH","TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI",
        "NDAQ","NTAP","NWS","NWSA","NEE","NKE","NI","NDSN","NSC","NTRS","NOC",
        "NCLH","NRG","NUE","NVDA","NVR","NXPI","ORLY","OXY","ODFL","OMC","ON",
        "OKE","ORCL","OTIS","PCAR","PKG","PANW","PH","PAYX","PAYC","PYPL",
        "PNR","PEP","PFE","PCG","PM","PSX","PNW","PNC","POOL","PPG","PPL",
        "PFG","PG","PGR","PLD","PRU","PEG","PTC","PSA","PHM","PWR","QCOM",
        "DGX","RL","RJF","RTX","O","REG","REGN","RF","RSG","RMD","RVTY",
        "ROK","ROL","ROP","ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SRE",
        "NOW","SHW","SPG","SWKS","SJM","SNA","SO","LUV","SWK","SBUX","STT",
        "STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TTWO",
        "TPR","TRGP","TGT","TEL","TDY","TFX","TER","TSLA","TXN","TXT","TMO",
        "TJX","TSCO","TT","TDG","TRV","TRMB","TFC","TYL","TSN","USB","UBER",
        "UDR","ULTA","UNP","UAL","UPS","URI","UNH","UHS","VLO","VTR","VRSN",
        "VRSK","VZ","VRTX","VTRS","VICI","V","VST","VMC","WRB","GWW","WAB",
        "WBA","WMT","DIS","WBD","WM","WAT","WEC","WFC","WELL","WST","WDC",
        "WY","WHR","WMB","WTW","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
    ]
    nasdaq_extra = [
        "ASML","BIDU","BKNG","BMRN","MELI","MRVL","NFLX","NTES","OKTA",
        "PDD","SIRI","TEAM","WDAY","ZM","ZS","JD","ILMN",
    ]
    growth = [
        "SQ","COIN","HOOD","SOFI","PLTR","CRWD","DDOG","NET","SNOW","MDB",
        "HUBS","TWLO","DOCN","GTLB","CFLT","BRZE","BILL","APPN","LYFT","DASH",
        "SNAP","PINS","SPOT","RBLX","U","RIVN","NIO","XPEV","LI","CHPT",
        "BLNK","EVGO","PLUG","BABA","SE","GRAB","NU","NVO","BNTX","HIMS",
        "TDOC","DOCS","IBKR","AFRM","UPST","ACHR","JOBY","RKLB","LUNR","ASTS",
        "MARA","RIOT","CLSK","HUT","CORZ","DELL","PSTG","AMKR","COHU","ONTO",
        "MKSI","KLIC","ICHR","AI","BBAI","SOUN","IONQ","RGTI","QUBT","QBTS",
    ]
    etfs = [
        "SPY","QQQ","IWM","DIA","MDY","IJR","IVV","VOO","VTI","VEA",
        "SMH","SOXX","XLK","XLF","XLE","XLV","XLI","XLB","XLU","XLP",
        "ARKK","ARKG","ARKW","ARKF","GLD","SLV","GDX","GDXJ","TLT","IEF",
        "SOXL","SOXS","TQQQ","SQQQ","UPRO","SPXU","LABU","LABD",
    ]
    all_tickers = sorted(set(sp500 + nasdaq_extra + growth + etfs))
    logger.info(f"Ticker universe: {len(all_tickers)}")
    return all_tickers


# ════════════════════════════════════════════════════════════════
#  DATA FETCHING  (retry + validation)
# ════════════════════════════════════════════════════════════════
def safe_history(ticker_obj, period, interval, min_bars, retries=2):
    for attempt in range(retries + 1):
        try:
            df = ticker_obj.history(period=period, interval=interval,
                                    auto_adjust=True)
            if df is None or df.empty:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return None
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col not in df.columns:
                    return None
            df = df.dropna(subset=["Close"])
            return df if len(df) >= min_bars else None
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
            else:
                logger.debug(f"safe_history {interval}: {e}")
    return None

def build_4h(df_1h):
    if df_1h is None or len(df_1h) < 20:
        return None
    try:
        df_4h = df_1h.resample("4h").agg({
            "Open": "first", "High": "max",
            "Low": "min", "Close": "last", "Volume": "sum",
        }).dropna(subset=["Close"])
        return df_4h if len(df_4h) >= 30 else None
    except Exception:
        return None

def fetch_all_timeframes(symbol: str):
    try:
        t     = yf.Ticker(symbol)
        df_1h = safe_history(t, "60d",  "1h",  48, retries=2)
        df_1d = safe_history(t, "2y",   "1d",  100, retries=2)
        df_1w = safe_history(t, "5y",   "1wk", 52, retries=2)
        df_1m = safe_history(t, "10y",  "1mo", 24, retries=2)
        df_4h = build_4h(df_1h)
        if any(x is None for x in [df_4h, df_1d, df_1w, df_1m]):
            return None
        return {"4h": df_4h, "1d": df_1d, "1wk": df_1w, "1mo": df_1m}
    except Exception as e:
        logger.debug(f"fetch_all {symbol}: {e}")
        return None


# ════════════════════════════════════════════════════════════════
#  INDICATORS
# ════════════════════════════════════════════════════════════════
def ema_s(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()

def macd_calc(close):
    m   = ema_s(close, 12) - ema_s(close, 26)
    sig = ema_s(m, 9)
    return m, sig, m - sig

def rsi_calc(close, p=14):
    d    = close.diff()
    gain = d.clip(lower=0).rolling(p).mean()
    loss = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - 100 / (1 + gain / (loss + 1e-9))

def atr_calc(high, low, close, p=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def emas_all(close):
    return {n: ema_s(close, p) for n, p in
            [("e9", 9), ("e21", 21), ("e50", 50), ("e100", 100), ("e200", 200)]}

def vol_ratio(volume, p=20):
    avg = volume.rolling(p).mean().iloc[-1]
    return round(volume.iloc[-1] / (avg + 1e-9), 2)

def rs_spy(close, spy_close, bars=50):
    if len(close) < bars or len(spy_close) < bars:
        return 1.0
    return round(
        (close.iloc[-1] / close.iloc[-bars]) /
        (spy_close.iloc[-1] / spy_close.iloc[-bars] + 1e-9), 2
    )


# ════════════════════════════════════════════════════════════════
#  SIGNAL LOGIC  (two consecutive bars of expansion = confirmed)
# ════════════════════════════════════════════════════════════════
def macd_bull(macd, sig, hist):
    if len(hist) < 4:
        return False
    return (
        macd.iloc[-1] > sig.iloc[-1] and
        hist.iloc[-1] > 0 and
        hist.iloc[-1] > hist.iloc[-2] and
        hist.iloc[-2] > hist.iloc[-3]
    )

def macd_bear(macd, sig, hist):
    if len(hist) < 4:
        return False
    return (
        macd.iloc[-1] < sig.iloc[-1] and
        hist.iloc[-1] < 0 and
        hist.iloc[-1] < hist.iloc[-2] and
        hist.iloc[-2] < hist.iloc[-3]
    )

def ema_bull_stack(close, e):
    p = close.iloc[-1]
    return (
        p > e["e9"].iloc[-1] > e["e21"].iloc[-1] > e["e50"].iloc[-1] and
        p > e["e200"].iloc[-1] and
        e["e9"].iloc[-1]  > e["e9"].iloc[-5] and
        e["e21"].iloc[-1] > e["e21"].iloc[-5]
    )

def ema_bear_stack(close, e):
    p = close.iloc[-1]
    return (
        p < e["e9"].iloc[-1] < e["e21"].iloc[-1] < e["e50"].iloc[-1] and
        p < e["e200"].iloc[-1] and
        e["e9"].iloc[-1]  < e["e9"].iloc[-5] and
        e["e21"].iloc[-1] < e["e21"].iloc[-5]
    )

def not_extended_bull(close, e, pct=8.0):
    p = close.iloc[-1]
    e21 = e["e21"].iloc[-1]
    return 0 <= (p - e21) / e21 * 100 < pct

def not_extended_bear(close, e, pct=8.0):
    p = close.iloc[-1]
    e21 = e["e21"].iloc[-1]
    return 0 <= (e21 - p) / e21 * 100 < pct

def near_ema(close, e, pct=3.0):
    p = close.iloc[-1]
    if abs(p - e["e21"].iloc[-1]) / e["e21"].iloc[-1] * 100 < pct:
        return "EMA21"
    if abs(p - e["e50"].iloc[-1]) / e["e50"].iloc[-1] * 100 < pct:
        return "EMA50"
    return None

def div_bull(close, macd_line, lb=12):
    if len(close) < lb + 2:
        return False
    return (close.iloc[-1] < close.iloc[-lb:-1].min() and
            macd_line.iloc[-1] > macd_line.iloc[-lb:-1].min())

def div_bear(close, macd_line, lb=12):
    if len(close) < lb + 2:
        return False
    return (close.iloc[-1] > close.iloc[-lb:-1].max() and
            macd_line.iloc[-1] < macd_line.iloc[-lb:-1].max())


# ════════════════════════════════════════════════════════════════
#  SL / TP
# ════════════════════════════════════════════════════════════════
def sl_tp_bull(price, e, atr_val):
    e50  = e["e50"].iloc[-1]
    sl   = round(min(e50 * 0.993, price - 1.5 * atr_val), 2)
    risk = price - sl
    if risk <= 0:
        return None, None, None, 0
    tp1 = round(price + 1.5 * risk, 2)
    tp2 = round(price + 3.0 * risk, 2)
    rr  = round((tp1 - price) / risk, 2)
    return sl, tp1, tp2, rr

def sl_tp_bear(price, e, atr_val):
    e50  = e["e50"].iloc[-1]
    sl   = round(max(e50 * 1.007, price + 1.5 * atr_val), 2)
    risk = sl - price
    if risk <= 0:
        return None, None, None, 0
    tp1 = round(price - 1.5 * risk, 2)
    tp2 = round(price - 3.0 * risk, 2)
    rr  = round((price - tp1) / risk, 2)
    return sl, tp1, tp2, rr


# ════════════════════════════════════════════════════════════════
#  EARNINGS
# ════════════════════════════════════════════════════════════════
def days_to_earnings(symbol):
    try:
        cal = yf.Ticker(symbol).calendar
        if cal is not None and not cal.empty and "Earnings Date" in cal.index:
            for d in cal.loc["Earnings Date"]:
                if pd.notna(d):
                    days = (pd.Timestamp(d).date() - datetime.utcnow().date()).days
                    if days >= 0:
                        return days
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════════
#  ANALYSE ONE TIMEFRAME
# ════════════════════════════════════════════════════════════════
def analyse_tf(df):
    try:
        c  = df["Close"].dropna()
        h  = df["High"].dropna()
        lo = df["Low"].dropna()
        v  = df["Volume"].dropna()
        if len(c) < 60:
            return None
        m, sig, hist = macd_calc(c)
        e            = emas_all(c)
        atr_val      = atr_calc(h, lo, c).iloc[-1]
        vr           = vol_ratio(v)
        return {
            "macd_bull": macd_bull(m, sig, hist),
            "macd_bear": macd_bear(m, sig, hist),
            "macd_line": m,
            "ema_bull":  ema_bull_stack(c, e),
            "ema_bear":  ema_bear_stack(c, e),
            "no_ext_b":  not_extended_bull(c, e),
            "no_ext_s":  not_extended_bear(c, e),
            "near_ema":  near_ema(c, e),
            "rsi":       round(rsi_calc(c).iloc[-1], 1),
            "atr":       atr_val,
            "emas":      e,
            "close":     c,
            "vol_ratio": vr,
            "div_bull":  div_bull(c, m),
            "div_bear":  div_bear(c, m),
        }
    except Exception as ex:
        logger.debug(f"analyse_tf: {ex}")
        return None


# ════════════════════════════════════════════════════════════════
#  SCORE TICKER
# ════════════════════════════════════════════════════════════════
def score_ticker(symbol, spy_close=None, mode="full"):
    data = fetch_all_timeframes(symbol)
    if not data:
        return None

    tf4  = analyse_tf(data["4h"])
    tf1d = analyse_tf(data["1d"])
    tf1w = analyse_tf(data["1wk"])
    tf1m = analyse_tf(data["1mo"])

    if not all([tf4, tf1d, tf1w, tf1m]):
        return None

    price   = round(tf4["close"].iloc[-1], 2)
    atr_val = tf4["atr"]
    rs      = rs_spy(tf1d["close"], spy_close) if spy_close is not None else 1.0

    # ── LONG ──────────────────────────────────────────────────
    macd_3b = tf1d["macd_bull"] and tf1w["macd_bull"] and tf1m["macd_bull"]
    long_ok = macd_3b and tf4["no_ext_b"] and (
        mode == "macd_only" or tf4["ema_bull"]
    )

    if long_ok:
        sl, tp1, tp2, rr = sl_tp_bull(price, tf4["emas"], atr_val)
        if sl is None or rr < 1.5:
            return None
        earn = days_to_earnings(symbol)
        nema = tf4["near_ema"] or "—"
        score = sum([
            tf1d["macd_bull"] * 2,
            tf1w["macd_bull"] * 2,
            tf1m["macd_bull"] * 2,
            tf4["macd_bull"],
            tf4["ema_bull"] if mode == "full" else 0,
            nema != "—",
            tf4["vol_ratio"] > 1.3,
            tf1d["div_bull"],
            rs > 1.1,
        ])
        return dict(signal="BUY", ticker=symbol, price=price, score=score,
                    sl=sl, tp1=tp1, tp2=tp2, rr=rr, rsi=tf4["rsi"],
                    vol_ratio=tf4["vol_ratio"], rs=rs,
                    divergence=tf1d["div_bull"], near_ema=nema,
                    earn_days=earn, macd_4h=tf4["macd_bull"], mode=mode)

    # ── SHORT ─────────────────────────────────────────────────
    macd_3s  = tf1d["macd_bear"] and tf1w["macd_bear"] and tf1m["macd_bear"]
    short_ok = macd_3s and tf4["no_ext_s"] and (
        mode == "macd_only" or tf4["ema_bear"]
    )

    if short_ok:
        sl, tp1, tp2, rr = sl_tp_bear(price, tf4["emas"], atr_val)
        if sl is None or rr < 1.5:
            return None
        earn = days_to_earnings(symbol)
        nema = tf4["near_ema"] or "—"
        score = sum([
            tf1d["macd_bear"] * 2,
            tf1w["macd_bear"] * 2,
            tf1m["macd_bear"] * 2,
            tf4["macd_bear"],
            tf4["ema_bear"] if mode == "full" else 0,
            nema != "—",
            tf4["vol_ratio"] > 1.3,
            tf1d["div_bear"],
            rs < 0.9,
        ])
        return dict(signal="SHORT", ticker=symbol, price=price, score=score,
                    sl=sl, tp1=tp1, tp2=tp2, rr=rr, rsi=tf4["rsi"],
                    vol_ratio=tf4["vol_ratio"], rs=rs,
                    divergence=tf1d["div_bear"], near_ema=nema,
                    earn_days=earn, macd_4h=tf4["macd_bear"], mode=mode)

    return None


# ════════════════════════════════════════════════════════════════
#  FORMAT ALERT
# ════════════════════════════════════════════════════════════════
def format_alert(r: dict, is_free=False) -> str:
    buy   = r["signal"] == "BUY"
    emoji = "🟢" if buy else "🔴"
    dir_  = "LONG 📈" if buy else "SHORT 📉"

    sl_lbl  = "Stop Loss (below EMA50):" if buy else "Stop Loss (above EMA50):"
    tp1_lbl = "TP1 (1.5R above entry):"  if buy else "TP1 (1.5R below entry):"
    tp2_lbl = "TP2 (3.0R above entry):"  if buy else "TP2 (3.0R below entry):"

    rsi_note = (
        "oversold ✅"   if (buy  and r["rsi"] < 40) else
        "overbought ✅" if (not buy and r["rsi"] > 60) else
        "neutral"
    )
    vol_str = (
        "🔥 HIGH"    if r["vol_ratio"] > 1.5 else
        "✅ AVG+"   if r["vol_ratio"] > 1.1 else
        "🔵 Normal"
    )
    rs_str = (
        f"🚀 {r['rs']}x (outperforming)" if r["rs"] > 1.2 else
        f"✅ {r['rs']}x"                  if r["rs"] > 1.0 else
        f"⚠️ {r['rs']}x (underperforming)"
    )
    earn_str = ""
    if r["earn_days"] is not None:
        if r["earn_days"] <= 3:
            earn_str = f"\n🚨 *EARNINGS IN {r['earn_days']} DAYS — SKIP*"
        elif r["earn_days"] <= 7:
            earn_str = f"\n⚠️ Earnings in {r['earn_days']} days — caution"
        elif r["earn_days"] <= 14:
            earn_str = f"\n📅 Earnings in {r['earn_days']} days"

    mode_tag  = "MACD" if r["mode"] == "macd_only" else "Full"
    stars     = "⭐" * min(r["score"], 10)
    macd4h    = "✅ Yes" if r["macd_4h"] else "⏳ Pending"
    div_str   = "✅ YES" if r["divergence"] else "—"
    watermark = "\n\n🔒 _Upgrade to Pro — /upgrade_" if is_free else ""

    return (
        f"{emoji} *{r['ticker']}*  —  {dir_}   `[{mode_tag}]`\n"
        f"💰 Price: *${r['price']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *ENTRY:*  ${r['price']}\n"
        f"🛑 *{sl_lbl}*  ${r['sl']}\n"
        f"💵 *{tp1_lbl}*  ${r['tp1']}\n"
        f"🏆 *{tp2_lbl}*  ${r['tp2']}\n"
        f"📐 *R:R Ratio:*  1:{r['rr']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *INDICATORS (4H)*\n"
        f"• RSI: {r['rsi']}  ({rsi_note})\n"
        f"• Volume: {vol_str}  ({r['vol_ratio']}× avg)\n"
        f"• Near EMA: {r['near_ema']}\n"
        f"• 4H MACD: {macd4h}\n"
        f"• Divergence: {div_str}\n"
        f"• RS vs SPY: {rs_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Confidence:* {stars} ({r['score']}/10)"
        f"{earn_str}{watermark}\n"
    )


# ════════════════════════════════════════════════════════════════
#  SCAN + BROADCAST
# ════════════════════════════════════════════════════════════════
async def run_scan(app: Application):
    users = load_users()
    logger.info("Scan starting...")

    spy_close = None
    try:
        spy_close = yf.Ticker("SPY").history(
            period="1y", interval="1d")["Close"].dropna()
    except Exception:
        logger.warning("SPY fetch failed")

    tickers = get_stock_list()
    buys, shorts = [], []
    errors = 0

    for i, sym in enumerate(tickers):
        try:
            res = score_ticker(sym, spy_close, mode="full")
            if res:
                (buys if res["signal"] == "BUY" else shorts).append(res)
                logger.info(
                    f"{res['signal']}: {sym} score={res['score']} rr={res['rr']}")
        except Exception as e:
            errors += 1
            logger.debug(f"{sym}: {e}")
        if i > 0 and i % 50 == 0:
            await asyncio.sleep(2 + random.uniform(0, 1))

    buys.sort(  key=lambda x: (x["score"], x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    logger.info(
        f"Scan done — buys:{len(buys)} shorts:{len(shorts)} errors:{errors}")

    for uid, udata in users.items():
        try:
            await deliver_results(app.bot, udata, buys, shorts, len(tickers))
        except Exception as e:
            logger.warning(f"Deliver to {uid}: {e}")


async def deliver_results(bot, user, buys, shorts, total):
    cid     = user["chat_id"]
    pro     = is_pro(user)
    max_res = PRO_MAX if pro else FREE_MAX
    is_free = not pro

    if is_free:
        asyncio.get_event_loop().call_later(
            FREE_DELAY_H * 3600,
            lambda: asyncio.create_task(
                _send_report(bot, cid, buys, shorts, total,
                             max_res, is_free=True)
            )
        )
    else:
        await _send_report(bot, cid, buys, shorts, total, max_res, is_free=False)


async def _send_report(bot, cid, buys, shorts, total, max_res, is_free):
    et        = datetime.now(pytz.timezone("America/New_York"))
    tier_tag  = "FREE (delayed)" if is_free else "PRO ⭐"
    delay_note = f"\n_Signals delayed {FREE_DELAY_H}h (Free tier)_" if is_free else ""

    header = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *SWING SCANNER REPORT*\n"
        f"🕐 {et.strftime('%Y-%m-%d %H:%M ET')}\n"
        f"🏷 Tier: *{tier_tag}*\n"
        f"🔍 {total} stocks scanned\n"
        f"🟢 {len(buys[:max_res])} Longs  |  🔴 {len(shorts[:max_res])} Shorts\n"
        f"━━━━━━━━━━━━━━━━━━━━━━{delay_note}"
    )
    try:
        await bot.send_message(cid, header, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        return
    await asyncio.sleep(0.4)

    if buys[:max_res]:
        await bot.send_message(cid,
            f"🟢 *TOP LONG SETUPS*  ({len(buys[:max_res])} found)",
            parse_mode=ParseMode.MARKDOWN)
        for r in buys[:max_res]:
            try:
                await bot.send_message(cid, format_alert(r, is_free),
                                       parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Alert {r['ticker']}: {e}")
    else:
        await bot.send_message(cid, "🟢 No strong long setups this scan.")

    await asyncio.sleep(0.8)

    if shorts[:max_res]:
        await bot.send_message(cid,
            f"🔴 *TOP SHORT SETUPS*  ({len(shorts[:max_res])} found)",
            parse_mode=ParseMode.MARKDOWN)
        for r in shorts[:max_res]:
            try:
                await bot.send_message(cid, format_alert(r, is_free),
                                       parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Short {r['ticker']}: {e}")
    else:
        await bot.send_message(cid, "🔴 No strong short setups this scan.")

    if is_free:
        footer = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *FREE TIER LIMITS*\n"
            f"• {FREE_MAX} results max  |  {FREE_DELAY_H}h delay\n"
            "• No full indicator details\n\n"
            f"⭐ *PRO — {PRO_MONTHLY_PRICE}*\n"
            "• Real-time  |  20 results  |  Full details\n"
            "Type /upgrade to get access\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "_Not financial advice._"
        )
    else:
        footer = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 LONG: Entry → SL below EMA50 → TP1 (50%) → TP2 trail\n"
            "📋 SHORT: Entry → SL above EMA50 → TP1 (50%) → TP2 trail\n"
            "⚠️ Skip earnings <7 days  |  Always check the chart\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "_Not financial advice._"
        )
    await bot.send_message(cid, footer, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════
#  USER COMMANDS
# ════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    cid   = update.effective_chat.id
    user  = get_user(users, cid)
    user["username"] = update.effective_user.username or ""
    save_users(users)
    pro   = is_pro(user)
    tier  = "⭐ PRO" if pro else "🆓 FREE"

    await update.message.reply_text(
        f"🚀 *ULTIMATE SWING SCANNER*\n\n"
        f"Welcome! Tier: *{tier}*\n"
        f"Your ID: `{cid}`\n\n"
        f"*Commands:*\n"
        f"/scan — Run scan now\n"
        f"/setmode — MACD-only or Full\n"
        f"/status — Account & bot status\n"
        f"/upgrade — Get PRO access\n"
        f"/help — How to use signals\n\n"
        f"🔄 Auto scan every 4 hours\n"
        f"{'✅ PRO: Real-time, 20 results' if pro else f'🔒 FREE: {FREE_DELAY_H}h delay, {FREE_MAX} results'}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    cid   = update.effective_chat.id
    user  = get_user(users, cid)
    if is_pro(user):
        expiry = user.get("pro_until") or "Lifetime"
        await update.message.reply_text(
            f"✅ You already have *PRO* access!\nExpires: *{expiry}*",
            parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(
        f"⭐ *UPGRADE TO PRO — {PRO_MONTHLY_PRICE}*\n\n"
        f"✅ Real-time signals (no delay)\n"
        f"✅ Up to {PRO_MAX} results per scan\n"
        f"✅ Full indicator details\n"
        f"✅ Volume + RS + Divergence\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{PRO_PAYMENT_INFO}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Your ID: `{cid}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users  = load_users()
    cid    = update.effective_chat.id
    user   = get_user(users, cid)
    pro    = is_pro(user)
    et     = datetime.now(pytz.timezone("America/New_York"))
    market = "🟢 OPEN" if (et.weekday() < 5 and 6 <= et.hour <= 20) else "🔴 CLOSED"
    mode   = user.get("scan_mode", "full")

    await update.message.reply_text(
        f"📡 *SCANNER STATUS*\n\n"
        f"👤 Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"{'📅 Pro until: ' + (user.get('pro_until') or 'Lifetime') if pro else ''}\n"
        f"⏰ NY Time: {et.strftime('%H:%M ET')}\n"
        f"🏛 Market: {market}\n"
        f"📊 Mode: {'MACD Only' if mode == 'macd_only' else 'Full Strategy'}\n\n"
        f"Max results: {'20' if pro else str(FREE_MAX)}\n"
        f"Signal delay: {'None ✅' if pro else str(FREE_DELAY_H)+'h'}\n"
        f"Full details: {'✅' if pro else '❌'}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    cid   = update.effective_chat.id
    user  = get_user(users, cid)
    mode  = user.get("scan_mode", "full")
    cur   = "MACD Only" if mode == "macd_only" else "Full Strategy"
    kb = [[
        InlineKeyboardButton("📡 MACD Only",     callback_data="mode_macd_only"),
        InlineKeyboardButton("🔬 Full Strategy", callback_data="mode_full"),
    ]]
    await update.message.reply_text(
        f"*Scan Mode*  (current: *{cur}*)\n\n"
        f"📡 *MACD Only* — All 3 TF MACD aligned\n"
        f"More signals, quicker confirmation\n\n"
        f"🔬 *Full Strategy* — MACD + 4H EMA stack\n"
        f"Fewer but higher-quality setups",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def callback_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users    = load_users()
    cid      = query.from_user.id
    user     = get_user(users, cid)
    new_mode = "macd_only" if query.data == "mode_macd_only" else "full"
    user["scan_mode"] = new_mode
    save_users(users)
    label = "📡 MACD Only" if new_mode == "macd_only" else "🔬 Full Strategy"
    await query.edit_message_text(
        f"✅ Mode set to *{label}*\n\nUse /scan to run manually.",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    cid   = update.effective_chat.id
    user  = get_user(users, cid)
    mode  = user.get("scan_mode", "full")
    tickers = get_stock_list()

    await update.message.reply_text(
        f"🔍 Scan started!\n"
        f"Mode: {'MACD Only' if mode == 'macd_only' else 'Full Strategy'}\n"
        f"Checking {len(tickers)} stocks... ~15 mins",
        parse_mode=ParseMode.MARKDOWN
    )

    spy_close = None
    try:
        spy_close = yf.Ticker("SPY").history(
            period="1y", interval="1d")["Close"].dropna()
    except Exception:
        pass

    buys, shorts = [], []
    for i, sym in enumerate(tickers):
        try:
            res = score_ticker(sym, spy_close, mode=mode)
            if res:
                (buys if res["signal"] == "BUY" else shorts).append(res)
        except Exception:
            pass
        if i > 0 and i % 50 == 0:
            await asyncio.sleep(2)

    buys.sort(  key=lambda x: (x["score"], x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)

    pro     = is_pro(user)
    max_res = PRO_MAX if pro else FREE_MAX
    await _send_report(context.bot, cid, buys, shorts, len(tickers),
                       max_res, is_free=not pro)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *HOW TO USE SIGNALS*\n\n"
        "🟢 *LONG TRADES*\n"
        "• Entry → buy at price shown\n"
        "• Stop Loss → BELOW EMA50 (hard stop)\n"
        "• TP1 → close 50-60% of position\n"
        "• TP2 → move stop to breakeven, let run\n\n"
        "🔴 *SHORT TRADES*\n"
        "• Entry → short at price shown\n"
        "• Stop Loss → ABOVE EMA50 (hard stop)\n"
        "• TP1 → cover 50-60% of short\n"
        "• TP2 → trail stop, let it fall\n\n"
        "⚠️ *BEFORE EVERY TRADE:*\n"
        "• Check the chart yourself\n"
        "• Skip if earnings < 7 days\n"
        "• Never risk more than 2% per trade\n\n"
        "_Not financial advice._",
        parse_mode=ParseMode.MARKDOWN
    )


# ════════════════════════════════════════════════════════════════
#  ADMIN COMMANDS  (owner only)
# ════════════════════════════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id):
        return
    users  = load_users()
    total  = len(users)
    pro_ct = sum(1 for u in users.values() if is_pro(u))
    await update.message.reply_text(
        f"🔧 *ADMIN PANEL*\n\n"
        f"👥 Total users: {total}\n"
        f"⭐ PRO: {pro_ct}  |  🆓 FREE: {total - pro_ct}\n\n"
        f"/addpro <id> <days> — Grant PRO\n"
        f"/rmpro <id> — Remove PRO\n"
        f"/broadcast <msg> — Message all users\n"
        f"/userlist — List users",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_addpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addpro <user_id> <days>")
        return
    try:
        tid  = int(args[0])
        days = int(args[1])
    except ValueError:
        await update.message.reply_text("Invalid. Example: /addpro 123456 30")
        return
    users = load_users()
    user  = get_user(users, tid)
    user["tier"]      = "pro"
    user["pro_until"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
    save_users(users)
    await update.message.reply_text(
        f"✅ PRO granted to `{tid}` for {days} days.\n"
        f"Expires: {user['pro_until']}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await context.bot.send_message(
            tid,
            f"🎉 *Your account is now PRO!*\n"
            f"Valid for {days} days.\n"
            f"✅ Real-time signals  ✅ {PRO_MAX} results\n"
            f"Use /scan to run your first Pro scan!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

async def cmd_rmpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /rmpro <user_id>")
        return
    try:
        tid = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID.")
        return
    users = load_users()
    user  = get_user(users, tid)
    user["tier"] = "free"
    user["pro_until"] = None
    save_users(users)
    await update.message.reply_text(f"✅ PRO removed from `{tid}`.",
                                    parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg   = " ".join(context.args)
    users = load_users()
    sent, failed = 0, 0
    for uid, udata in users.items():
        try:
            await context.bot.send_message(
                udata["chat_id"],
                f"📢 *Announcement*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.1)
    await update.message.reply_text(
        f"Broadcast: {sent} sent, {failed} failed.")

async def cmd_userlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id):
        return
    users = load_users()
    lines = ["*USER LIST*\n"]
    for uid, u in list(users.items())[:50]:
        tier = "PRO" if is_pro(u) else "free"
        name = u.get("username") or "—"
        lines.append(f"`{uid}` | @{name} | {tier}")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════
#  SCHEDULED AUTO SCAN
# ════════════════════════════════════════════════════════════════
async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Scheduled scan triggered")
    await run_scan(context.application)


# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════
def main():
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError("Set TELEGRAM_TOKEN environment variable!")
    if OWNER_CHAT_ID == 0:
        raise ValueError("Set CHAT_ID environment variable!")

    logger.info("Starting Ultimate Swing Scanner v4.0...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("scan",    cmd_scan))
    app.add_handler(CommandHandler("setmode", cmd_setmode))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("upgrade", cmd_upgrade))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(callback_mode, pattern="^mode_"))

    # Admin commands
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("addpro",    cmd_addpro))
    app.add_handler(CommandHandler("rmpro",     cmd_rmpro))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("userlist",  cmd_userlist))

    app.job_queue.run_repeating(
        scheduled_scan,
        interval=SCAN_INTERVAL,
        first=120
    )

    logger.info("Bot polling started v4.0 ✅")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
