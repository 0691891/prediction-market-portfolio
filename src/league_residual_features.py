"""Competition-aware residual-alpha feature design; hypotheses, NOT fitted alpha."""
import math
from european_coverage import TOP_FLIGHTS,INTERNATIONAL,competition_group
FEATURES={
 "league_goal_environment":"Rolling league xG/goals baseline vs Europe, prior matches only",
 "league_draw_rate":"Rolling 1X2 draw base rate with shrinkage",
 "league_home_advantage":"Rolling home effect adjusted for opponent strength",
 "league_goal_dispersion":"Prior goal variance / mean; test overdispersion vs Poisson",
 "league_market_margin":"Contemporaneous 1X2 book overround and coverage",
 "league_market_depth":"Observed books/quote spread, not assumed liquidity",
 "league_style_matchup":"Predeclared pressing, buildup, transition and set-piece interaction",
 "league_schedule_congestion":"Rest, travel and continental competition burden",
 "league_squad_depth":"Lineup shock interacted with prior measured replacement strength",
 "league_referee_penalties":"Prior referee/team penalty and card tendency if PIT available",
 "league_weather_pitch":"Weather, altitude and surface when observed before entry",
 "league_season_phase":"Predeclared stage, relegation/title stakes, winter/summer season",
 "national_team_cohesion":"Prior minutes together and coach tenure, no invented chemistry",
 "national_team_callups":"Verified squad withdrawals and availability at snapshot",
 "national_team_travel":"International travel/rest and neutral venue",
 "national_team_tier_gap":"Opponent-adjusted national-team strength",
 "national_team_group_incentive":"Qualification/promotion/relegation scenario as of snapshot",
 "competition_format_epoch":"Historical rules and tournament phase; never apply 2028/29 rules to 2026/27",
}
# Descriptive league hypotheses to test, NOT blanket claims about all teams.
HYPOTHESES={
 "Premier League":["transition","schedule_congestion","squad_depth"],
 "La Liga":["possession_matchup","home_advantage","draw_rate"],
 "Serie A":["game_state","defensive_matchup","draw_rate"],
 "Bundesliga":["transition","goal_dispersion","high_line"],
 "Ligue 1":["tier_gap","squad_depth","transition"],
 "Eredivisie":["goal_environment","goal_dispersion","tier_gap"],
 "Primeira Liga":["tier_gap","home_advantage","market_depth"],
 "Scottish Premiership":["tier_gap","squad_depth","market_depth"],
 "Turkish Süper Lig":["home_advantage","referee_penalties","market_depth"],
 "Norwegian Eliteserien":["summer_calendar","weather_pitch","travel"],
 "Swedish Allsvenskan":["summer_calendar","weather_pitch","travel"],
 "Finnish Veikkausliiga":["summer_calendar","weather_pitch","market_depth"],
 "UEFA Nations League":["national_team_tier_gap","national_team_cohesion","national_team_group_incentive","competition_format_epoch"],
 "UEFA EURO Qualifying":["national_team_tier_gap","national_team_callups","national_team_group_incentive","competition_format_epoch"],
}
def design(name):
 return {"competition":name,"group":competition_group(name),
  "hypotheses_not_trained":HYPOTHESES.get(name,["goal_environment","home_advantage","draw_rate","market_depth","season_phase"]),
  "pooling":"global residual + competition group + shrinkage-adjusted league deviations",
  "training_gate":"no coefficient activated without adequate PIT coverage and chronological league/group holdout"}
