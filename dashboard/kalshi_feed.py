"""Read-only Kalshi REST adapter: public football markets + server-side signed account GETs.

Never sends POST/PUT/DELETE; never logs secrets, private data or private endpoint bodies.
No actual trades or order placement. GitHub Actions secrets and Streamlit Cloud
secrets are DIFFERENT stores: Streamlit deployment needs its own app secrets.
"""
import base64
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

API = "https://external-api.kalshi.com"
PREFIX = "/trade-api/v2"
FOOTBALL = re.compile(r"(?i)\b(soccer|premier league|la liga|serie a|bundesliga|ligue 1|champions league|europa league|carabao|fa cup|uefa|mls|world cup|epl|football match|futbol)\b")
SKIP = re.compile(r"(?i)\b(nfl|nba|nhl|ncaa|super bowl|american football|college football)\b")

def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def _number(v):
    try:
        return float(Decimal(str(v))) if v is not None else None
    except (InvalidOperation, ValueError):
        return None

def dollars(obj, dollar_field, cent_field):
    raw=_number(obj.get(dollar_field))
    if raw is not None:return raw
    cents=_number(obj.get(cent_field))
    return cents/100.0 if cents is not None else None

def _signed_headers(key_id, pem, path):
    if not key_id or not pem:
        raise ValueError("Kalshi account credentials not configured")
    # Import inside authenticated request so public feed works without cryptography.
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    ts=str(int(time.time()*1000))
    # Kalshi signs timestamp + uppercase method + request path WITHOUT query.
    msg=(ts+"GET"+path).encode("utf-8")
    private=serialization.load_pem_private_key(pem.replace("\\n","\n").encode("utf-8"),password=None)
    signature=private.sign(msg,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                           salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    return {"KALSHI-ACCESS-KEY":key_id,
            "KALSHI-ACCESS-TIMESTAMP":ts,
            "KALSHI-ACCESS-SIGNATURE":base64.b64encode(signature).decode("ascii")}

def get(path,params=None,key_id=None,pem=None):
    if not path.startswith(PREFIX+"/"):raise ValueError("Invalid API path")
    if key_id or pem:
        if not (key_id and pem):raise ValueError("Both Kalshi credentials are required")
        headers=_signed_headers(key_id,pem,path)
    else:headers={}
    params={k:v for k,v in (params or {}).items() if v is not None and v!=""}
    qs=urllib.parse.urlencode(params)
    url=API+path+("?"+qs if qs else "")
    req=urllib.request.Request(url,headers={"User-Agent":"FootballAlphaTerminal/1.2",**headers},method="GET")
    try:
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never include remote error body: could leak private account context.
        raise RuntimeError("Kalshi HTTP "+str(exc.code)+" on "+path) from None

def _football_title(x):
    title=" ".join(str(x.get(k) or "") for k in ("title","subtitle","category","ticker"))
    return bool(FOOTBALL.search(title) and not SKIP.search(title))

def market_row(m, fetched, source):
    bid=dollars(m,"yes_bid_dollars","yes_bid")
    ask=dollars(m,"yes_ask_dollars","yes_ask")
    no_bid=dollars(m,"no_bid_dollars","no_bid")
    no_ask=dollars(m,"no_ask_dollars","no_ask")
    # No bid => YES ask at 1 - no bid; explicitly label it as derived, not direct quote.
    if ask is None and no_bid is not None:ask=round(1-no_bid,6)
    if no_ask is None and bid is not None:no_ask=round(1-bid,6)
    return {"ticker":m.get("ticker"),"event_ticker":m.get("event_ticker"),
            "series_ticker":m.get("series_ticker"),"title":m.get("title"),
            "subtitle":m.get("subtitle"),"status":m.get("status"),
            "yes_bid_usd":bid,"yes_ask_usd":ask,
            "no_bid_usd":no_bid,"no_ask_usd":no_ask,
            "last_usd":dollars(m,"last_price_dollars","last_price"),
            "volume_contracts":_number(m.get("volume_fp",m.get("volume"))),
            "open_interest_contracts":_number(m.get("open_interest_fp",m.get("open_interest"))),
            "bid_size_contracts":_number(m.get("yes_bid_size_fp")),
            "ask_size_contracts":_number(m.get("yes_ask_size_fp")),
            "close_time":m.get("close_time"),"market_updated_utc":m.get("updated_time"),
            "fetched_utc":fetched,"source":source,
            "quote_quality":"INDICATIVE_NOT_DEPTH_OR_FILL_VERIFIED"}

def public_markets(series_tickers=None, watch_tickers=None, pages_per_series=2):
    """Football market discovery, safe no-auth GET; never promises exhaustive coverage."""
    fetched=_now();errors={};sources=[];raw=[]
    series=[x.strip().upper() for x in (series_tickers or []) if x and x.strip()]
    watch=[x.strip().upper() for x in (watch_tickers or []) if x and x.strip()]
    if not series:
        try:
            d=get(PREFIX+"/series",{"category":"Sports"})
            eligible=[x for x in d.get("series",[]) if _football_title(x) and x.get("ticker")]
            # Front-load match-result series, rather than season props; cap API
            # requests per hourly scan to reduce Kalshi 429 rate-limit responses.
            def priority(x):
                name=str(x.get("title","")).lower()
                ticker=str(x.get("ticker","")).upper()
                match_terms=("match winner","game winner","match result","soccer game","to win the match")
                league_terms=("premier league","la liga","bundesliga","serie a","ligue 1","champions league","europa league")
                return (int(any(z in name for z in match_terms) or ticker.endswith("GAME")),
                        int(any(z in name for z in league_terms)),
                        -int("season" in name or "top scorer" in name))
            eligible.sort(key=priority,reverse=True)
            sources=[x["ticker"] for x in eligible[:10]]
        except (RuntimeError,OSError,ValueError,urllib.error.URLError) as exc:
            errors["series_discovery"]=str(exc)
    else:sources=series[:24]
    for ticker in sources:
        cursor=None
        time.sleep(0.22)
        for _ in range(pages_per_series):
            try:
                d=get(PREFIX+"/markets",{"series_ticker":ticker,"status":"open",
                                          "limit":200,"cursor":cursor})
                raw.extend(d.get("markets",[]))
                cursor=d.get("cursor")
                if not cursor:break
            except (RuntimeError,OSError,ValueError,urllib.error.URLError) as exc:
                errors[ticker]=str(exc);break
    for ticker in watch[:30]:
        # Only controlled uppercase ticker identifiers go into URL path.
        if not re.fullmatch(r"[A-Z0-9_-]{2,120}",ticker):continue
        try:
            d=get(PREFIX+"/markets/"+urllib.parse.quote(ticker,safe="-_"))
            if d.get("market"):raw.append(d["market"])
        except (RuntimeError,OSError,ValueError,urllib.error.URLError) as exc:
            errors["watch:"+ticker]=str(exc)
    seen=set();rows=[]
    for m in raw:
        ticker=m.get("ticker")
        if not ticker or ticker in seen:continue
        seen.add(ticker)
        rows.append(market_row(m,fetched,"Kalshi REST GET"))
    return rows,errors,fetched,{"discovered_series":len(sources),"selected_series":sources,"pages_per_series":pages_per_series,
                                "watch_count":len(watch),"note":"Pagination/coverage limited; configure series tickers to widen."}

def read_account(key_id,pem):
    """Server-only private account data, NEVER persist to repo/public JSON."""
    fetched=_now();errors={}
    if not (key_id and pem):
        return {},{"credentials":"Configure key ID and PEM in Streamlit app secrets"},fetched
    endpoints={"balance":("/portfolio/balance",{}),
               "positions":("/portfolio/positions",{"limit":200}),
               "orders":("/portfolio/orders",{"limit":100})}
    result={}
    for name,(path,params) in endpoints.items():
        try:result[name]=get(PREFIX+path,params,key_id,pem)
        except (RuntimeError,OSError,ValueError,urllib.error.URLError) as exc:
            errors[name]=str(exc)
    return result,errors,fetched

def account_view(data):
    """Return only intended fields, not full exchange responses / PII."""
    balance=data.get("balance") or {}
    positions=(data.get("positions") or {}).get("market_positions") or []
    event_positions=(data.get("positions") or {}).get("event_positions") or []
    orders=(data.get("orders") or {}).get("orders") or []
    snapshot={"balance_usd":dollars(balance,"balance_dollars","balance"),
              "portfolio_value_usd":dollars(balance,"portfolio_value_dollars","portfolio_value"),
              "total_value_usd":None}
    if snapshot["balance_usd"] is not None and snapshot["portfolio_value_usd"] is not None:
        snapshot["total_value_usd"]=snapshot["balance_usd"]+snapshot["portfolio_value_usd"]
    safe_positions=[{"ticker":p.get("ticker"),"position_fp":p.get("position_fp",p.get("position")),
                    "market_exposure_usd":dollars(p,"market_exposure_dollars","market_exposure"),
                    "realized_pnl_usd":dollars(p,"realized_pnl_dollars","realized_pnl"),
                    "fees_paid_usd":dollars(p,"fees_paid_dollars","fees_paid")} for p in positions]
    safe_orders=[{"ticker":o.get("ticker"),"side":o.get("side"),"action":o.get("action"),
                  "status":o.get("status"),"remaining_count_fp":o.get("remaining_count_fp",o.get("remaining_count")),
                  "created_time":o.get("created_time")} for o in orders]
    return snapshot,safe_positions,safe_orders,len(event_positions)
