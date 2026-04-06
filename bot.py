"""
╔══════════════════════════════════════════════════════════════╗
║           ULTIMATE SWING SCANNER BOT v3.0                   ║
║  Strategy: MACD (D/W/M) + 4H EMA Stack + Filters           ║
║  Modes: MACD-Only or Full (MACD + EMA + Volume + RS)        ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import logging
import pandas as pd
import numpy as np
import yfinance as yf
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram import Update
from datetime import datetime
import pytz

# ── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHAT_ID        = os.environ.get("CHAT_ID", "YOUR_CHAT_ID_HERE")
SCAN_INTERVAL  = 4 * 60 * 60
MAX_RESULTS    = 15

# Scan mode: "macd_only" or "full"
# Changed by /setmode command — stored in memory
SCAN_MODE = {"mode": "full"}

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── MARKET HOURS ──────────────────────────────────────────────────────────────
def is_market_open():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    if now.weekday() >= 5:
        return False
    return 6 <= now.hour <= 20

# ── STOCK LIST ────────────────────────────────────────────────────────────────
def get_stock_list():
    tickers = [
        "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB",
        "AKAM","ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN",
        "AMCR","AEE","AAL","AEP","AXP","AIG","AMT","AWK","AMP","AME","AMGN",
        "APH","ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET",
        "AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
        "BAC","BK","BBWI","BAX","BDX","BRK-B","BBY","BIO","TECH","BIIB","BLK",
        "BX","BA","BSX","BMY","AVGO","BR","BRO","BLDR","BG","CDNS","CZR","CPT",
        "CPB","COF","CAH","KMX","CCL","CARR","CAT","CBOE","CBRE","CDW","CE",
        "COR","CNC","CNX","CDAY","CF","CRL","SCHW","CHTR","CVX","CMG","CB",
        "CHD","CI","CINF","CTAS","CSCO","C","CFG","CLX","CME","CMS","KO",
        "CTSH","CL","CMCSA","CAG","COP","ED","STZ","CEG","COO","CPRT","GLW",
        "CPAY","CTVA","CSGP","COST","CTRA","CCI","CSX","CMI","CVS","DHI","DHR",
        "DRI","DVA","DAY","DE","DAL","XRAY","DVN","DXCM","FANG","DLR","DFS",
        "DG","DLTR","D","DPZ","DOV","DOW","DTE","DUK","DD","EMN","ETN","EBAY",
        "ECL","EIX","EW","EA","ELV","LLY","EMR","ENPH","ETR","EOG","EPAM","EQT",
        "EFX","EQIX","EQR","ESS","EL","ETSY","EG","EVRG","ES","EXC","EXPE",
        "EXPD","EXR","XOM","FFIV","FDS","FICO","FAST","FRT","FDX","FIS","FITB",
        "FSLR","FE","FI","FLT","FMC","F","FTNT","FTV","FOXA","FOX","BEN","FCX",
        "GRMN","IT","GE","GEHC","GEV","GEN","GNRC","GD","GIS","GM","GPC","GILD",
        "GPN","GL","GDDY","GS","HAL","HIG","HAS","HCA","DOC","HSIC","HSY","HES",
        "HPE","HLT","HOLX","HD","HON","HRL","HST","HWM","HPQ","HUBB","HUM",
        "HBAN","HII","IBM","IEX","IDXX","ITW","INCY","IR","PODD","INTC","ICE",
        "IFF","IP","IPG","INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT","JBL",
        "JKHY","J","JNJ","JCI","JPM","JNPR","K","KVUE","KDP","KEY","KEYS",
        "KMB","KIM","KMI","KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS","LDOS",
        "LEN","LIN","LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MRO","MPC",
        "MKTX","MAR","MMC","MLM","MAS","MA","MTCH","MKC","MCD","MCK","MDT","MRK",
        "META","MET","MTD","MGM","MCHP","MU","MSFT","MAA","MRNA","MHK","MOH",
        "TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ","NTAP",
        "NWS","NWSA","NEE","NKE","NI","NDSN","NSC","NTRS","NOC","NCLH","NRG",
        "NUE","NVDA","NVR","NXPI","ORLY","OXY","ODFL","OMC","ON","OKE","ORCL",
        "OTIS","PCAR","PKG","PANW","PH","PAYX","PAYC","PYPL","PNR","PEP","PFE",
        "PCG","PM","PSX","PNW","PNC","POOL","PPG","PPL","PFG","PG","PGR","PLD",
        "PRU","PEG","PTC","PSA","PHM","QRVO","PWR","QCOM","DGX","RL","RJF","RTX",
        "O","REG","REGN","RF","RSG","RMD","RVTY","ROK","ROL","ROP","ROST","RCL",
        "SPGI","CRM","SBAC","SLB","STX","SRE","NOW","SHW","SPG","SWKS","SJM",
        "SNA","SOLV","SO","LUV","SWK","SBUX","STT","STLD","STE","SYK","SMCI",
        "SYF","SNPS","SYY","TMUS","TROW","TTWO","TPR","TRGP","TGT","TEL","TDY",
        "TFX","TER","TSLA","TXN","TXT","TMO","TJX","TSCO","TT","TDG","TRV",
        "TRMB","TFC","TYL","TSN","USB","UBER","UDR","ULTA","UNP","UAL","UPS",
        "URI","UNH","UHS","VLO","VTR","VLTO","VRSN","VRSK","VZ","VRTX","VTRS",
        "VICI","V","VST","VMC","WRB","GWW","WAB","WBA","WMT","DIS","WBD","WM",
        "WAT","WEC","WFC","WELL","WST","WDC","WY","WHR","WMB","WTW","WYNN",
        "XEL","XYL","YUM","ZBRA","ZBH","ZTS",
        # NASDAQ 100 extras
        "ADSK","ALGN","ASML","BIDU","BIIB","BKNG","BMRN","CDNS","CMCSA","CPRT",
        "CSGP","DLTR","DXCM","ENPH","EQIX","FAST","FTNT","GILD","IDXX","ILMN",
        "INCY","ISRG","JD","KLAC","LRCX","MCHP","MDLZ","MELI","MNST","MRNA",
        "MRVL","NFLX","NTES","NXPI","OKTA","PAYX","PCAR","PDD","QCOM","REGN",
        "ROST","SIRI","SNPS","TEAM","TXN","VRSK","VRSN","VRTX","WDAY","ZM","ZS",
        # Growth / momentum
        "SQ","COIN","HOOD","SOFI","PLTR","CRWD","DDOG","NET","SNOW","MDB",
        "HUBS","TWLO","DOCN","GTLB","CFLT","BRZE","BILL","APPN","LYFT","DASH",
        "SNAP","PINS","SPOT","RBLX","U","RIVN","LCID","NIO","XPEV","LI",
        "CHPT","BLNK","EVGO","PLUG","FCEL","BABA","SE","GRAB","NU","VIPS",
        "NVO","BNTX","HIMS","TDOC","DOCS","IBKR","AFRM","UPST","ACHR","JOBY",
        "RKLB","LUNR","ASTS","MARA","RIOT","CLSK","HUT","CORZ","DELL","PSTG",
        "AMKR","COHU","ONTO","MKSI","KLIC","ICHR","FORM","AOSL","DIOD",
        "AI","BBAI","SOUN","IONQ","RGTI","QUBT","QBTS",
        # ETFs
        "SPY","QQQ","IWM","DIA","MDY","IJR","IVV","VOO","VTI","VEA",
        "SMH","SOXX","XLK","XLF","XLE","XLV","XLI","XLB","XLU","XLP",
        "ARKK","ARKG","ARKW","ARKF","GLD","SLV","GDX","GDXJ","TLT","IEF",
        "SOXL","SOXS","TQQQ","SQQQ","UPRO","SPXU","LABU","LABD",
    ]
    result = sorted(set(tickers))
    logger.info(f"Total tickers to scan: {len(result)}")
    return result

# ── EARNINGS CHECK ────────────────────────────────────────────────────────────
def days_to_earnings(ticker: str):
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is not None and not cal.empty:
            dates = cal.loc["Earnings Date"] if "Earnings Date" in cal.index else None
            if dates is not None:
                for d in dates:
                    if pd.notna(d):
                        days = (pd.Timestamp(d).date() - datetime.now().date()).days
                        if days >= 0:
                            return days
    except Exception:
        pass
    return None

# ── INDICATORS ────────────────────────────────────────────────────────────────
def ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()

def compute_macd(close):
    m   = ema(close, 12) - ema(close, 26)
    sig = ema(m, 9)
    return m, sig, m - sig

def compute_rsi(close, period=14):
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

def compute_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_volume_ratio(volume, period=20):
    avg = volume.rolling(period).mean()
    return volume.iloc[-1] / (avg.iloc[-1] + 1e-10)

def compute_emas(close):
    return {k: ema(close, v) for k, v in
            [("e9",9),("e21",21),("e50",50),("e100",100),("e200",200)]}

def relative_strength(close, spy_close):
    if len(close) < 50 or len(spy_close) < 50:
        return 1.0
    stock_ret = close.iloc[-1] / close.iloc[-50]
    spy_ret   = spy_close.iloc[-1] / spy_close.iloc[-50]
    return round(stock_ret / (spy_ret + 1e-10), 2)

# ── MACD SIGNALS ──────────────────────────────────────────────────────────────
def macd_bull(macd, sig, hist):
    if len(hist) < 3:
        return False
    # Bullish: MACD line above signal, histogram positive and growing
    return (macd.iloc[-1] > sig.iloc[-1] and
            hist.iloc[-1] > 0 and
            hist.iloc[-1] > hist.iloc[-2])

def macd_bear(macd, sig, hist):
    if len(hist) < 3:
        return False
    # Bearish: MACD line BELOW signal, histogram NEGATIVE and FALLING (more negative)
    return (macd.iloc[-1] < sig.iloc[-1] and
            hist.iloc[-1] < 0 and
            hist.iloc[-1] < hist.iloc[-2])

# ── EMA STACK CHECKS ─────────────────────────────────────────────────────────
def ema_bull_stack(close, emas):
    """LONG: price > EMA9 > EMA21 > EMA50, all sloping up, above EMA200."""
    p    = close.iloc[-1]
    e9   = emas["e9"].iloc[-1]
    e21  = emas["e21"].iloc[-1]
    e50  = emas["e50"].iloc[-1]
    e200 = emas["e200"].iloc[-1]
    stack   = p > e9 > e21 > e50
    above   = p > e200
    slope9  = emas["e9"].iloc[-1]  > emas["e9"].iloc[-4]
    slope21 = emas["e21"].iloc[-1] > emas["e21"].iloc[-4]
    return stack and above and slope9 and slope21

def ema_bear_stack(close, emas):
    """SHORT: price < EMA9 < EMA21 < EMA50, all sloping DOWN, below EMA200."""
    p    = close.iloc[-1]
    e9   = emas["e9"].iloc[-1]
    e21  = emas["e21"].iloc[-1]
    e50  = emas["e50"].iloc[-1]
    e200 = emas["e200"].iloc[-1]
    # Fully inverted stack for shorts
    stack   = p < e9 < e21 < e50
    below   = p < e200
    slope9  = emas["e9"].iloc[-1]  < emas["e9"].iloc[-4]
    slope21 = emas["e21"].iloc[-1] < emas["e21"].iloc[-4]
    return stack and below and slope9 and slope21

def not_overextended_bull(close, emas, threshold=7.0):
    """LONG: price not too far above EMA21 (no chasing pumps)."""
    p   = close.iloc[-1]
    e21 = emas["e21"].iloc[-1]
    return (p - e21) / e21 * 100 < threshold

def not_overextended_bear(close, emas, threshold=7.0):
    """SHORT: price not too far below EMA21 (no chasing drops)."""
    p   = close.iloc[-1]
    e21 = emas["e21"].iloc[-1]
    return (e21 - p) / e21 * 100 < threshold

def near_ema_support_bull(close, emas):
    """Price pulling back UP to EMA21/50 = buy zone."""
    p   = close.iloc[-1]
    e21 = emas["e21"].iloc[-1]
    e50 = emas["e50"].iloc[-1]
    return abs(p - e21) / e21 * 100 < 2.5, abs(p - e50) / e50 * 100 < 2.5

def near_ema_resistance_bear(close, emas):
    """Price bouncing DOWN from EMA21/50 (from below) = short zone."""
    p   = close.iloc[-1]
    e21 = emas["e21"].iloc[-1]
    e50 = emas["e50"].iloc[-1]
    return abs(p - e21) / e21 * 100 < 2.5, abs(p - e50) / e50 * 100 < 2.5

# ── SL / TP CALC ──────────────────────────────────────────────────────────────
def compute_sl_tp_bull(close, emas, atr=None):
    """LONG: stop below EMA50, TP1 at 1.5R, TP2 at 3R."""
    price   = close.iloc[-1]
    e50     = emas["e50"].iloc[-1]
    atr_val = atr.iloc[-1] if atr is not None else price * 0.02
    sl      = round(min(e50 * 0.995, price - 1.5 * atr_val), 2)
    risk    = price - sl
    if risk <= 0:
        return None, None, None, 0
    tp1 = round(price + 1.5 * risk, 2)
    tp2 = round(price + 3.0 * risk, 2)
    rr  = round((tp1 - price) / risk, 2)
    return sl, tp1, tp2, rr

def compute_sl_tp_bear(close, emas, atr=None):
    """SHORT: stop ABOVE EMA50, TP1 at 1.5R DOWN, TP2 at 3R DOWN."""
    price   = close.iloc[-1]
    e50     = emas["e50"].iloc[-1]
    atr_val = atr.iloc[-1] if atr is not None else price * 0.02
    # Stop is ABOVE price for shorts
    sl      = round(max(e50 * 1.005, price + 1.5 * atr_val), 2)
    risk    = sl - price
    if risk <= 0:
        return None, None, None, 0
    # Targets are BELOW price for shorts
    tp1 = round(price - 1.5 * risk, 2)
    tp2 = round(price - 3.0 * risk, 2)
    rr  = round((price - tp1) / risk, 2)
    return sl, tp1, tp2, rr

def detect_bull_divergence(close, macd, lookback=10):
    if len(close) < lookback + 2:
        return False
    price_ll = close.iloc[-1] < close.iloc[-lookback:-1].min()
    macd_hl  = macd.iloc[-1]  > macd.iloc[-lookback:-1].min()
    return price_ll and macd_hl

def detect_bear_divergence(close, macd, lookback=10):
    if len(close) < lookback + 2:
        return False
    price_hh = close.iloc[-1] > close.iloc[-lookback:-1].max()
    macd_lh  = macd.iloc[-1]  < macd.iloc[-lookback:-1].max()
    return price_hh and macd_lh

# ── TIMEFRAME ANALYSIS ────────────────────────────────────────────────────────
def analyze_tf(df):
    if df is None or len(df) < 60:
        return None
    try:
        close = df["Close"].dropna()
        high  = df["High"].dropna()
        low   = df["Low"].dropna()
        vol   = df["Volume"].dropna() if "Volume" in df.columns else None
        if len(close) < 55:
            return None
        m, sig, hist = compute_macd(close)
        emas_        = compute_emas(close)
        rsi_         = compute_rsi(close)
        atr_         = compute_atr(high, low, close)
        vol_ratio    = compute_volume_ratio(vol) if vol is not None else 1.0
        return {
            "macd_bull":      macd_bull(m, sig, hist),
            "macd_bear":      macd_bear(m, sig, hist),
            "macd_line":      round(m.iloc[-1], 4),
            "macd_hist":      round(hist.iloc[-1], 4),
            "macd_series":    m,
            "ema_bull":       ema_bull_stack(close, emas_),
            "ema_bear":       ema_bear_stack(close, emas_),
            "not_ext_bull":   not_overextended_bull(close, emas_),
            "not_ext_bear":   not_overextended_bear(close, emas_),
            "near_sup":       near_ema_support_bull(close, emas_),
            "near_res":       near_ema_resistance_bear(close, emas_),
            "rsi":            round(rsi_.iloc[-1], 1),
            "atr":            atr_,
            "emas":           emas_,
            "close":          close,
            "vol_ratio":      round(vol_ratio, 2),
            "div_bull":       detect_bull_divergence(close, m),
            "div_bear":       detect_bear_divergence(close, m),
        }
    except Exception as e:
        logger.debug(f"analyze_tf error: {e}")
        return None

# ── FETCH ALL TIMEFRAMES ──────────────────────────────────────────────────────
def fetch_all(ticker: str, spy_close=None):
    try:
        t    = yf.Ticker(ticker)
        data = {}
        h1   = t.history(period="60d", interval="1h")
        if h1 is not None and len(h1) > 30:
            h4 = h1.resample("4h").agg({
                "Open":"first","High":"max","Low":"min",
                "Close":"last","Volume":"sum"
            }).dropna()
            data["4h"] = h4
        d1 = t.history(period="2y",  interval="1d")
        wk = t.history(period="5y",  interval="1wk")
        mo = t.history(period="10y", interval="1mo")
        if d1 is not None and len(d1) > 60:  data["1d"]  = d1
        if wk is not None and len(wk) > 50:  data["1wk"] = wk
        if mo is not None and len(mo) > 24:  data["1mo"] = mo
        if len(data) < 4:
            return None
        rs = 1.0
        if spy_close is not None and "1d" in data:
            rs = relative_strength(data["1d"]["Close"], spy_close)
        data["rs"] = rs
        return data
    except Exception as e:
        logger.debug(f"fetch_all {ticker}: {e}")
        return None

# ── SCORE TICKER ──────────────────────────────────────────────────────────────
def score_ticker(ticker: str, spy_close=None, mode="full"):
    data = fetch_all(ticker, spy_close)
    if not data:
        return None

    tf4  = analyze_tf(data.get("4h"))
    tf1d = analyze_tf(data.get("1d"))
    tf1w = analyze_tf(data.get("1wk"))
    tf1m = analyze_tf(data.get("1mo"))
    rs   = data.get("rs", 1.0)

    if not all([tf4, tf1d, tf1w, tf1m]):
        return None

    h4df  = data.get("4h")
    price = round(tf4["close"].iloc[-1], 2)

    # ═══════════════════════════════════════════
    #  STRONG BUY (LONG)
    # ═══════════════════════════════════════════
    macd_3tf_bull = tf1d["macd_bull"] and tf1w["macd_bull"] and tf1m["macd_bull"]

    if mode == "macd_only":
        # MACD-only mode: just need all 3 TF bullish + not overextended
        if macd_3tf_bull and tf4["not_ext_bull"]:
            sl, tp1, tp2, rr = compute_sl_tp_bull(tf4["close"], tf4["emas"], tf4["atr"])
            if sl is None or rr < 1.5:
                return None
            earn_days = days_to_earnings(ticker)
            score = sum([
                tf1d["macd_bull"],
                tf1w["macd_bull"],
                tf1m["macd_bull"],
                tf4["macd_bull"],          # bonus: 4H also confirms
                tf4["div_bull"],           # bonus: divergence
                rs > 1.1,
            ])
            return {
                "signal": "BUY", "ticker": ticker, "price": price,
                "score": score, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
                "rsi": tf4["rsi"], "vol_ratio": tf4["vol_ratio"], "rs": rs,
                "divergence": tf4["div_bull"], "near_ema": "—",
                "earn_days": earn_days, "macd_4h": tf4["macd_bull"],
                "mode": "MACD Only"
            }

    else:
        # Full mode: MACD all 3 TF + 4H EMA bull stack + not overextended
        if (macd_3tf_bull and tf4["ema_bull"] and tf4["not_ext_bull"]):
            sl, tp1, tp2, rr = compute_sl_tp_bull(tf4["close"], tf4["emas"], tf4["atr"])
            if sl is None or rr < 1.5:
                return None
            earn_days = days_to_earnings(ticker)
            near21, near50 = tf4["near_sup"]
            score = sum([
                macd_3tf_bull * 3,
                tf4["ema_bull"] * 2,
                near21 or near50,
                tf4["vol_ratio"] > 1.3,
                tf1d["div_bull"],
                rs > 1.1,
            ])
            return {
                "signal": "BUY", "ticker": ticker, "price": price,
                "score": score, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
                "rsi": tf4["rsi"], "vol_ratio": tf4["vol_ratio"], "rs": rs,
                "divergence": tf1d["div_bull"],
                "near_ema": "EMA21" if near21 else ("EMA50" if near50 else "—"),
                "earn_days": earn_days, "macd_4h": tf4["macd_bull"],
                "mode": "Full"
            }

    # ═══════════════════════════════════════════
    #  STRONG SHORT
    # ═══════════════════════════════════════════
    macd_3tf_bear = tf1d["macd_bear"] and tf1w["macd_bear"] and tf1m["macd_bear"]

    if mode == "macd_only":
        if macd_3tf_bear and tf4["not_ext_bear"]:
            sl, tp1, tp2, rr = compute_sl_tp_bear(tf4["close"], tf4["emas"], tf4["atr"])
            if sl is None or rr < 1.5:
                return None
            earn_days = days_to_earnings(ticker)
            score = sum([
                tf1d["macd_bear"],
                tf1w["macd_bear"],
                tf1m["macd_bear"],
                tf4["macd_bear"],
                tf4["div_bear"],
                rs < 0.9,
            ])
            return {
                "signal": "SHORT", "ticker": ticker, "price": price,
                "score": score, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
                "rsi": tf4["rsi"], "vol_ratio": tf4["vol_ratio"], "rs": rs,
                "divergence": tf4["div_bear"], "near_ema": "—",
                "earn_days": earn_days, "macd_4h": tf4["macd_bear"],
                "mode": "MACD Only"
            }

    else:
        # Full mode shorts: MACD all 3 TF BEARISH + 4H EMA BEAR stack
        if (macd_3tf_bear and tf4["ema_bear"] and tf4["not_ext_bear"]):
            sl, tp1, tp2, rr = compute_sl_tp_bear(tf4["close"], tf4["emas"], tf4["atr"])
            if sl is None or rr < 1.5:
                return None
            earn_days = days_to_earnings(ticker)
            near21, near50 = tf4["near_res"]
            score = sum([
                macd_3tf_bear * 3,
                tf4["ema_bear"] * 2,
                near21 or near50,
                tf4["vol_ratio"] > 1.3,
                tf1d["div_bear"],
                rs < 0.9,
            ])
            return {
                "signal": "SHORT", "ticker": ticker, "price": price,
                "score": score, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
                "rsi": tf4["rsi"], "vol_ratio": tf4["vol_ratio"], "rs": rs,
                "divergence": tf1d["div_bear"],
                "near_ema": "EMA21" if near21 else ("EMA50" if near50 else "—"),
                "earn_days": earn_days, "macd_4h": tf4["macd_bear"],
                "mode": "Full"
            }

    return None

# ── FORMAT ALERT ──────────────────────────────────────────────────────────────
def format_alert(r: dict) -> str:
    is_buy = r["signal"] == "BUY"

    if is_buy:
        emoji      = "🟢"
        direction  = "LONG 📈"
        sl_label   = "🛑 STOP LOSS (below EMA50):"
        tp1_label  = "💵 TP1 (1.5R above entry):"
        tp2_label  = "🏆 TP2 (3R above entry):"
        rs_emoji   = "🚀" if r["rs"] > 1.2 else "✅"
        rsi_note   = "oversold ✅" if r["rsi"] < 40 else ("neutral" if r["rsi"] < 60 else "watch ⚠️")
    else:
        emoji      = "🔴"
        direction  = "SHORT 📉"
        sl_label   = "🛑 STOP LOSS (above EMA50):"   # stop is ABOVE for shorts
        tp1_label  = "💵 TP1 (1.5R below entry):"    # targets are BELOW
        tp2_label  = "🏆 TP2 (3R below entry):"
        rs_emoji   = "📉" if r["rs"] < 0.8 else "⚠️"
        rsi_note   = "overbought ✅" if r["rsi"] > 60 else ("neutral" if r["rsi"] > 40 else "watch ⚠️")

    stars     = "⭐" * min(r["score"], 10)
    vol_str   = ("🔥 HIGH" if r["vol_ratio"] > 1.5 else
                 "✅ AVG+" if r["vol_ratio"] > 1.1 else "🔵 Normal")
    div_str   = "✅ YES" if r["divergence"] else "—"
    rs_str    = f"{rs_emoji} {r['rs']}x SPY"
    macd4h    = "✅ Confirmed" if r["macd_4h"] else "⏳ Pending"
    mode_str  = f"[{r['mode']}]"

    earn_str = ""
    if r["earn_days"] is not None:
        if r["earn_days"] <= 7:
            earn_str = f"\n⚠️ *EARNINGS IN {r['earn_days']} DAYS — CAUTION*"
        elif r["earn_days"] <= 14:
            earn_str = f"\n📅 Earnings in {r['earn_days']} days"

    msg = (
        f"{emoji} *{r['ticker']}* — {direction}  _{mode_str}_\n"
        f"💰 Price: *${r['price']}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *ENTRY:* ${r['price']}\n"
        f"{sl_label} *${r['sl']}*\n"
        f"{tp1_label} *${r['tp1']}*\n"
        f"{tp2_label} *${r['tp2']}*\n"
        f"📐 *R:R Ratio:* 1:{r['rr']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *INDICATORS*\n"
        f"• RSI (4H): {r['rsi']} — {rsi_note}\n"
        f"• Volume: {vol_str} ({r['vol_ratio']}x avg)\n"
        f"• Near EMA: {r['near_ema']}\n"
        f"• 4H MACD: {macd4h}\n"
        f"• Divergence: {div_str}\n"
        f"• RS vs SPY: {rs_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Confidence:* {stars} ({r['score']}/10)"
        f"{earn_str}\n"
    )
    return msg

# ── MAIN SCAN ─────────────────────────────────────────────────────────────────
async def run_scan(bot: Bot, manual=False, mode=None):
    if mode is None:
        mode = SCAN_MODE["mode"]

    now_et = datetime.now(pytz.timezone("America/New_York"))
    mode_label = "📡 MACD-Only Mode" if mode == "macd_only" else "🔬 Full Strategy Mode"
    logger.info(f"Scan started [{mode}] at {now_et.strftime('%Y-%m-%d %H:%M ET')}")

    spy_close = None
    try:
        spy_data  = yf.Ticker("SPY").history(period="1y", interval="1d")
        spy_close = spy_data["Close"].dropna()
    except Exception:
        pass

    tickers = get_stock_list()
    buys, shorts = [], []
    errors = 0

    await bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"🔍 *Scan started* — {len(tickers)} stocks\n"
            f"{mode_label}\n"
            f"🕐 {now_et.strftime('%H:%M ET')} | Results in ~15 mins"
        ),
        parse_mode="Markdown"
    )

    for i, ticker in enumerate(tickers):
        try:
            result = score_ticker(ticker, spy_close, mode=mode)
            if result:
                if result["signal"] == "BUY":
                    buys.append(result)
                else:
                    shorts.append(result)
        except Exception as e:
            errors += 1
            logger.debug(f"Error {ticker}: {e}")
        if i % 100 == 0 and i > 0:
            await asyncio.sleep(3)

    buys.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    shorts.sort(key=lambda x: (x["score"], x["rr"]), reverse=True)
    await send_full_report(bot, buys, shorts, len(tickers), errors, mode)

# ── SEND REPORT ───────────────────────────────────────────────────────────────
async def send_full_report(bot, buys, shorts, total, errors, mode):
    now    = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M UTC")
    et     = datetime.now(pytz.timezone("America/New_York")).strftime("%H:%M ET")
    mlabel = "MACD-Only" if mode == "macd_only" else "Full Strategy"

    header = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *SWING SCANNER REPORT*\n"
        f"🕐 {now} ({et})\n"
        f"📡 Mode: *{mlabel}*\n"
        f"🔍 {total} stocks scanned\n"
        f"🟢 {len(buys)} Longs | 🔴 {len(shorts)} Shorts\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode="Markdown")
    await asyncio.sleep(0.5)

    if buys:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🟢 *TOP LONG SETUPS* ({len(buys)} found)",
            parse_mode="Markdown"
        )
        for r in buys[:MAX_RESULTS]:
            try:
                await bot.send_message(
                    chat_id=CHAT_ID, text=format_alert(r), parse_mode="Markdown"
                )
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Alert send failed {r['ticker']}: {e}")
    else:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🟢 No strong long setups this scan."
        )

    await asyncio.sleep(1)

    if shorts:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🔴 *TOP SHORT SETUPS* ({len(shorts)} found)",
            parse_mode="Markdown"
        )
        for r in shorts[:MAX_RESULTS]:
            try:
                await bot.send_message(
                    chat_id=CHAT_ID, text=format_alert(r), parse_mode="Markdown"
                )
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Short alert send failed {r['ticker']}: {e}")
    else:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🔴 No strong short setups this scan."
        )

    footer = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *HOW TO USE THESE ALERTS*\n"
        "🟢 *LONG trades:*\n"
        "  Entry → buy at price shown\n"
        "  SL → below EMA50 (hard stop)\n"
        "  TP1 → take 50-60% profit here\n"
        "  TP2 → trail stop, let rest run\n\n"
        "🔴 *SHORT trades:*\n"
        "  Entry → short at price shown\n"
        "  SL → above EMA50 (hard stop)\n"
        "  TP1 → cover 50-60% here\n"
        "  TP2 → trail stop, let rest run\n\n"
        "⚠️ SKIP earnings <7 days away\n"
        "Always glance at chart before entering\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ _Not financial advice._"
    )
    await bot.send_message(chat_id=CHAT_ID, text=footer, parse_mode="Markdown")

# ── BOT COMMANDS ──────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🚀 *ULTIMATE SWING SCANNER BOT v3*\n\n"
        f"Your Chat ID: `{cid}`\n\n"
        f"*Commands:*\n"
        f"/scan — Manual scan (current mode)\n"
        f"/setmode — Choose scan mode\n"
        f"/mode — See current mode\n"
        f"/status — Bot status\n"
        f"/help — How to use alerts\n\n"
        f"✅ Auto scan every 4 hours\n"
        f"📊 Strategy: MACD(D/W/M) + 4H EMA + Filters\n"
        f"🎯 Entry, SL, TP1, TP2, R:R calculated\n"
        f"📅 Earnings warnings included",
        parse_mode="Markdown"
    )

async def cmd_setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show mode selection buttons."""
    keyboard = [
        [
            InlineKeyboardButton("📡 MACD Only", callback_data="mode_macd_only"),
            InlineKeyboardButton("🔬 Full Strategy", callback_data="mode_full"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    current = "MACD Only" if SCAN_MODE["mode"] == "macd_only" else "Full Strategy"
    await update.message.reply_text(
        f"*Choose Scan Mode*\n\n"
        f"Current: *{current}*\n\n"
        f"📡 *MACD Only* — Faster, more signals\n"
        f"  Filters: MACD bullish/bearish on Daily + Weekly + Monthly\n"
        f"  Good for: seeing overall trend direction\n\n"
        f"🔬 *Full Strategy* — Stricter, higher quality\n"
        f"  Filters: MACD (D/W/M) + 4H EMA stack + Volume + RS\n"
        f"  Good for: high probability setups only",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def callback_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "mode_macd_only":
        SCAN_MODE["mode"] = "macd_only"
        label = "📡 MACD Only"
        desc  = "Faster scans, more signals. Filters: MACD bullish/bearish on D+W+M."
    else:
        SCAN_MODE["mode"] = "full"
        label = "🔬 Full Strategy"
        desc  = "Stricter, higher quality. Filters: MACD + 4H EMA stack + Volume + RS."
    await query.edit_message_text(
        f"✅ Mode set to *{label}*\n\n{desc}\n\n"
        f"Next auto scan will use this mode.\nUse /scan to run manually now.",
        parse_mode="Markdown"
    )

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = SCAN_MODE["mode"]
    label = "📡 MACD Only" if m == "macd_only" else "🔬 Full Strategy"
    await update.message.reply_text(
        f"Current scan mode: *{label}*\n\nUse /setmode to change it.",
        parse_mode="Markdown"
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    et     = datetime.now(pytz.timezone("America/New_York"))
    market = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
    m      = SCAN_MODE["mode"]
    mlabel = "📡 MACD Only" if m == "macd_only" else "🔬 Full Strategy"
    await update.message.reply_text(
        f"✅ *Bot is running*\n\n"
        f"📡 Mode: *{mlabel}*\n"
        f"🕐 NY Time: {et.strftime('%H:%M ET')}\n"
        f"🏛 Market: {market}\n"
        f"⏰ Auto scan: every 4 hours\n\n"
        f"*Filters active:*\n"
        f"• MACD D+W+M alignment\n"
        f"• Not overextended (no chasing)\n"
        f"• R:R minimum 1.5:1\n"
        f"• Earnings date warnings\n"
        f"{'• 4H EMA stack check' if m == 'full' else ''}\n"
        f"{'• Volume confirmation' if m == 'full' else ''}\n"
        f"{'• Relative strength vs SPY' if m == 'full' else ''}",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *HOW TO USE YOUR ALERTS*\n\n"
        "🟢 *LONG TRADES*\n"
        "• Entry: buy at or near the price shown\n"
        "• Stop Loss: set BELOW EMA50 — if price drops here, exit\n"
        "• TP1: close 50-60% of position here (locks profit)\n"
        "• TP2: move stop to breakeven, let rest run\n\n"
        "🔴 *SHORT TRADES*\n"
        "• Entry: short at or near the price shown\n"
        "• Stop Loss: set ABOVE EMA50 — if price rises here, exit\n"
        "• TP1: cover 50-60% of short position here\n"
        "• TP2: trail stop, let rest run down\n\n"
        "📐 *R:R RATIO*\n"
        "Only trades with 1:1.5+ sent. Higher = better.\n\n"
        "⚠️ *EARNINGS*\n"
        "Skip or reduce size if earnings <7 days away.\n\n"
        "🔥 *VOLUME*\n"
        "HIGH volume = strongest signal confirmation.\n\n"
        "📡 *MODES*\n"
        "Use /setmode to switch between MACD-Only and Full Strategy.",
        parse_mode="Markdown"
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = SCAN_MODE["mode"]
    label = "MACD Only" if m == "macd_only" else "Full Strategy"
    await update.message.reply_text(
        f"🔍 Manual scan started [{label}]...\nResults in ~15 mins"
    )
    await run_scan(context.bot, manual=True)

async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Scheduled scan triggered")
    await run_scan(context.bot)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError("Set TELEGRAM_TOKEN environment variable!")
    if CHAT_ID == "YOUR_CHAT_ID_HERE":
        raise ValueError("Set CHAT_ID environment variable!")

    logger.info("Starting Ultimate Swing Scanner Bot v3...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("scan",    cmd_scan))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("setmode", cmd_setmode))
    app.add_handler(CommandHandler("mode",    cmd_mode))
    app.add_handler(CallbackQueryHandler(callback_mode, pattern="^mode_"))

    app.job_queue.run_repeating(
        scheduled_scan,
        interval=SCAN_INTERVAL,
        first=90
    )

    logger.info("Bot polling started ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
