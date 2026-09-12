"""North American place negatives for the DCT search campaign.

DCT sells European and other long-haul coach tours to Canadians. Queries that
name a North American place are almost always local intent: day trips, city
bus tours, domestic holidays. This module holds the terms that exclude them.

Two lists are fed from here:

* ``DCT | Global Country Negatives`` gains the Canada replacement terms, US
  states, Canadian destination provinces and regions, and well-known parks.
  It already holds ``USA`` / ``United States`` / ``Mexico``. The bare broad
  ``Canada`` is removed by the same change - see CANADA_BROAD_REMOVAL below.
* ``DCT | Global City Negatives`` (new) holds cities only.

Match-type rules, applied by apply_google_ads_place_negatives.py:

* A single word is BROAD. It blocks any query containing that word.
* A multi-word term is PHRASE. It blocks only the contiguous phrase, so
  ``new york`` cannot touch a query about York in England.
* Anything in COLLISION_EXCLUDED is never used as a bare broad term. Those
  are Canadian and US places that share a name with an approved destination
  (London, Windsor, Cambridge, Paris, Naples...). Where the Canadian city is
  worth blocking anyway it appears below qualified by its province instead.

Why the broad ``Canada`` is removed: negative keywords match the search
query, not the searcher's location. A campaign that targets Canada and
carries ``Canada`` as a broad negative blocks ``trafalgar tours canada`` -
the exact query its own headline "Trafalgar Tours Canada" was written for.
The phrase terms below still exclude tours *of* Canada without doing that.

Residence provinces (Ontario, Quebec, Alberta, Saskatchewan, Manitoba) were
left out on 11 Sep 2026 on the theory that a broad ``ontario`` would block
``[brand] tours ontario`` from a prospect. The first search-terms report
(12 Sep) showed the opposite in practice: every province query was local
product - ``day trips for seniors in ontario``, ``bus tours to quebec``,
``saskatchewan bus tours for seniors`` - and no brand-plus-province query
appeared at all. They are now in, broad, at Ben's call. British Columbia
stays out because its abbreviation ``bc`` is too short to be safe broad and
the full name never appeared.

Also fed from here since 12 Sep 2026:

* ``DCT | Competitor Tour Operators`` (new) - Canadian domestic coach
  companies and Europe-direct competitors seen in the search terms.
* Intent exclusions (``near me``, ``day trip``, ``tour bus``...) go to
  ``DCT | Global Search Exclusions``.
"""
from __future__ import annotations

# --- country list: Canada broad -> phrase replacement -------------------

CANADA_BROAD_REMOVAL = "Canada"

# All PHRASE. Contiguous "canada <noun>" or "<verb> of canada" patterns only,
# so brand-plus-market queries like "globus tours canada" still serve.
CANADA_PHRASES = [
    "canada tours", "canada tour", "tours of canada", "tour of canada",
    "canada coach tours", "canada coach tour", "canada bus tours",
    "canada bus tour", "canada vacation", "canada vacations",
    "canada holiday", "canada holidays", "canada trip", "canada trips",
    "canada rail", "canada train", "cross canada", "across canada",
    "eastern canada", "western canada", "atlantic canada",
    "canadian rockies", "canadian rockies tour", "canadian maritimes",
]

# Destination provinces, regions and landmarks. Single words are BROAD.
CANADA_REGIONS = [
    "rockies", "rocky mountaineer", "banff", "jasper", "lake louise",
    "whistler", "tofino", "okanagan", "niagara", "muskoka", "algonquin",
    "yukon", "maritimes", "newfoundland", "labrador", "nova scotia",
    "new brunswick", "prince edward island", "cabot trail", "gaspe",
    "quebec city", "northwest territories", "nunavut",
    # residence provinces - added 12 Sep 2026 from search-terms evidence
    "ontario", "quebec", "alberta", "saskatchewan", "manitoba", "pei",
]

# --- country list: US states and national parks ----------------------------

US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "hawaii", "idaho", "illinois",
    "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "north carolina", "south carolina",
    "north dakota", "south dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "tennessee", "texas", "utah", "vermont",
    "virginia", "west virginia", "wisconsin", "wyoming", "new england",
    "puerto rico", "us virgin islands",
]
# Excluded from US_STATES on purpose: "washington" (needs the DC/state
# qualifier - see US_CITIES) and "georgia" (also a country; not approved
# either, but a bare broad on a country name is the pattern being removed).

US_PARKS = [
    "yellowstone", "grand canyon", "yosemite", "zion national park",
    "bryce canyon", "glacier national park", "great smoky mountains",
    "everglades", "acadia national park", "rocky mountain national park",
    "mount rushmore", "monument valley", "death valley", "sequoia",
]

# --- city list --------------------------------------------------------------

CANADA_CITIES = [
    # Major
    "toronto", "montreal", "vancouver", "calgary", "edmonton", "ottawa",
    "winnipeg", "halifax", "mississauga", "brampton", "markham", "vaughan",
    "hamilton", "kitchener", "laval", "gatineau", "longueuil", "saskatoon",
    "regina", "kelowna", "barrie", "oshawa", "sherbrooke", "guelph",
    "kingston", "moncton", "fredericton", "charlottetown", "burnaby",
    "saanich", "abbotsford", "coquitlam", "brantford", "sarnia", "belleville",
    "orillia", "timmins", "welland", "whitehorse", "yellowknife", "chilliwack",
    "pickering", "lunenburg", "antigonish", "kamloops", "nanaimo",
    "lethbridge", "sudbury", "oakville", "burlington",
    # Multi-word (phrase)
    "st johns", "saint john", "thunder bay", "red deer", "medicine hat",
    "prince george", "sault ste marie", "st catharines", "north bay",
    "owen sound", "grande prairie", "fort mcmurray", "sherwood park",
    "st albert", "maple ridge", "port coquitlam", "richmond hill",
    "new glasgow", "niagara falls", "niagara on the lake",
    # Name-collision cities, qualified by province so they stay safe
    "london ontario", "windsor ontario", "waterloo ontario",
    "cambridge ontario", "peterborough ontario", "stratford ontario",
    "whitby ontario", "newmarket ontario", "milton ontario",
    "chatham ontario", "cornwall ontario", "woodstock ontario",
    "paris ontario", "perth ontario", "brussels ontario", "zurich ontario",
    "dresden ontario", "victoria bc", "surrey bc", "richmond bc", "delta bc",
    "langley bc", "new westminster", "truro nova scotia",
    "liverpool nova scotia", "yarmouth nova scotia", "sydney nova scotia",
    "inverness nova scotia",
]

US_CITIES = [
    # Single-word (broad)
    "nyc", "chicago", "houston", "phoenix", "philadelphia", "dallas", "austin",
    "jacksonville", "columbus", "charlotte", "indianapolis", "seattle",
    "denver", "boston", "nashville", "detroit", "portland", "louisville",
    "baltimore", "milwaukee", "albuquerque", "tucson", "fresno",
    "sacramento", "atlanta", "miami", "orlando", "tampa", "cleveland",
    "pittsburgh", "cincinnati", "minneapolis", "honolulu", "anchorage",
    "buffalo", "savannah", "charleston", "branson", "sedona", "scottsdale",
    "boulder", "aspen", "vail", "reno", "oakland", "anaheim", "malibu",
    "monterey", "pasadena", "hollywood", "madison", "montgomery",
    "chattanooga", "knoxville", "lexington", "greenville", "asheville",
    "williamsburg", "spokane", "tacoma", "boise", "fargo", "bismarck",
    "billings", "bozeman", "cheyenne", "taos", "galveston", "amarillo",
    "lubbock", "hartford", "providence", "nantucket", "adirondacks",
    "catskills", "brooklyn", "manhattan", "bronx", "annapolis", "gettysburg",
    "hershey", "wilmington", "omaha", "tulsa", "raleigh", "daytona",
    # Multi-word (phrase)
    "new york", "los angeles", "san antonio", "san diego", "san jose",
    "fort worth", "san francisco", "washington dc", "washington state",
    "las vegas", "kansas city", "new orleans", "st louis", "saint louis",
    "salt lake city", "myrtle beach", "key west", "palm springs",
    "santa fe", "napa valley", "cape cod", "oklahoma city", "richmond va",
    "richmond virginia", "virginia beach", "san juan", "fort lauderdale",
    "west palm beach", "palm beach", "st augustine", "st petersburg florida",
    "colorado springs", "lake tahoe", "long beach", "santa barbara",
    "santa monica", "big sur", "san luis obispo", "beverly hills",
    "grand rapids", "ann arbor", "des moines", "little rock", "baton rouge",
    "hilton head", "outer banks", "sioux falls", "jackson hole", "el paso",
    "corpus christi", "south padre", "new haven", "newport rhode island",
    "marthas vineyard", "bar harbor", "white mountains", "lake placid",
    "hudson valley", "finger lakes", "long island", "staten island",
    "atlantic city", "ocean city", "cape may", "niagara falls ny",
    "memphis tennessee", "alexandria virginia", "birmingham alabama",
    "lancaster pennsylvania", "manchester new hampshire", "york pennsylvania",
    "cambridge massachusetts", "santa cruz california", "columbia south carolina",
]

# Places NOT used as bare broad terms, with the approved-destination or
# common-word collision that rules each one out. Kept as documentation and
# as the validation set the apply tool checks every candidate against.
COLLISION_EXCLUDED = {
    "london": "England",
    "york": "England (also blocks 'new york' only via phrase)",
    "windsor": "Windsor Castle, England",
    "cambridge": "England",
    "peterborough": "England",
    "stratford": "Stratford-upon-Avon, England",
    "whitby": "England",
    "newmarket": "England",
    "milton": "Milton Keynes, England",
    "chatham": "England",
    "cornwall": "England",
    "woodstock": "England",
    "waterloo": "Belgium (Waterloo battlefield tours)",
    "paris": "France",
    "perth": "Scotland",
    "brussels": "Belgium",
    "zurich": "Switzerland",
    "dresden": "Germany",
    "truro": "Cornwall, England",
    "liverpool": "England",
    "yarmouth": "England",
    "sydney": "Australia (not approved, but bare country/city pattern)",
    "inverness": "Scotland",
    "victoria": "Victoria Falls / Lake Victoria, Africa",
    "surrey": "England",
    "richmond": "Richmond upon Thames, England",
    "delta": "Nile Delta, Egypt; also a common word",
    "langley": "England",
    "westminster": "England",
    "memphis": "Ancient Memphis, Egypt (Nile itineraries)",
    "alexandria": "Egypt",
    "birmingham": "England",
    "lancaster": "England",
    "manchester": "England",
    "santa cruz": "Santa Cruz de Tenerife, Spain",
    "columbia": "would also match 'british columbia' - handled by province rule",
    "naples": "Italy",
    "venice": "Italy",
    "florence": "Italy",
    "rome": "Italy",
    "athens": "Greece",
    "dublin": "Ireland",
    "lisbon": "Portugal",
    "vienna": "Austria",
    "berlin": "Germany",
    "geneva": "Switzerland",
    "toledo": "Spain",
    "valencia": "Spain",
    "granada": "Spain",
    "nice": "France; also a common word",
    "split": "Croatia; also a common word",
    "bath": "England; also a common word",
    "kent": "England",
    "oxford": "England",
    "brighton": "England",
    "dover": "England",
    "lincoln": "England",
    "durham": "England",
    "essex": "England",
    "norfolk": "England",
    "sussex": "England",
    "wellington": "New Zealand; common surname",
    "ajax": "common word / brand",
    "mobile": "common word",
    "queens": "common word",
    "georgia": "also a country",
    "washington": "needs dc/state qualifier",
    "hanover": "Germany",
    "glasgow": "Scotland ('new glasgow' phrase is fine)",
}


# --- competitor list ---------------------------------------------------------
# Every one appeared in the search-terms report of 12 Sep 2026. Domestic
# day-trip and coach companies, plus operators selling Europe direct that DCT
# does not resell. Add to this as new ones show up.
COMPETITOR_OPERATORS = [
    "great canadian", "front line", "collette", "approach tours",
    "comfort tours", "go ahead", "exoticca", "rabbies", "caa", "taipan",
    "protours", "fehrway", "wnax", "concorde", "concord tours", "maple leaf",
    "diamond tours", "collins tours", "atlantic tours", "jump in travel",
    "tours of distinction", "shoptravel", "shorttrips", "salem",
    # 12 Sep (second report): bus-ticketing and more domestic operators
    "flixbus", "senior discovery", "dreamtour", "sunrise tours",
    "west world", "matrix tours", "stewart travel",
]

# --- intent exclusions (search-exclusion list) -------------------------------
# Query shapes that are never a coach-tour buyer. ``tour bus`` as a phrase
# does NOT match ``bus tour`` - order matters, and that is the point.
INTENT_EXCLUSIONS = [
    "near me", "day trip", "day trips", "tour bus", "schedule", "reviews",
    "tour companies", "long stay", "free", "heathrow", "airport",
    # Google negatives do NOT match plurals or close variants. The list had
    # "complaint" and "river cruise" and still let "cosmos travel reviews
    # complaints" and "trafalgar river cruises" through. Both forms needed.
    "complaints", "review", "river cruises",
    # bus-ticket buyers (FlixBus/Greyhound intent) and navigational queries
    # for the operator's own site ("trafalgar com", "globus com").
    "ticket", "tickets", "website", "login", "com",
]


def _typed(terms: list[str]) -> list[tuple[str, str]]:
    return [(t, "PHRASE" if " " in t else "BROAD") for t in terms]


def competitor_terms() -> list[tuple[str, str]]:
    return _typed(COMPETITOR_OPERATORS)


def intent_terms() -> list[tuple[str, str]]:
    return _typed(INTENT_EXCLUSIONS)


def canada_replacement_terms() -> list[tuple[str, str]]:
    return [(t, "PHRASE") for t in CANADA_PHRASES] + [
        (t, "PHRASE" if " " in t else "BROAD") for t in CANADA_REGIONS
    ]


def country_list_additions() -> list[tuple[str, str]]:
    """Everything added to the country list. Bare Canada is removed separately."""
    return (
        canada_replacement_terms()
        + [(t, "PHRASE" if " " in t else "BROAD") for t in US_STATES]
        + [(t, "PHRASE" if " " in t else "BROAD") for t in US_PARKS]
    )


def city_list_terms() -> list[tuple[str, str]]:
    return [
        (t, "PHRASE" if " " in t else "BROAD")
        for t in CANADA_CITIES + US_CITIES
    ]
