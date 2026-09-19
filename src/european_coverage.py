"""European football coverage registry. Provider IDs are opt-in verified, not guessed."""
TOP_FLIGHTS={
"Premier League":"England","Scottish Premiership":"Scotland","Irish Premier Division":"Ireland",
"NIFL Premiership":"Northern Ireland","Welsh Cymru Premier":"Wales",
"La Liga":"Spain","Primeira Liga":"Portugal","Ligue 1":"France","Belgian Pro League":"Belgium",
"Eredivisie":"Netherlands","Bundesliga":"Germany","Austrian Bundesliga":"Austria",
"Swiss Super League":"Switzerland","Serie A":"Italy","Danish Superliga":"Denmark",
"Swedish Allsvenskan":"Sweden","Norwegian Eliteserien":"Norway","Finnish Veikkausliiga":"Finland",
"Icelandic Besta deild":"Iceland","Polish Ekstraklasa":"Poland","Czech First League":"Czechia",
"Slovak Super Liga":"Slovakia","Hungarian NB I":"Hungary","Romanian SuperLiga":"Romania",
"Bulgarian First League":"Bulgaria","Greek Super League":"Greece","Turkish Süper Lig":"Türkiye",
"Croatian HNL":"Croatia","Serbian SuperLiga":"Serbia","Slovenian PrvaLiga":"Slovenia",
"Bosnian Premier League":"Bosnia and Herzegovina","Montenegrin First League":"Montenegro",
"Albanian Kategoria Superiore":"Albania","Kosovo Superleague":"Kosovo",
"North Macedonian First League":"North Macedonia","Cypriot First Division":"Cyprus",
"Ukrainian Premier League":"Ukraine","Moldovan Super Liga":"Moldova",
"Georgian Erovnuli Liga":"Georgia","Armenian Premier League":"Armenia",
"Azerbaijan Premier League":"Azerbaijan","Kazakhstan Premier League":"Kazakhstan",
"Israeli Premier League":"Israel","Maltese Premier League":"Malta",
"Luxembourg National Division":"Luxembourg","Lithuanian A Lyga":"Lithuania",
"Latvian Virsliga":"Latvia","Estonian Meistriliiga":"Estonia",
"Belarusian Premier League":"Belarus","Faroe Islands Premier League":"Faroe Islands",
"Andorran Primera Divisió":"Andorra","Gibraltar Football League":"Gibraltar",
"San Marino Campionato":"San Marino"}
INTERNATIONAL={"UEFA Nations League","UEFA EURO Qualifying","UEFA European Qualifiers"}
CUPS={"UEFA Champions League","UEFA Europa League","UEFA Conference League","EFL/Carabao Cup","FA Cup"}
COVERAGE=set(TOP_FLIGHTS)|INTERNATIONAL|CUPS
# Verify actual provider sport keys from its live catalog before mapping.
VERIFIED_ODDS_KEYS={
"Premier League":"soccer_epl","La Liga":"soccer_spain_la_liga",
"Serie A":"soccer_italy_serie_a","Bundesliga":"soccer_germany_bundesliga",
"Ligue 1":"soccer_france_ligue_one","UEFA Champions League":"soccer_uefa_champs_league",
"UEFA Europa League":"soccer_uefa_europa_league",
"EFL/Carabao Cup":"soccer_england_efl_cup","FA Cup":"soccer_fa_cup"}
def competition_group(name):
 if name in INTERNATIONAL:return "NATIONAL_TEAM"
 if name in CUPS:return "CUP"
 return "DOMESTIC_TOP_FLIGHT" if name in TOP_FLIGHTS else "UNKNOWN"
