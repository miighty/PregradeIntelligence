"""
Comprehensive Pokemon Name Database

Contains all 1025 Pokemon species (Gen 1-9) for card identity validation.
This module provides the complete name database with proper handling of
special characters (é, ', ., etc.) and alternate forms.

IMPORTANT: This data is used for validation ONLY. PreGrade does NOT
act as an authority - it provides advisory identification.
"""

# All 1025 Pokemon species names (normalized lowercase, special chars preserved)
# Organized by generation for maintainability
POKEMON_NAMES_GEN1: set[str] = {
    "bulbasaur", "ivysaur", "venusaur", "charmander", "charmeleon", "charizard",
    "squirtle", "wartortle", "blastoise", "caterpie", "metapod", "butterfree",
    "weedle", "kakuna", "beedrill", "pidgey", "pidgeotto", "pidgeot",
    "rattata", "raticate", "spearow", "fearow", "ekans", "arbok",
    "pikachu", "raichu", "sandshrew", "sandslash", "nidoran", "nidorina",
    "nidoqueen", "nidorino", "nidoking", "clefairy", "clefable", "vulpix",
    "ninetales", "jigglypuff", "wigglytuff", "zubat", "golbat", "oddish",
    "gloom", "vileplume", "paras", "parasect", "venonat", "venomoth",
    "diglett", "dugtrio", "meowth", "persian", "psyduck", "golduck",
    "mankey", "primeape", "growlithe", "arcanine", "poliwag", "poliwhirl",
    "poliwrath", "abra", "kadabra", "alakazam", "machop", "machoke",
    "machamp", "bellsprout", "weepinbell", "victreebel", "tentacool", "tentacruel",
    "geodude", "graveler", "golem", "ponyta", "rapidash", "slowpoke",
    "slowbro", "magnemite", "magneton", "farfetch'd", "farfetchd", "doduo", "dodrio",
    "seel", "dewgong", "grimer", "muk", "shellder", "cloyster",
    "gastly", "haunter", "gengar", "onix", "drowzee", "hypno",
    "krabby", "kingler", "voltorb", "electrode", "exeggcute", "exeggutor",
    "cubone", "marowak", "hitmonlee", "hitmonchan", "lickitung", "koffing",
    "weezing", "rhyhorn", "rhydon", "chansey", "tangela", "kangaskhan",
    "horsea", "seadra", "goldeen", "seaking", "staryu", "starmie",
    "mr. mime", "mr mime", "mrmime", "scyther", "jynx", "electabuzz", "magmar", "pinsir",
    "tauros", "magikarp", "gyarados", "lapras", "ditto", "eevee",
    "vaporeon", "jolteon", "flareon", "porygon", "omanyte", "omastar",
    "kabuto", "kabutops", "aerodactyl", "snorlax", "articuno", "zapdos",
    "moltres", "dratini", "dragonair", "dragonite", "mewtwo", "mew",
}

POKEMON_NAMES_GEN2: set[str] = {
    "chikorita", "bayleef", "meganium", "cyndaquil", "quilava", "typhlosion",
    "totodile", "croconaw", "feraligatr", "sentret", "furret", "hoothoot",
    "noctowl", "ledyba", "ledian", "spinarak", "ariados", "crobat",
    "chinchou", "lanturn", "pichu", "cleffa", "igglybuff", "togepi",
    "togetic", "natu", "xatu", "mareep", "flaaffy", "ampharos",
    "bellossom", "marill", "azumarill", "sudowoodo", "politoed", "hoppip",
    "skiploom", "jumpluff", "aipom", "sunkern", "sunflora", "yanma",
    "wooper", "quagsire", "espeon", "umbreon", "murkrow", "slowking",
    "misdreavus", "unown", "wobbuffet", "girafarig", "pineco", "forretress",
    "dunsparce", "gligar", "steelix", "snubbull", "granbull", "qwilfish",
    "scizor", "shuckle", "heracross", "sneasel", "teddiursa", "ursaring",
    "slugma", "magcargo", "swinub", "piloswine", "corsola", "remoraid",
    "octillery", "delibird", "mantine", "skarmory", "houndour", "houndoom",
    "kingdra", "phanpy", "donphan", "porygon2", "stantler", "smeargle",
    "tyrogue", "hitmontop", "smoochum", "elekid", "magby", "miltank",
    "blissey", "raikou", "entei", "suicune", "larvitar", "pupitar",
    "tyranitar", "lugia", "ho-oh", "hooh", "celebi",
}

POKEMON_NAMES_GEN3: set[str] = {
    "treecko", "grovyle", "sceptile", "torchic", "combusken", "blaziken",
    "mudkip", "marshtomp", "swampert", "poochyena", "mightyena", "zigzagoon",
    "linoone", "wurmple", "silcoon", "beautifly", "cascoon", "dustox",
    "lotad", "lombre", "ludicolo", "seedot", "nuzleaf", "shiftry",
    "taillow", "swellow", "wingull", "pelipper", "ralts", "kirlia",
    "gardevoir", "surskit", "masquerain", "shroomish", "breloom", "slakoth",
    "vigoroth", "slaking", "nincada", "ninjask", "shedinja", "whismur",
    "loudred", "exploud", "makuhita", "hariyama", "azurill", "nosepass",
    "skitty", "delcatty", "sableye", "mawile", "aron", "lairon",
    "aggron", "meditite", "medicham", "electrike", "manectric", "plusle",
    "minun", "volbeat", "illumise", "roselia", "gulpin", "swalot",
    "carvanha", "sharpedo", "wailmer", "wailord", "numel", "camerupt",
    "torkoal", "spoink", "grumpig", "spinda", "trapinch", "vibrava",
    "flygon", "cacnea", "cacturne", "swablu", "altaria", "zangoose",
    "seviper", "lunatone", "solrock", "barboach", "whiscash", "corphish",
    "crawdaunt", "baltoy", "claydol", "lileep", "cradily", "anorith",
    "armaldo", "feebas", "milotic", "castform", "kecleon", "shuppet",
    "banette", "duskull", "dusclops", "tropius", "chimecho", "absol",
    "wynaut", "snorunt", "glalie", "spheal", "sealeo", "walrein",
    "clamperl", "huntail", "gorebyss", "relicanth", "luvdisc", "bagon",
    "shelgon", "salamence", "beldum", "metang", "metagross", "regirock",
    "regice", "registeel", "latias", "latios", "kyogre", "groudon",
    "rayquaza", "jirachi", "deoxys",
}

POKEMON_NAMES_GEN4: set[str] = {
    "turtwig", "grotle", "torterra", "chimchar", "monferno", "infernape",
    "piplup", "prinplup", "empoleon", "starly", "staravia", "staraptor",
    "bidoof", "bibarel", "kricketot", "kricketune", "shinx", "luxio",
    "luxray", "budew", "roserade", "cranidos", "rampardos", "shieldon",
    "bastiodon", "burmy", "wormadam", "mothim", "combee", "vespiquen",
    "pachirisu", "buizel", "floatzel", "cherubi", "cherrim", "shellos",
    "gastrodon", "ambipom", "drifloon", "drifblim", "buneary", "lopunny",
    "mismagius", "honchkrow", "glameow", "purugly", "chingling", "stunky",
    "skuntank", "bronzor", "bronzong", "bonsly", "mime jr.", "mime jr", "mimejr",
    "happiny", "chatot", "spiritomb", "gible", "gabite", "garchomp",
    "munchlax", "riolu", "lucario", "hippopotas", "hippowdon", "skorupi",
    "drapion", "croagunk", "toxicroak", "carnivine", "finneon", "lumineon",
    "mantyke", "snover", "abomasnow", "weavile", "magnezone", "lickilicky",
    "rhyperior", "tangrowth", "electivire", "magmortar", "togekiss", "yanmega",
    "leafeon", "glaceon", "gliscor", "mamoswine", "porygon-z", "porygonz",
    "gallade", "probopass", "dusknoir", "froslass", "rotom", "uxie",
    "mesprit", "azelf", "dialga", "palkia", "heatran", "regigigas",
    "giratina", "cresselia", "phione", "manaphy", "darkrai", "shaymin",
    "arceus",
}

POKEMON_NAMES_GEN5: set[str] = {
    "victini", "snivy", "servine", "serperior", "tepig", "pignite",
    "emboar", "oshawott", "dewott", "samurott", "patrat", "watchog",
    "lillipup", "herdier", "stoutland", "purrloin", "liepard", "pansage",
    "simisage", "pansear", "simisear", "panpour", "simipour", "munna",
    "musharna", "pidove", "tranquill", "unfezant", "blitzle", "zebstrika",
    "roggenrola", "boldore", "gigalith", "woobat", "swoobat", "drilbur",
    "excadrill", "audino", "timburr", "gurdurr", "conkeldurr", "tympole",
    "palpitoad", "seismitoad", "throh", "sawk", "sewaddle", "swadloon",
    "leavanny", "venipede", "whirlipede", "scolipede", "cottonee", "whimsicott",
    "petilil", "lilligant", "basculin", "sandile", "krokorok", "krookodile",
    "darumaka", "darmanitan", "maractus", "dwebble", "crustle", "scraggy",
    "scrafty", "sigilyph", "yamask", "cofagrigus", "tirtouga", "carracosta",
    "archen", "archeops", "trubbish", "garbodor", "zorua", "zoroark",
    "minccino", "cinccino", "gothita", "gothorita", "gothitelle", "solosis",
    "duosion", "reuniclus", "ducklett", "swanna", "vanillite", "vanillish",
    "vanilluxe", "deerling", "sawsbuck", "emolga", "karrablast", "escavalier",
    "foongus", "amoonguss", "frillish", "jellicent", "alomomola", "joltik",
    "galvantula", "ferroseed", "ferrothorn", "klink", "klang", "klinklang",
    "tynamo", "eelektrik", "eelektross", "elgyem", "beheeyem", "litwick",
    "lampent", "chandelure", "axew", "fraxure", "haxorus", "cubchoo",
    "beartic", "cryogonal", "shelmet", "accelgor", "stunfisk", "mienfoo",
    "mienshao", "druddigon", "golett", "golurk", "pawniard", "bisharp",
    "bouffalant", "rufflet", "braviary", "vullaby", "mandibuzz", "heatmor",
    "durant", "deino", "zweilous", "hydreigon", "larvesta", "volcarona",
    "cobalion", "terrakion", "virizion", "tornadus", "thundurus", "reshiram",
    "zekrom", "landorus", "kyurem", "keldeo", "meloetta", "genesect",
}

POKEMON_NAMES_GEN6: set[str] = {
    "chespin", "quilladin", "chesnaught", "fennekin", "braixen", "delphox",
    "froakie", "frogadier", "greninja", "bunnelby", "diggersby", "fletchling",
    "fletchinder", "talonflame", "scatterbug", "spewpa", "vivillon", "litleo",
    "pyroar", "flabébé", "flabebe", "floette", "florges", "skiddo", "gogoat",
    "pancham", "pangoro", "furfrou", "espurr", "meowstic", "honedge",
    "doublade", "aegislash", "spritzee", "aromatisse", "swirlix", "slurpuff",
    "inkay", "malamar", "binacle", "barbaracle", "skrelp", "dragalge",
    "clauncher", "clawitzer", "helioptile", "heliolisk", "tyrunt", "tyrantrum",
    "amaura", "aurorus", "sylveon", "hawlucha", "dedenne", "carbink",
    "goomy", "sliggoo", "goodra", "klefki", "phantump", "trevenant",
    "pumpkaboo", "gourgeist", "bergmite", "avalugg", "noibat", "noivern",
    "xerneas", "yveltal", "zygarde", "diancie", "hoopa", "volcanion",
}

POKEMON_NAMES_GEN7: set[str] = {
    "rowlet", "dartrix", "decidueye", "litten", "torracat", "incineroar",
    "popplio", "brionne", "primarina", "pikipek", "trumbeak", "toucannon",
    "yungoos", "gumshoos", "grubbin", "charjabug", "vikavolt", "crabrawler",
    "crabominable", "oricorio", "cutiefly", "ribombee", "rockruff", "lycanroc",
    "wishiwashi", "mareanie", "toxapex", "mudbray", "mudsdale", "dewpider",
    "araquanid", "fomantis", "lurantis", "morelull", "shiinotic", "salandit",
    "salazzle", "stufful", "bewear", "bounsweet", "steenee", "tsareena",
    "comfey", "oranguru", "passimian", "wimpod", "golisopod", "sandygast",
    "palossand", "pyukumuku", "type: null", "type null", "typenull", "silvally",
    "minior", "komala", "turtonator", "togedemaru", "mimikyu", "bruxish",
    "drampa", "dhelmise", "jangmo-o", "jangmoo", "hakamo-o", "hakamoo",
    "kommo-o", "kommoo", "tapu koko", "tapukoko", "tapu lele", "tapulele",
    "tapu bulu", "tapubulu", "tapu fini", "tapufini", "cosmog", "cosmoem",
    "solgaleo", "lunala", "nihilego", "buzzwole", "pheromosa", "xurkitree",
    "celesteela", "kartana", "guzzlord", "necrozma", "magearna", "marshadow",
    "poipole", "naganadel", "stakataka", "blacephalon", "zeraora", "meltan", "melmetal",
}

POKEMON_NAMES_GEN8: set[str] = {
    "grookey", "thwackey", "rillaboom", "scorbunny", "raboot", "cinderace",
    "sobble", "drizzile", "inteleon", "skwovet", "greedent", "rookidee",
    "corvisquire", "corviknight", "blipbug", "dottler", "orbeetle", "nickit",
    "thievul", "gossifleur", "eldegoss", "wooloo", "dubwool", "chewtle",
    "drednaw", "yamper", "boltund", "rolycoly", "carkol", "coalossal",
    "applin", "flapple", "appletun", "silicobra", "sandaconda", "cramorant",
    "arrokuda", "barraskewda", "toxel", "toxtricity", "sizzlipede", "centiskorch",
    "clobbopus", "grapploct", "sinistea", "polteageist", "hatenna", "hattrem",
    "hatterene", "impidimp", "morgrem", "grimmsnarl", "obstagoon", "perrserker",
    "cursola", "sirfetch'd", "sirfetchd", "mr. rime", "mr rime", "mrrime",
    "runerigus", "milcery", "alcremie", "falinks", "pincurchin", "snom",
    "frosmoth", "stonjourner", "eiscue", "indeedee", "morpeko", "cufant",
    "copperajah", "dracozolt", "arctozolt", "dracovish", "arctovish", "duraludon",
    "dreepy", "drakloak", "dragapult", "zacian", "zamazenta", "eternatus",
    "kubfu", "urshifu", "zarude", "regieleki", "regidrago", "glastrier",
    "spectrier", "calyrex", "wyrdeer", "kleavor", "ursaluna", "basculegion",
    "sneasler", "overqwil", "enamorus",
}

POKEMON_NAMES_GEN9: set[str] = {
    "sprigatito", "floragato", "meowscarada", "fuecoco", "crocalor", "skeledirge",
    "quaxly", "quaxwell", "quaquaval", "lechonk", "oinkologne", "tarountula",
    "spidops", "nymble", "lokix", "pawmi", "pawmo", "pawmot",
    "tandemaus", "maushold", "fidough", "dachsbun", "smoliv", "dolliv",
    "arboliva", "squawkabilly", "nacli", "naclstack", "garganacl", "charcadet",
    "armarouge", "ceruledge", "tadbulb", "bellibolt", "wattrel", "kilowattrel",
    "maschiff", "mabosstiff", "shroodle", "grafaiai", "bramblin", "brambleghast",
    "toedscool", "toedscruel", "klawf", "capsakid", "scovillain", "rellor",
    "rabsca", "flittle", "espathra", "tinkatink", "tinkatuff", "tinkaton",
    "wiglett", "wugtrio", "bombirdier", "finizen", "palafin", "varoom",
    "revavroom", "cyclizar", "orthworm", "glimmet", "glimmora", "greavard",
    "houndstone", "flamigo", "cetoddle", "cetitan", "veluza", "dondozo",
    "tatsugiri", "annihilape", "clodsire", "farigiraf", "dudunsparce", "kingambit",
    "great tusk", "greattusk", "scream tail", "screamtail", "brute bonnet", "brutebonnet",
    "flutter mane", "fluttermane", "slither wing", "slitherwing", "sandy shocks", "sandyshocks",
    "iron treads", "irontreads", "iron bundle", "ironbundle", "iron hands", "ironhands",
    "iron jugulis", "ironjugulis", "iron moth", "ironmoth", "iron thorns", "ironthorns",
    "frigibax", "arctibax", "baxcalibur", "gimmighoul", "gholdengo", "wo-chien", "wochien",
    "chien-pao", "chienpao", "ting-lu", "tinglu", "chi-yu", "chiyu",
    "roaring moon", "roaringmoon", "iron valiant", "ironvaliant", "koraidon", "miraidon",
    "walking wake", "walkingwake", "iron leaves", "ironleaves", "dipplin", "poltchageist",
    "sinistcha", "okidogi", "munkidori", "fezandipiti", "ogerpon", "archaludon",
    "hydrapple", "gouging fire", "gougingfire", "raging bolt", "ragingbolt",
    "iron boulder", "ironboulder", "iron crown", "ironcrown", "terapagos", "pecharunt",
}

# Combined set of all Pokemon names
ALL_POKEMON_NAMES: set[str] = (
    POKEMON_NAMES_GEN1 |
    POKEMON_NAMES_GEN2 |
    POKEMON_NAMES_GEN3 |
    POKEMON_NAMES_GEN4 |
    POKEMON_NAMES_GEN5 |
    POKEMON_NAMES_GEN6 |
    POKEMON_NAMES_GEN7 |
    POKEMON_NAMES_GEN8 |
    POKEMON_NAMES_GEN9
)

# Owner prefixes (gym leaders, team members, etc.)
OWNER_PREFIXES: set[str] = {
    # Kanto Gym Leaders
    "brock's", "misty's", "lt. surge's", "lt surge's", "surge's",
    "erika's", "koga's", "sabrina's", "blaine's", "giovanni's",
    # Johto Gym Leaders
    "falkner's", "bugsy's", "whitney's", "morty's", "chuck's",
    "jasmine's", "pryce's", "clair's",
    # Team Rocket
    "rocket's", "team rocket's",
    # Team Aqua / Team Magma
    "team aqua's", "aqua's", "team magma's", "magma's",
    # Team Plasma
    "team plasma",
    # Other trainers
    "lance's", "lorelei's", "bruno's", "agatha's", "will's", "karen's",
}

# Variant prefixes (Dark, Light, regional forms, etc.)
VARIANT_PREFIXES: set[str] = {
    # Classic variants
    "dark", "light", "shining", "crystal",
    # Regional forms
    "alolan", "galarian", "hisuian", "paldean",
    # Special variants
    "radiant", "amazing",
    # Temporal variants (Scarlet/Violet)
    "ancient", "future",
    # Delta Species
    "delta", "δ",
    # Shadow (Pokemon Colosseum/XD)
    "shadow",
}

# Mechanic suffixes (card mechanics/rules)
MECHANIC_SUFFIXES: set[str] = {
    # Classic EX era (lowercase)
    "ex",
    # Black & White / XY era (uppercase - treated same after normalization)
    # Sun & Moon GX
    "gx",
    # Sword & Shield V series
    "v", "vmax", "vstar", "v-union", "vunion",
    # Diamond & Pearl
    "lv.x", "lvx", "lv x",
    # HGSS / BW era
    "prime", "legend",
    # XY era
    "break", "mega", "m",
    # Special mechanics
    "sp", "gl", "fb", "c", "g", "4",
    # Star Pokemon
    "star", "☆", "◇",
    # TAG TEAM
    "tag team", "tagteam",
    # Tera (Scarlet/Violet)
    "tera",
    # Battle Styles
    "single strike", "singlestrike",
    "rapid strike", "rapidstrike",
    "fusion strike", "fusionstrike",
    # Prism Star
    "prism star", "prismstar",
}

# Energy types for Energy card detection
ENERGY_TYPES: set[str] = {
    "grass", "fire", "water", "lightning", "psychic",
    "fighting", "darkness", "dark", "metal", "steel",
    "fairy", "dragon", "colorless", "normal",
}

# Trainer card subtypes for Trainer card detection
TRAINER_SUBTYPES: set[str] = {
    "item", "supporter", "stadium", "pokemon tool", "pokémon tool",
    "technical machine", "tm", "ace spec", "acespec",
    "rocket's secret machine", "goldenrod game corner",
}


def get_all_pokemon_names() -> set[str]:
    """Return the complete set of all Pokemon names."""
    return ALL_POKEMON_NAMES.copy()


def get_owner_prefixes() -> set[str]:
    """Return the set of owner prefixes."""
    return OWNER_PREFIXES.copy()


def get_variant_prefixes() -> set[str]:
    """Return the set of variant prefixes."""
    return VARIANT_PREFIXES.copy()


def get_mechanic_suffixes() -> set[str]:
    """Return the set of mechanic suffixes."""
    return MECHANIC_SUFFIXES.copy()


def get_energy_types() -> set[str]:
    """Return the set of energy types."""
    return ENERGY_TYPES.copy()


def get_trainer_subtypes() -> set[str]:
    """Return the set of trainer subtypes."""
    return TRAINER_SUBTYPES.copy()
