"""
╔══════════════════════════════════════════════════════════════════════╗
║              SWING SCANNER PRO  v7.0                               ║
║   MACD-ONLY strategy — Daily + Weekly + Monthly                    ║
║   Smart tiered signals: STRONG / CONFIRMED / DEVELOPING            ║
║   1200+ tickers | Per-user onboarding | Free vs Pro               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, asyncio, logging, json, time, random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
import pytz

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, ConversationHandler, MessageHandler, filters
)
from telegram.constants import ParseMode

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN")
OWNER_CHAT_ID   = int(os.environ.get("CHAT_ID", "0"))
OWNER_USERNAME  = os.environ.get("OWNER_USERNAME", "@YourUsername")
USDT_WALLET     = os.environ.get("USDT_WALLET",  "YOUR_USDT_TRC20")
BTC_WALLET      = os.environ.get("BTC_WALLET",   "YOUR_BTC_ADDRESS")
ETH_WALLET      = os.environ.get("ETH_WALLET",   "YOUR_ETH_ADDRESS")
SOL_WALLET      = os.environ.get("SOL_WALLET",   "YOUR_SOL_ADDRESS")
PRO_PRICE       = os.environ.get("PRO_PRICE",    "29")

SCAN_INTERVAL   = 4 * 60 * 60
FREE_MAX        = 3
PRO_MAX         = 30
BOT_NAME        = "Swing Scanner Pro"
DATA_FILE       = Path("/tmp/users.json")
ASK_NAME, ASK_EXP, ASK_DONE = range(3)

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

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
        db[key] = {"chat_id": cid, "tier": "free", "joined": datetime.utcnow().isoformat(),
                   "pro_until": None, "username": "", "name": "", "experience": "",
                   "onboarded": False, "scans": 0, "last_scan": None}
        save_db(db)
    return db[key]

def is_pro(u):
    if u.get("tier") != "pro": return False
    if u.get("pro_until") is None: return True
    try: return datetime.utcnow() < datetime.fromisoformat(u["pro_until"])
    except: return False

def is_owner(cid): return cid == OWNER_CHAT_ID

TICKERS = sorted(set([
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","LLY",
    "JPM","V","MA","UNH","XOM","JNJ","WMT","PG","HD","MRK","CVX","ABBV",
    "BAC","COST","KO","PEP","ADBE","CSCO","CRM","TMO","ACN","MCD","ABT",
    "DHR","LIN","TXN","NFLX","CMCSA","NKE","AMD","PM","UPS","MS","BMY",
    "RTX","INTU","SPGI","HON","AMGN","SBUX","LOW","GE","CAT","GS","BLK",
    "AMAT","ELV","ISRG","GILD","MDT","ADP","LRCX","SYK","REGN","VRTX",
    "ADI","PANW","KLAC","SNPS","CDNS","MCHP","NXPI","FTNT","CRWD","NOW",
    "MMM","AES","AIG","AMT","AMP","APH","ANSS","AON","APA","APTV","ANET",
    "T","ADSK","AZO","AVB","AXON","BKR","BALL","BK","BBWI","BAX","BDX",
    "BRK-B","BBY","BIIB","BX","BA","BSX","BG","CAH","KMX","CCL","CARR",
    "CBOE","CBRE","CDW","CE","COR","CNC","CF","CRL","SCHW","CHTR","CMG",
    "CB","CHD","CI","CINF","CTAS","C","CFG","CLX","CME","CMS","CTSH","CL",
    "CAG","COP","ED","STZ","CEG","COO","CPRT","GLW","CTVA","CSGP","CTRA",
    "CCI","CSX","CMI","CVS","DHI","DRI","DVA","DE","DAL","DVN","DXCM",
    "DLR","DFS","DG","DLTR","D","DPZ","DOW","DTE","DUK","DD","ETN","EBAY",
    "ECL","EIX","EW","EA","EMR","ENPH","EOG","EQT","EFX","EQIX","EQR",
    "ESS","EL","ETSY","EXC","EXPE","FDS","FICO","FAST","FDX","FIS","FITB",
    "FSLR","FI","FLT","F","FTV","FCX","GD","GIS","GM","GPC","GPN","GL",
    "GDDY","HAL","HIG","HCA","HSY","HES","HPE","HLT","HRL","HPQ","HUBB",
    "HUM","IBM","IDXX","ITW","INTC","ICE","IRM","JCI","K","KDP","KEY",
    "KMB","KMI","KHC","KR","LHX","LW","LVS","LEN","LMT","L","LULU","MTB",
    "MPC","MAR","MMC","MAS","MKC","MCK","MET","MGM","MU","MRNA","MCO",
    "MSI","MSCI","NDAQ","NEE","NSC","NOC","NCLH","ORLY","OXY","ODFL","ON",
    "OKE","ORCL","PCAR","PKG","PH","PAYX","PYPL","PSX","PNC","PPG","PGR",
    "PLD","PRU","PSA","PWR","QCOM","RTX","O","RSG","RMD","ROK","ROP",
    "ROST","SBAC","SLB","SRE","SHW","SPG","STT","STLD","STE","SYF","SYY",
    "TMUS","TROW","TGT","TJX","TSCO","TT","TDG","TRV","TFC","TSN","USB",
    "UNP","UAL","URI","VLO","VTR","VZ","VICI","WBA","WM","WAT","WFC",
    "WELL","WDC","WY","WMB","WYNN","XEL","YUM","ZBRA","ZBH","ZTS","AFL",
    "ALL","BEN","BIIB","BWA","CPB","CHRW","CINF","CMA","CNP","DOV","DXC",
    "EMN","EG","ES","EXPD","EXR","FFIV","FMC","FOXA","FOX","FRT","GEV",
    "GEHC","GNRC","GRMN","HAS","HEI","HII","HOLX","HWM","HBAN","IEX",
    "INCY","IR","IVZ","INVH","IQV","IT","JBHT","JKHY","J","KVUE","KIM",
    "LDOS","LKQ","LYB","LYV","MLM","MRO","MKTX","MOH","MOS","MPWR","MNST",
    "MDLZ","NI","NRG","NUE","NVR","NDSN","NTRS","NWS","NWSA","PCG","PFG",
    "PEG","PNR","PNW","POOL","PPL","PTC","PHM","QRVO","RL","RJF","RF",
    "RVTY","ROL","RCL","SNA","SO","LUV","SWK","STX","SJM","SOLV","SWKS",
    "TPR","TRGP","TEL","TDY","TFX","TER","TXT","TYL","UDR","ULTA","UHS",
    "VTRS","VST","WRB","GWW","WAB","WBD","WST","WHR","WTW","XYL","SMCI",
    "ARE","SBA","TSM","ARM","WDC","NTAP","PSTG","DELL","NET","DDOG","SNOW",
    "MDB","GTLB","CFLT","HUBS","TWLO","DOCN","BRZE","BILL","APPN","ZM",
    "ZS","OKTA","SNAP","PINS","RBLX","U","SHOP","SPOT","DASH","LYFT","UBER",
    "ABNB","EXPE","BKNG","VRSK","IBKR","MKTX","LPLA","AFRM","UPST","COIN",
    "HOOD","SOFI","PLTR","CRWD","PANW","S","AI","BBAI","SOUN","IONQ","MSTR",
    "RIOT","MARA","CLSK","HUT","CORZ","ACHR","JOBY","RKLB","LUNR","ASTS",
    "RIVN","LCID","NIO","XPEV","LI","PLUG","ENPH","CELH","HIMS","DOCS",
    "TDOC","GRAB","SE","BABA","JD","PDD","BIDU","NTES","TCOM","NU",
    "RXRX","ARWR","NTLA","BEAM","CRSP","INSM","SRPT","ALNY","BMRN","INCY",
    "EXAS","ACAD","NVAX","ONTO","AMKR","COHU","KLIC","WOLF","AEHR","MRVL",
    "SWKS","NXPI","ADI","MPWR","ENTG","AMBA","CLS","XOM","CVX","COP","SLB",
    "HAL","BKR","OXY","MPC","VLO","PSX","DVN","EOG","HES","MRO","APA",
    "EQT","RRC","SM","NOG","CTRA","SWN","AR","MTDR","FANG","MPLX","EPD",
    "ET","WMB","OKE","KMI","PAA","TRGP","LLY","NVO","MRNA","BNTX","ABBV",
    "PFE","AMGN","GILD","REGN","VRTX","BIIB","ILMN","HIMS","ALNY","SRPT",
    "JAZZ","ALKS","NBIX","ITCI","AXSM","CORT","PRGO","CTLT","AZN","NVS",
    "GSK","SNY","NEE","DUK","SO","D","AEP","EXC","XEL","ED","PCG","EIX",
    "PEG","ES","EVRG","NI","CMS","WEC","AEE","AMT","CCI","SBAC","EQIX",
    "DLR","IRM","PSA","EXR","EQR","AVB","CPT","MAA","UDR","NHI","VTR",
    "WELL","OHI","O","NNN","VICI","MGM","LVS","WYNN","FCX","NEM","GOLD",
    "AEM","WPM","PAAS","NUE","STLD","CLF","RS","CMC","LYB","CC","HUN",
    "RPM","ECL","IFF","NTR","CF","FMC","SQM","ALB","SPY","QQQ","IWM",
    "DIA","MDY","IJR","IVV","VOO","VTI","SMH","SOXX","XLK","XLF","XLE",
    "XLV","XLI","XLB","XLU","XLP","XLY","XLC","XLRE","XBI","IBB","ARKK",
    "ARKG","ARKW","GLD","SLV","GDX","GDXJ","IAU","TLT","IEF","SHY","BND",
    "AGG","LQD","HYG","JNK","EMB","SOXL","TQQQ","UPRO","SPXL","LABU",
    "NUGT","SOXS","SQQQ","SPXS","LABD","DUST","VNQ","XLRE","OIH","XOP",
    "ICLN","QCLN","PBW","BOTZ","ROBO","AIQ","WCLD","BUG","CIBR","HACK",
    "BA","LMT","NOC","GD","LHX","HII","TDG","CAT","DE","PCAR","UPS",
    "FDX","XPO","CHRW","ODFL","SAIA","WERN","KNX","GE","HON","MMM","EMR",
    "ROK","ITW","PH","DOV","IR","TT","OTIS","T","VZ","TMUS","DIS","PARA",
    "WBD","FOXA","FOX","AMC","CNK","IMAX","TTWO","EA","ATVI","RBLX",
    "GS","JPM","BAC","C","WFC","MS","BLK","SCHW","AXP","COF","DFS","SYF",
    "AIG","MET","PRU","AFL","TRV","CB","HIG","LNC","UNM","RE","MFC",
]))

TICKERS = sorted(set(t for t in TICKERS if t.replace("-","").isalnum() and 1 < len(t) <= 6))

def get_stock_list():
    log.info(f"Tickers: {len(TICKERS)}")
    return list(TICKERS)

def ema(s, p): return s.ewm(span=p, adjust=False).mean()

def calc_macd(close):
    if len(close) < 30: return None, None, None, None
    m    = ema(close, 12) - ema(close, 26)
    sig  = ema(m, 9)
    hist = m - sig
    return (round(m.iloc[-1], 6), round(sig.iloc[-1], 6),
            round(hist.iloc[-1], 6), round(hist.iloc[-2], 6) if len(hist) >= 2 else 0)

def is_bull(m, sig): return m is not None and m > sig
def is_bear(m, sig): return m is not None and m < sig
def expanding(h, ph): return h is not None and ph is not None and abs(h) > abs(ph)

def calc_rsi(close, p=14):
    if len(close) < p+2: return 50.0
    d = close.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return round((100 - 100/(1+g/(l+1e-9))).iloc[-1], 1)

def calc_atr(df, p=14):
    try:
        h,lo,c = df["High"],df["Low"],df["Close"]
        tr = pd.concat([h-lo,(h-c.shift()).abs(),(lo-c.shift()).abs()],axis=1).max(axis=1)
        return tr.rolling(p).mean().iloc[-1]
    except: return df["Close"].iloc[-1]*0.02

def calc_vr(df, p=20):
    try:
        v=df["Volume"]; avg=v.rolling(p).mean().iloc[-1]
        return round(v.iloc[-1]/(avg+1e-9),2)
    except: return 1.0

def fetch_data(symbol):
    try:
        t  = yf.Ticker(symbol)
        d1 = t.history(period="1y",  interval="1d",  auto_adjust=True)
        wk = t.history(period="5y",  interval="1wk", auto_adjust=True)
        mo = t.history(period="10y", interval="1mo", auto_adjust=True)
        if d1 is None or len(d1)<30: return None
        if wk is None or len(wk)<30: return None
        if mo is None or len(mo)<20: return None
        return {"1d":d1.dropna(subset=["Close"]),"1wk":wk.dropna(subset=["Close"]),"1mo":mo.dropna(subset=["Close"])}
    except Exception as e:
        log.debug(f"fetch {symbol}: {e}")
        return None

def score_ticker(symbol):
    data = fetch_data(symbol)
    if not data: return None

    c1d=data["1d"]["Close"]; cwk=data["1wk"]["Close"]; cmo=data["1mo"]["Close"]
    m1d,s1d,h1d,h1dp = calc_macd(c1d)
    mwk,swk,hwk,hwkp = calc_macd(cwk)
    mmo,smo,hmo,hcmp = calc_macd(cmo)
    if any(x is None for x in [m1d,mwk,mmo]): return None

    b1d=is_bull(m1d,s1d); bwk=is_bull(mwk,swk); bmo=is_bull(mmo,smo)
    s1d=is_bear(m1d,s1d); swk=is_bear(mwk,swk); smo=is_bear(mmo,smo)
    e1d=expanding(h1d,h1dp); ewk=expanding(hwk,hwkp); emo=expanding(hmo,hcmp)

    price=round(c1d.iloc[-1],2)
    rsi=calc_rsi(c1d); atr=calc_atr(data["1d"]); vr=calc_vr(data["1d"])

    # Determine tier and direction
    if b1d and bwk and bmo:
        tier,base,direction="STRONG",7,"BUY"
    elif bwk and bmo:
        tier,base,direction="CONFIRMED",5,"BUY"
    elif bmo and not swk:
        tier,base,direction="DEVELOPING",3,"BUY"
    elif s1d and swk and smo:
        tier,base,direction="STRONG",7,"SHORT"
    elif swk and smo:
        tier,base,direction="CONFIRMED",5,"SHORT"
    elif smo and not bwk:
        tier,base,direction="DEVELOPING",3,"SHORT"
    else:
        return None

    exp_count=sum([e1d,ewk,emo])
    score=base+exp_count
    if vr>1.3: score+=1
    if direction=="BUY" and rsi<60: score+=1
    if direction=="SHORT" and rsi>40: score+=1
    score=min(score,10)

    if direction=="BUY":
        sl=round(price-2.0*atr,2); tp1=round(price+2.0*atr,2); tp2=round(price+4.0*atr,2)
    else:
        sl=round(price+2.0*atr,2); tp1=round(price-2.0*atr,2); tp2=round(price-4.0*atr,2)

    return {"signal":direction,"ticker":symbol,"price":price,"score":score,"tier":tier,
            "sl":sl,"tp1":tp1,"tp2":tp2,"rr":2.0,"rsi":rsi,"vr":vr,
            "b1d":b1d,"bwk":bwk,"bmo":bmo,"s1d":s1d,"swk":swk,"smo":smo,
            "e1d":e1d,"ewk":ewk,"emo":emo,"h1d":h1d,"hwk":hwk,"hmo":hmo}

def fmt_alert(r, is_free=False):
    buy=r["signal"]=="BUY"
    col="🟢" if buy else "🔴"
    act="LONG  📈" if buy else "SHORT 📉"
    sl_d="below" if buy else "above"
    arr="▲" if buy else "▼"
    tier_b={"STRONG":"🔥 STRONG","CONFIRMED":"✅ CONFIRMED","DEVELOPING":"🔵 DEVELOPING"}.get(r["tier"],r["tier"])
    tier_e={"STRONG":"All 3 timeframes aligned — highest conviction",
             "CONFIRMED":"Weekly+Monthly aligned — strong trend confirmed",
             "DEVELOPING":"Monthly turning — watch for weekly confirmation"}.get(r["tier"],"")
    sc=r["score"]; bar="█"*sc+"░"*(10-sc)
    conf=("🔥 VERY HIGH" if sc>=9 else "✅ HIGH" if sc>=7 else "🔵 MEDIUM" if sc>=5 else "⚪ BUILDING")
    def box(b): return "🟩" if b else "🟥"
    d_box=box(r["b1d"] if buy else r["s1d"])
    w_box=box(r["bwk"] if buy else r["swk"])
    m_box=box(r["bmo"] if buy else r["smo"])
    ec=sum([r["e1d"],r["ewk"],r["emo"]])
    mom=("🔥 All 3 TFs accelerating" if ec==3 else "✅ 2 TFs accelerating" if ec==2
         else "🔵 1 TF accelerating" if ec==1 else "⚪ Building")
    rsi_t=("🟢 Oversold" if (buy and r["rsi"]<40) else "🔴 Overbought" if (not buy and r["rsi"]>60) else "🔵 Neutral")
    vol_t=("🔥 HIGH" if r["vr"]>1.5 else "✅ Good" if r["vr"]>1.1 else "⚪ Normal")
    lock="\n🔒 _Full details: /upgrade_" if is_free else ""
    return (f"━━━━━━━━━━━━━━━━━━━━━━━━\n{col} *{r['ticker']}*  |  {act}\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *{tier_b}*\n_{tier_e}_\n\n"
            f"💰 Price:   `${r['price']}`\n🛑 SL ({sl_d}): `${r['sl']}`\n"
            f"💵 TP1 {arr}:   `${r['tp1']}`\n🏆 TP2 {arr}:   `${r['tp2']}`\n📐 R:R:     `1:{r['rr']}`\n\n"
            f"*📡 MACD ALIGNMENT*\nDaily {d_box}  Weekly {w_box}  Monthly {m_box}\n"
            f"Momentum: {mom}\n\n*📈 INDICATORS*\n├ RSI: `{r['rsi']}`  {rsi_t}\n"
            f"└ Volume: {vol_t} `({r['vr']}× avg)`\n\n*⚡ CONFIDENCE:* {conf}\n"
            f"`{bar}` `{sc}/10`{lock}\n━━━━━━━━━━━━━━━━━━━━━━━━")

async def run_scan(tickers):
    buys,shorts,errors=[],[],0
    for i,sym in enumerate(tickers):
        try:
            r=score_ticker(sym)
            if r:
                (buys if r["signal"]=="BUY" else shorts).append(r)
                log.info(f"{r['signal']} {sym} {r['tier']} sc={r['score']}")
        except Exception as e:
            errors+=1; log.debug(f"{sym}: {e}")
        if i>0 and i%30==0:
            await asyncio.sleep(1.5+random.uniform(0,0.5))
    tier_ord={"STRONG":0,"CONFIRMED":1,"DEVELOPING":2}
    buys.sort(key=lambda x:(tier_ord.get(x["tier"],3),-x["score"]))
    shorts.sort(key=lambda x:(tier_ord.get(x["tier"],3),-x["score"]))
    log.info(f"Scan done: B:{len(buys)} S:{len(shorts)} Err:{errors}")
    return buys,shorts,errors

async def deliver_report(bot,user,buys,shorts,total,errors=0):
    cid=user["chat_id"]; pro=is_pro(user); max_r=PRO_MAX if pro else FREE_MAX
    is_free=not pro; et=datetime.now(pytz.timezone("America/New_York"))
    tier_lbl="⭐ PRO" if pro else "🆓 FREE"; name=user.get("name","Trader")
    sb=sum(1 for r in buys if r["tier"]=="STRONG"); ss=sum(1 for r in shorts if r["tier"]=="STRONG")
    cb=sum(1 for r in buys if r["tier"]=="CONFIRMED"); cs=sum(1 for r in shorts if r["tier"]=="CONFIRMED")
    db2=sum(1 for r in buys if r["tier"]=="DEVELOPING"); ds=sum(1 for r in shorts if r["tier"]=="DEVELOPING")
    try:
        await bot.send_message(cid,
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n📊 *{BOT_NAME}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {name}  |  🏷 {tier_lbl}\n🕐 {et.strftime('%a %b %d  %H:%M ET')}\n"
            f"🔍 Scanned: *{total}* stocks\n\n*📡 MACD SIGNAL SUMMARY*\n"
            f"🔥 Strong:     🟢 {sb}  🔴 {ss}\n✅ Confirmed:  🟢 {cb}  🔴 {cs}\n"
            f"🔵 Developing: 🟢 {db2}  🔴 {ds}\n━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.MARKDOWN)
    except: return
    await asyncio.sleep(0.4)

    shown_b=buys[:max_r]
    if shown_b:
        await bot.send_message(cid,f"🟢 *LONG SETUPS — {len(shown_b)} shown*"+(f" _(of {len(buys)} total)_" if len(buys)>len(shown_b) else ""),parse_mode=ParseMode.MARKDOWN)
        for r in shown_b:
            try: await bot.send_message(cid,fmt_alert(r,is_free),parse_mode=ParseMode.MARKDOWN); await asyncio.sleep(0.35)
            except Exception as e: log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,"🟢 *No long setups this scan*\n_MACD not bullish on any timeframe combination right now_\n_This is expected during strong downtrends — check shorts below_",parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(0.5)
    shown_s=shorts[:max_r]
    if shown_s:
        await bot.send_message(cid,f"🔴 *SHORT SETUPS — {len(shown_s)} shown*"+(f" _(of {len(shorts)} total)_" if len(shorts)>len(shown_s) else ""),parse_mode=ParseMode.MARKDOWN)
        for r in shown_s:
            try: await bot.send_message(cid,fmt_alert(r,is_free),parse_mode=ParseMode.MARKDOWN); await asyncio.sleep(0.35)
            except Exception as e: log.warning(f"Send {r['ticker']}: {e}")
    else:
        await bot.send_message(cid,"🔴 *No short setups this scan*",parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(0.5)
    if is_free:
        await bot.send_message(cid,
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n🔒 *FREE TIER* — {name}\nShowing {FREE_MAX} of {len(buys)} longs + {len(shorts)} shorts\n\n"
            f"⭐ *PRO — ${PRO_PRICE}/month*\n✅ All {PRO_MAX} signals per scan\n✅ Full MACD + momentum details\n✅ Volume analysis\n✅ Priority delivery\n\n👉 /upgrade\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Not financial advice._",
            parse_mode=ParseMode.MARKDOWN)
    else:
        await bot.send_message(cid,
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n📋 *TRADE RULES*  |  {name}\n🔥 Strong → enter with full size\n✅ Confirmed → 50-75% size\n🔵 Developing → watch only\n\n"
            f"🟢 LONG: SL below entry → TP1 (50%) → TP2 trail\n🔴 SHORT: SL above entry → TP1 (50%) → TP2 trail\n⚠️ Never risk more than 2% per trade\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Not financial advice._",
            parse_mode=ParseMode.MARKDOWN)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=load_db(); cid=update.effective_chat.id; u=get_user(db,cid)
    u["username"]=update.effective_user.username or ""; save_db(db)
    if u.get("onboarded"):
        await show_main_menu(update,u); return ConversationHandler.END
    tg_name=update.effective_user.first_name or "Trader"
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🚀 *Welcome to {BOT_NAME}!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hey {tg_name}! 👋\n\nI scan *{len(TICKERS)}+ stocks* every 4 hours\nusing *MACD on Daily + Weekly + Monthly*\n\n"
        f"*📡 Signal Tiers:*\n🔥 Strong → All 3 TFs aligned\n✅ Confirmed → 2 TFs aligned\n🔵 Developing → Monthly turning\n\n"
        f"You ALWAYS get signals — bull or bear market.\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n*Step 1 of 2* ✍️\n\nWhat's your *first name*?",
        parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def onboard_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name=update.message.text.strip()
    if not name or len(name)>30:
        await update.message.reply_text("Please enter a valid name (1-30 chars):"); return ASK_NAME
    context.user_data["ob_name"]=name
    kb=ReplyKeyboardMarkup([["🆕 Beginner","📊 Intermediate"],["🏆 Advanced","💼 Professional"]],resize_keyboard=True,one_time_keyboard=True)
    await update.message.reply_text(f"Nice to meet you, *{name}!* 🤝\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n*Step 2 of 2*\n\nWhat's your trading experience?",parse_mode=ParseMode.MARKDOWN,reply_markup=kb)
    return ASK_EXP

async def onboard_exp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exp=update.message.text.strip(); name=context.user_data.get("ob_name",update.effective_user.first_name or "Trader")
    db=load_db(); cid=update.effective_chat.id; u=get_user(db,cid)
    u["name"]=name; u["experience"]=exp; u["onboarded"]=True; save_db(db)
    pro=is_pro(u)
    kb=ReplyKeyboardMarkup([["🔍 Scan Now","📊 My Account"],["⭐ Upgrade to PRO","❓ Help"]],resize_keyboard=True)
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n✅ *All set, {name}!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *Your Setup:*\n├ Name: *{name}*\n├ Level: *{exp}*\n├ Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"└ Signals: *{'Up to '+str(PRO_MAX) if pro else str(FREE_MAX)+' per scan (FREE)'}*\n\n"
        f"Strategy: *MACD on D+W+M* ✅\nAuto scans every *4 hours* ✅\n\n"
        f"*/scan* — Run scan now\n*/status* — Your account\n*/upgrade* — Get PRO\n*/help* — Signal guide\n*/signals* — Indicator guide\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n_Tap Scan Now to start!_ 🚀",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    return ConversationHandler.END

async def onboard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Setup cancelled. Type /start to begin again.",reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def show_main_menu(update,u):
    name=u.get("name","Trader"); pro=is_pro(u)
    et=datetime.now(pytz.timezone("America/New_York"))
    mkt="🟢 OPEN" if (et.weekday()<5 and 9<=et.hour<16) else "🔴 CLOSED"
    kb=ReplyKeyboardMarkup([["🔍 Scan Now","📊 My Account"],["⭐ Upgrade to PRO","❓ Help"]],resize_keyboard=True)
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🚀 *{BOT_NAME}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Welcome back, *{name}!* 👋\nTier: *{'⭐ PRO' if pro else '🆓 FREE'}*\nMarket: {mkt}  |  {et.strftime('%H:%M ET')}\n\n"
        f"*/scan* /status /upgrade /help /signals\n━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def handle_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t=update.message.text
    if t=="🔍 Scan Now": await cmd_scan(update,context)
    elif t=="📊 My Account": await cmd_status(update,context)
    elif t=="⭐ Upgrade to PRO": await cmd_upgrade(update,context)
    elif t=="❓ Help": await cmd_help(update,context)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=load_db(); cid=update.effective_chat.id; u=get_user(db,cid)
    if not u.get("onboarded"):
        await update.message.reply_text("Please complete setup first — send /start 👋"); return
    u["scans"]=u.get("scans",0)+1; u["last_scan"]=datetime.utcnow().isoformat(); save_db(db)
    name=u.get("name","Trader"); tickers=get_stock_list()
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🔍 *Scanning, {name}!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Strategy: *MACD — Daily + Weekly + Monthly*\n📈 Stocks: *{len(tickers)}*\n⏱ Est: *~15 mins*\n\n"
        f"Finding Strong, Confirmed & Developing setups...\n_Results coming_ 📬",
        parse_mode=ParseMode.MARKDOWN)
    buys,shorts,errors=await run_scan(tickers)
    await deliver_report(context.bot,u,buys,shorts,len(tickers),errors)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=load_db(); cid=update.effective_chat.id; u=get_user(db,cid); pro=is_pro(u)
    name=u.get("name","Trader")
    et=datetime.now(pytz.timezone("America/New_York"))
    mkt="🟢 OPEN" if (et.weekday()<5 and 9<=et.hour<16) else "🔴 CLOSED"
    exp=u.get("pro_until") or ("Lifetime" if pro else "—")
    last=u.get("last_scan","Never")
    if last!="Never":
        try: last=datetime.fromisoformat(last).strftime("%b %d %H:%M UTC")
        except: pass
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n📡 *YOUR ACCOUNT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Name: *{name}*\n🎓 Level: *{u.get('experience','—')}*\n🏷 Tier: *{'⭐ PRO' if pro else '🆓 FREE'}*\n"
        f"{'📅 PRO until: `'+exp+'`' if pro else '👉 /upgrade to go PRO'}\n\n"
        f"📊 Strategy: *MACD D+W+M*\n📬 Signals/scan: *{PRO_MAX if pro else FREE_MAX}*\n"
        f"🔢 Total Scans: *{u.get('scans',0)}*\n🕐 Last Scan: *{last}*\n\n"
        f"🏛 Market: {mkt}\n🕐 NY Time: {et.strftime('%H:%M ET')}\n📈 Stocks: *{len(TICKERS)}*\n━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=load_db(); cid=update.effective_chat.id; u=get_user(db,cid)
    if is_pro(u):
        await update.message.reply_text(f"✅ *You already have PRO!*\nExpires: `{u.get('pro_until') or 'Lifetime'}`",parse_mode=ParseMode.MARKDOWN); return
    name=u.get("name","Trader")
    kb=[[InlineKeyboardButton("💰 USDT TRC20",callback_data="pay_usdt")],
        [InlineKeyboardButton("₿  Bitcoin",   callback_data="pay_btc")],
        [InlineKeyboardButton("Ξ  Ethereum",  callback_data="pay_eth")],
        [InlineKeyboardButton("◎  Solana",    callback_data="pay_sol")]]
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n⭐ *UPGRADE TO PRO*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hey *{name}*! Unlock:\n\n🔓 *{PRO_MAX} signals per scan* (vs {FREE_MAX})\n"
        f"🔓 Strong + Confirmed + Developing\n🔓 Full MACD momentum breakdown\n"
        f"🔓 Volume + RSI on every signal\n🔓 Trade rules after every scan\n\n"
        f"💵 *${PRO_PRICE}/month*\n\n👇 *Choose payment:*",
        parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup(kb))

async def callback_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); cid=q.from_user.id
    db=load_db(); u=get_user(db,cid); name=u.get("name","Trader")
    wallets={"pay_usdt":("💰 USDT TRC20",USDT_WALLET,"USDT"),"pay_btc":("₿ Bitcoin",BTC_WALLET,"BTC"),
             "pay_eth":("Ξ Ethereum",ETH_WALLET,"ETH"),"pay_sol":("◎ Solana",SOL_WALLET,"SOL")}
    label,wallet,coin=wallets.get(q.data,("?","?","?"))
    await q.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n{label} *PAYMENT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 For: *{name}*\n💵 Amount: *${PRO_PRICE} USD* in {coin}\n\n"
        f"📋 *Send to:*\n`{wallet}`\n\n*After paying, DM {OWNER_USERNAME}:*\n"
        f"1️⃣ Screenshot of payment\n2️⃣ Your Telegram ID: `{cid}`\n\n✅ Access in under 1 hour\n━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=load_db(); u=get_user(db,update.effective_chat.id); name=u.get("name","Trader")
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n📋 *HOW TO TRADE SIGNALS*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*📡 SIGNAL TIERS*\n🔥 *Strong* — D+W+M all aligned → Full size entry\n"
        f"✅ *Confirmed* — W+M aligned → 50-75% size\n🔵 *Developing* — Monthly turning → Watch only\n\n"
        f"*🟢 LONG TRADE*\n1. Enter at shown price\n2. Set SL immediately (below entry)\n"
        f"3. TP1 → close 50% of position\n4. Move SL to breakeven\n5. TP2 → trail stop\n\n"
        f"*🔴 SHORT TRADE*\n1. Short at shown price\n2. Set SL (above entry)\n"
        f"3. TP1 → cover 50%\n4. Move SL to breakeven\n5. TP2 → trail stop down\n\n"
        f"*📊 MACD BOXES*\n🟩 = Bullish on that timeframe\n🟥 = Bearish on that timeframe\n"
        f"3× 🟩🟩🟩 = Maximum conviction\n\n"
        f"*⚠️ GOLDEN RULES*\n• Never risk more than 2% per trade\n• Check the chart before entering\n"
        f"• Trust the shorts in a bear market\n• Patience beats chasing\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Not financial advice, {name}._",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n📊 *INDICATOR GUIDE*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*MACD*\nEMA(12) minus EMA(26)\nLine above signal = bullish momentum\nLine below signal = bearish momentum\n\n"
        f"*📡 MACD Boxes*\nDaily  🟩 = short-term bull\nWeekly 🟩 = medium-term bull\nMonthly 🟩 = long-term bull\n\n"
        f"*Momentum (Histogram)*\nExpanding bars = momentum growing\n3/3 accelerating = strongest setup\n\n"
        f"*RSI*\n< 40 = oversold (buy zone)\n> 60 = overbought (short zone)\n\n"
        f"*Volume*\n🔥 HIGH = 1.5x avg — strong move\n✅ Good = 1.1x avg — decent\n⚪ Normal = average\n\n"
        f"*R:R 1:2*\nRisk $1 to potentially make $2\nTP1 = 1x risk, TP2 = 2x risk\n━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db=load_db(); total=len(db); pros=sum(1 for u in db.values() if is_pro(u))
    onb=sum(1 for u in db.values() if u.get("onboarded"))
    await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🔧 *ADMIN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Users: *{total}*  ✅ Onboarded: *{onb}*\n⭐ PRO: *{pros}*  🆓 FREE: *{total-pros}*\n\n"
        f"*/addpro* `<id> <days>`\n*/rmpro* `<id>`\n*/broadcast* `<msg>`\n*/userlist*",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_addpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    args=context.args
    if len(args)<2: await update.message.reply_text("Usage: /addpro <id> <days>"); return
    try: tid,days=int(args[0]),int(args[1])
    except: await update.message.reply_text("Invalid. Example: /addpro 123456 30"); return
    db=load_db(); u=get_user(db,tid)
    u["tier"]="pro"; u["pro_until"]=(datetime.utcnow()+timedelta(days=days)).isoformat(); save_db(db)
    await update.message.reply_text(f"✅ PRO granted to `{tid}` for *{days} days*",parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(tid,f"🎉 *PRO activated, {u.get('name','Trader')}!*\n\n✅ {days} days\n✅ {PRO_MAX} signals/scan\n\nSend /scan now! 🚀",parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cmd_rmpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    args=context.args
    if not args: await update.message.reply_text("Usage: /rmpro <id>"); return
    try: tid=int(args[0])
    except: await update.message.reply_text("Invalid."); return
    db=load_db(); u=get_user(db,tid); u["tier"]="free"; u["pro_until"]=None; save_db(db)
    await update.message.reply_text(f"✅ PRO removed from `{tid}`",parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    if not context.args: await update.message.reply_text("Usage: /broadcast <msg>"); return
    msg=" ".join(context.args); db=load_db(); sent,fail=0,0
    for ud in db.values():
        try: await context.bot.send_message(ud["chat_id"],f"📢 *Announcement*\n\n{msg}",parse_mode=ParseMode.MARKDOWN); sent+=1
        except: fail+=1
        await asyncio.sleep(0.1)
    await update.message.reply_text(f"✅ Sent:{sent} Failed:{fail}")

async def cmd_userlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_chat.id): return
    db=load_db(); lines=[f"*USERS* ({len(db)} total)\n"]
    for uid,u in list(db.items())[:50]:
        tier="PRO⭐" if is_pro(u) else "free"; name=u.get("name") or u.get("username") or "—"
        lines.append(f"`{uid}` | {name} | {tier} | {u.get('scans',0)} scans")
    await update.message.reply_text("\n".join(lines),parse_mode=ParseMode.MARKDOWN)

async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    log.info("Auto scan starting...")
    db=load_db()
    if not db: return
    tickers=get_stock_list()
    buys,shorts,errors=await run_scan(tickers)
    for uid,udata in db.items():
        if not udata.get("onboarded"): continue
        try: await deliver_report(context.bot,udata,buys,shorts,len(tickers),errors); await asyncio.sleep(0.5)
        except Exception as e: log.warning(f"Auto deliver {uid}: {e}")

def main():
    if TELEGRAM_TOKEN=="YOUR_TOKEN": raise ValueError("Set TELEGRAM_TOKEN!")
    if OWNER_CHAT_ID==0: raise ValueError("Set CHAT_ID!")
    log.info(f"Starting {BOT_NAME} v7.0 — {len(TICKERS)} tickers")
    app=Application.builder().token(TELEGRAM_TOKEN).build()
    conv=ConversationHandler(
        entry_points=[CommandHandler("start",cmd_start)],
        states={ASK_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,onboard_name)],
                ASK_EXP:[MessageHandler(filters.TEXT&~filters.COMMAND,onboard_exp)]},
        fallbacks=[CommandHandler("cancel",onboard_cancel)],allow_reentry=True)
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND&filters.Regex(r"^(🔍 Scan Now|📊 My Account|⭐ Upgrade to PRO|❓ Help)$"),handle_keyboard))
    for cmd,fn in [("scan",cmd_scan),("status",cmd_status),("upgrade",cmd_upgrade),("help",cmd_help),("signals",cmd_signals)]:
        app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(CallbackQueryHandler(callback_pay,pattern="^pay_"))
    for cmd,fn in [("admin",cmd_admin),("addpro",cmd_addpro),("rmpro",cmd_rmpro),("broadcast",cmd_broadcast),("userlist",cmd_userlist)]:
        app.add_handler(CommandHandler(cmd,fn))
    app.job_queue.run_repeating(scheduled_scan,interval=SCAN_INTERVAL,first=120)
    log.info(f"{BOT_NAME} v7.0 live ✅")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
