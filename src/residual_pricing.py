#!/usr/bin/env python3
"""v0.4 market-anchored football residual pricing.

Only contemporaneous, frozen, verified features enter the price. Missing
inputs contribute zero, NEVER a fabricated observation. Uncalibrated residual
weights cannot trigger auto-paper execution.
"""
import math
CAPS={"attack_xg":.12,"defense_xga":.12,"shot_volume":.06,"xg_per_shot":.06,
      "finishing_regression":.035,"form_opponent_adjusted":.05,"home_away":.05,
      "coach_tactical_matchup":.07,"pressing_build_up":.05,"transition":.06,
      "set_piece":.04,"game_state_asymmetry":.05,"lineup":.09,
      "injuries_suspensions":.08,"squad_depth":.06,"tier_gap":.07,
      "rotation_depth_interaction":.06,"rest_fatigue":.04,"travel":.025,
      "motivation":.035,"weather":.02,"human_disagreement":.025,
      "market_sentiment":.035,"market_movement":.035}
def sigmoid(x):return 1/(1+math.exp(-max(-30,min(30,x))))
def logit(p):return math.log(p/(1-p))
def devig(decimal_odds):
    """Return 1X2/totals outcome baseline; all outcomes in same market."""
    if not decimal_odds or any(float(o)<=1 for o in decimal_odds):raise ValueError("full market odds required")
    q=[1/float(o) for o in decimal_odds];z=sum(q);return [v/z for v in q]
def price(market_probability,features,weights=None,calibration=None):
    """Feature values standardized pre-match (z); weights fit on TRAIN ONLY.

    P = sigmoid(logit(p_market)+sum(w_i clip(z_i,-2,2))).
    No arbitrary fixed alpha weights are activated by default.
    """
    if not 0<market_probability<1:raise ValueError("market baseline invalid")
    weights=weights or {}; contributions={};missing=[]
    for k,cap in CAPS.items():
        z=features.get(k)
        if z is None:missing.append(k);continue
        if k not in weights:missing.append(k+":UNFITTED");continue
        contributions[k]=max(-cap,min(cap,float(weights[k])*max(-2,min(2,float(z)))))
    residual=sum(contributions.values())
    raw=sigmoid(logit(market_probability)+residual)
    if calibration and calibration.get("fitted_on_prior_season"):
        a=float(calibration["intercept"]);b=float(calibration["slope"])
        fair=sigmoid(a+b*logit(raw));status="CALIBRATED"
    else:fair=raw;status="RESEARCH_UNCALIBRATED"
    return {"market_prior":market_probability,"residual_log_odds":residual,
            "factor_contributions_log_odds":contributions,"raw_fair":raw,
            "fair_probability":fair,"fair_odds":1/fair,"missing_or_unfitted":missing,
            "status":status,"auto_paper_eligible":status=="CALIBRATED" and bool(contributions)}
def trade(fair,decimal_odds,fee_per_stake=0,slippage_per_stake=0,model_uncertainty_pp=0):
    """Conservative EV: use lower-bound fair, not point estimate."""
    if not 0<fair<1 or decimal_odds<=1:raise ValueError("invalid fair or odds")
    lower=max(0,fair-max(0,model_uncertainty_pp))
    ev=lower*decimal_odds-1-fee_per_stake-slippage_per_stake
    return {"break_even":1/decimal_odds,"lower_bound_fair":lower,"net_ev":ev,
            "qualifies_5pct":ev>=.05}
