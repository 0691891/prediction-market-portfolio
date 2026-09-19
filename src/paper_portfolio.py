#!/usr/bin/env python3
"""Append-only, deterministic virtual-only football portfolio processor.

Reads paper/signals.json and paper/results.json. Updates paper/state.json;
never reads or writes data/trades.json and never sends orders.
"""
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
GRADES = {"A": 0.75, "B": 0.5, "C": 0.25}
LEAGUES = {"Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
           "UEFA Champions League", "UEFA Europa League", "EFL/Carabao Cup", "FA Cup"}

def load(name, default):
    p = PAPER / name
    return json.loads(p.read_text()) if p.exists() else default

def save(name, obj):
    (PAPER / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

def utc(x):
    z = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    if z.utcoffset() is None:
        raise ValueError("timestamp must be offset-aware")
    return z.astimezone(dt.timezone.utc)

def run():
    account = load("account.json", {})
    start = float(account["initial_capital_usd"])
    unit = float(account["unit_usd"])
    per_match = float(account["maximum_exposure_per_match_usd"])
    total_cap = float(account["maximum_total_open_exposure_usd"])
    signals = load("signals.json", {"signals": []})["signals"]
    results = load("results.json", {"results": []})["results"]
    old = load("state.json", {"trades": [], "rejections": []})
    trades = {t["signal_id"]: t for t in old.get("trades", [])}
    rejections = {r["signal_id"]: r for r in old.get("rejections", [])}
    result_index = {}
    for r in results:
        key = (r.get("match_id"), r.get("market_id"), r.get("selection"))
        if key in result_index and result_index[key].get("outcome") != r.get("outcome"):
            raise ValueError("contradictory paper settlement for " + str(key))
        result_index[key] = r

    for s in signals:
        sid = s.get("signal_id")
        if not sid:
            raise ValueError("paper signal missing signal_id")
        if sid in trades or sid in rejections:
            continue
        why = None
        try:
            if s.get("competition") not in LEAGUES: raise ValueError("unsupported league")
            if s.get("paper_eligible") is False: raise ValueError("explicitly paper-ineligible")
            research = s.get("cohort") == "ALL_MATCHES_300_RESEARCH" and s.get("model_version") == "v0.5-market-baseline-control"
            if s.get("lineup_status") == "UNCONFIRMED" and not research and s.get("lineup_uncertainty_resolved") is not True:
                raise ValueError("unresolved lineup uncertainty")
            if any(flag in str(s.get("risk_flags", [])).lower() for flag in
                   ("unresolved rotation", "unresolved motivation", "lineup shock")):
                raise ValueError("unresolved risk gate")
            kickoff, quote = utc(s["kickoff_utc"]), utc(s["quote_timestamp_utc"])
            entry_phase = s.get("entry_phase", "PREMATCH")
            if entry_phase != "PREMATCH":
                raise ValueError("in-play paper trading disabled: prematch-only research mode")
            if quote >= kickoff:
                raise ValueError("prematch quote was not pre-kickoff")
            for key in ("match_id", "match", "market", "selection", "market_id",
                        "quote_source", "quote_url", "model_version", "scenario"):
                if not s.get(key): raise ValueError("missing " + key)
            odds = float(s["decimal_odds"])
            fair = float(s["fair_probability"])
            stake = float(s["stake_usd"])
            grade = s["grade"]
            if grade not in GRADES: raise ValueError("unknown grade")
            if not (1 < odds <= 1001 and 0 < fair < 1 and stake > 0):
                raise ValueError("invalid odds, fair or stake")
            if stake > GRADES[grade] * unit + 0.001: raise ValueError("grade stake cap")
            net_ev = fair * odds - 1 - float(s.get("fees_usd", 0)) / stake
            if not research and net_ev <= 0: raise ValueError("nonpositive net EV")
            if not research and net_ev < float(s.get("min_net_ev", 0.05)): raise ValueError("net EV below paper entry threshold")
            if s.get("liquidity_usd") is not None and float(s["liquidity_usd"]) < stake:
                raise ValueError("insufficient quoted liquidity")
            open_rows = [t for t in trades.values() if t["status"] == "OPEN"]
            open_total = sum(float(t["stake_usd"]) for t in open_rows)
            this_match = sum(float(t["stake_usd"]) for t in open_rows
                             if s["match_id"] in t.get("match_ids", [t["match_id"]]))
            if this_match + stake > per_match + 0.001: raise ValueError("match exposure limit")
            if open_total + stake > total_cap + 0.001: raise ValueError("total exposure limit")
            legs=s.get("legs") or []
            if legs:
                if len(legs)!=2 or len({x.get("match_id") for x in legs})!=2: raise ValueError("parlay requires two distinct fixtures")
                if s.get("market_id")!="PARLAY-2": raise ValueError("parlay market_id must be PARLAY-2")
                if any(not all(x.get(k) for k in ("match_id","market_id","selection","kickoff_utc","quote_timestamp_utc","decimal_odds")) for x in legs): raise ValueError("missing parlay leg fields")
                if any(utc(x["quote_timestamp_utc"])>=utc(x["kickoff_utc"]) for x in legs): raise ValueError("parlay leg quote after kickoff")
                if any(abs((utc(x["quote_timestamp_utc"])-quote).total_seconds())>1800 for x in legs): raise ValueError("unsynchronized parlay quotes")
                if abs(odds-float(legs[0]["decimal_odds"])*float(legs[1]["decimal_odds"]))>0.0001: raise ValueError("invalid parlay product odds")
                if grade!="B" or stake>0.5*unit+0.001: raise ValueError("parlay grade B cap")
                if not research and not s.get("joint_probability_method"): raise ValueError("joint probability method required")
                for m in (x["match_id"] for x in legs):
                    if sum(float(t["stake_usd"]) for t in open_rows if m in t.get("match_ids",[t["match_id"]]))+stake>per_match+0.001: raise ValueError("parlay leg exposure cap")
        except (KeyError, TypeError, ValueError) as e:
            why = str(e)
        if why:
            rejections[sid] = {"signal_id": sid, "reason": why}
            continue
        trades[sid] = {
            "signal_id": sid, "match_id": s["match_id"], "match_ids": [x["match_id"] for x in s.get("legs",[])] if s.get("legs") else [s["match_id"]],
            "legs": s.get("legs",[]), "bet_type": "PARLAY_2" if s.get("legs") else "SINGLE",
            "competition": s["competition"], "match": s["match"],
            "market": s["market"], "selection": s["selection"], "market_id": s["market_id"],
            "quote_timestamp_utc": s["quote_timestamp_utc"],
            "quote_source": s["quote_source"], "quote_url": s["quote_url"],
            "kickoff_utc": s["kickoff_utc"], "model_version": s["model_version"],
            "fair_probability_at_entry": fair, "decimal_odds": odds, "stake_usd": stake,
            "entry_ev": round(fair * odds - 1, 6), "entry_net_ev": round(net_ev, 6), "grade": grade,
            "scenario": s["scenario"], "entry_phase": entry_phase,
            "cohort": s.get("cohort", "ALPHA_CANDIDATE"),
            "entry_reason": s.get("entry_reason"),
            "live_entry_state": ({k: s.get(k) for k in
                ("event_state_timestamp_utc", "home_score", "away_score",
                 "match_minute", "home_red_cards", "away_red_cards",
                 "live_fair_method", "score_source", "quote_age_seconds")}
                 if entry_phase == "LIVE" else None),
            "status": "OPEN", "realized_pnl_usd": 0.0,
            "fees_usd": float(s.get("fees_usd", 0))
        }

    for t in trades.values():
        if t["status"] != "OPEN": continue
        legs=t.get("legs") or []
        if legs:
            leg_results=[result_index.get((x["match_id"],x["market_id"],x["selection"])) for x in legs]
            if any(not x or not x.get("result_source") or not x.get("verified_at_utc") for x in leg_results): continue
            if any(utc(x["verified_at_utc"])<=utc(t["quote_timestamp_utc"]) for x in leg_results): raise ValueError("parlay result before entry")
            if any(x["outcome"]=="LOSS" for x in leg_results): outcome="LOSS"
            elif all(x["outcome"]=="WIN" for x in leg_results): outcome="WIN"
            elif all(x["outcome"] in ("WIN","VOID","PUSH") for x in leg_results):
                outcome="VOID" if all(x["outcome"] in ("VOID","PUSH") for x in leg_results) else "PARTIAL_VOID"
            else: continue
            result={"outcome":outcome,"result_source":"; ".join(x["result_source"] for x in leg_results),
                    "verified_at_utc":max(x["verified_at_utc"] for x in leg_results)}
            if outcome=="PARTIAL_VOID":
                t["decimal_odds_settled"]=float(__import__("math").prod(float(leg["decimal_odds"]) for leg,res in zip(legs,leg_results) if res["outcome"]=="WIN"))
        else:
            key = (t["match_id"], t["market_id"], t["selection"])
            result = result_index.get(key)
            if not result: continue
            outcome = result.get("outcome")
        if outcome not in ("WIN", "LOSS", "VOID", "PUSH", "PARTIAL_VOID"): continue
        if not result.get("result_source") or not result.get("verified_at_utc"):
            continue
        if utc(result["verified_at_utc"]) <= utc(t["kickoff_utc"]):
            raise ValueError("result verified before kickoff " + t["signal_id"])
        stake, odds, fees = t["stake_usd"], t.get("decimal_odds_settled",t["decimal_odds"]), t["fees_usd"]
        t["realized_pnl_usd"] = round(
            (stake * (odds - 1) if outcome in ("WIN","PARTIAL_VOID") else
             -stake if outcome == "LOSS" else 0) - fees, 2)
        t["outcome"] = outcome
        t["result_source"] = result["result_source"]
        t["verified_at_utc"] = result["verified_at_utc"]
        t["status"] = "SETTLED"

    rows = list(trades.values())
    realized = round(sum(t["realized_pnl_usd"] for t in rows), 2)
    open_stake = round(sum(t["stake_usd"] for t in rows if t["status"] == "OPEN"), 2)
    settled_stake = sum(t["stake_usd"] for t in rows if t["status"] == "SETTLED")
    state = {
        "mode": "PAPER_ONLY", "initial_capital_usd": start,
        "realized_pnl_usd": realized, "realized_nav_usd": round(start + realized, 2),
        "open_stake_usd": open_stake,
        "available_cash_usd": round(start + realized - open_stake, 2),
        "settled_stake_usd": round(settled_stake, 2),
        "settled_stake_roi": round(realized / settled_stake, 6) if settled_stake else None,
        "paper_orders": len(rows), "open_orders": sum(t["status"] == "OPEN" for t in rows),
        "settled_orders": sum(t["status"] == "SETTLED" for t in rows),
        "trades": rows, "rejections": list(rejections.values()),
        "valuation_note": "Realized NAV excludes unreliable unrealized marks; OPEN stake reserved."
    }
    save("state.json", state)
    print("paper NAV", state["realized_nav_usd"], "orders", len(rows),
          "settled", state["settled_orders"], "rejections", len(rejections))

if __name__ == "__main__":
    run()
