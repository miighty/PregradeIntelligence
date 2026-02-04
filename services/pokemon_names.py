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

# Energy types for Energy card detection (basic types)
ENERGY_TYPES: set[str] = {
    "grass", "fire", "water", "lightning", "psychic",
    "fighting", "darkness", "dark", "metal", "steel",
    "fairy", "dragon", "colorless", "normal",
}

# Complete Energy card names (basic + special)
ENERGY_CARD_NAMES: set[str] = {
    # Basic Energy (each type + "Energy" suffix)
    "grass energy", "fire energy", "water energy", "lightning energy",
    "psychic energy", "fighting energy", "darkness energy", "dark energy",
    "metal energy", "steel energy", "fairy energy", "dragon energy",
    "colorless energy", "normal energy",
    # Basic Energy (type only - often OCR'd without "Energy")
    "grass", "fire", "water", "lightning", "psychic",
    "fighting", "darkness", "metal", "fairy", "dragon", "colorless",
    # Special Energy cards (commonly played)
    "double colorless energy", "dce", "double turbo energy",
    "twin energy", "triple acceleration energy", "counter energy",
    "rainbow energy", "multi energy", "blend energy",
    "aurora energy", "capture energy", "coating energy",
    "heat energy", "horror psychic energy", "hiding darkness energy",
    "powerful colorless energy", "speed lightning energy",
    "stone fighting energy", "spiral energy", "unit energy",
    "weakness guard energy", "recycle energy", "warp energy",
    "boost energy", "scramble energy", "react energy",
    "holon energy", "heal energy", "recover energy",
    "double dragon energy", "dangerous energy", "mystery energy",
    "herbal energy", "burning energy", "splash energy",
    "shield energy", "gift energy", "jet energy", "luminous energy",
    "reversal energy", "therapeutic energy", "neo upper energy",
    "legacy energy", "basic energy", "special energy",
    # V-Star / Ace Spec Energy
    "v star energy", "double rainbow energy",
    # Fusion Strike Energy
    "fusion strike energy",
    # Call Energy
    "call energy",
    # Newer special energy
    "v guard energy", "gift energy", "luminous energy",
    "jet energy", "reversal energy", "therapeutic energy",
    "neo upper energy", "legacy energy",
    # Sword & Shield era energy
    "capture energy", "coating energy", "heat energy",
    "horror psychic energy", "hiding darkness energy",
    "powerful colorless energy", "speed lightning energy",
    "stone fighting energy", "aromatic energy",
    "lucky energy", "draw energy", "impact energy",
    "regenerative energy", "modifying energy", "mirage energy",
    # Modern competitive energy
    "double turbo energy", "dte", "dce",
    "basic grass energy", "basic fire energy", "basic water energy",
    "basic lightning energy", "basic psychic energy", "basic fighting energy",
    "basic darkness energy", "basic metal energy", "basic fairy energy",
}

# Trainer card subtypes for Trainer card detection
TRAINER_SUBTYPES: set[str] = {
    "item", "supporter", "stadium", "pokemon tool", "pokémon tool",
    "technical machine", "tm", "ace spec", "acespec",
    "rocket's secret machine", "goldenrod game corner",
}

# Common Trainer card names for validation
# This is a representative list of popular/common trainer cards across sets
TRAINER_CARD_NAMES: set[str] = {
    # Popular Items
    "pokemon catcher", "pokémon catcher", "ultra ball", "nest ball", "quick ball",
    "level ball", "heavy ball", "dive ball", "net ball", "friend ball",
    "great ball", "poke ball", "pokeball", "pokéball", "master ball",
    "timer ball", "repeat ball", "dusk ball", "luxury ball", "beast ball",
    "cherish ball", "dream ball", "safari ball", "sport ball", "moon ball",
    "love ball", "fast ball", "lure ball", "heal ball", "premier ball",
    "rare candy", "switch", "escape rope", "potion", "super potion",
    "hyper potion", "max potion", "full heal", "full restore",
    "revive", "max revive", "super rod", "good rod", "old rod",
    "evolution incense", "lucky egg", "exp share", "rescue stretcher",
    "vs seeker", "vs recorder", "battle compressor", "trainers' mail",
    "acro bike", "mach bike", "bicycle", "roller skates",
    "crushing hammer", "enhanced hammer", "pal pad", "town map",
    "energy retrieval", "energy search", "energy recycler", "energy switch",
    "energy spinner", "energy removal", "super energy removal",
    "computer search", "gust of wind", "item finder", "night maintenance",
    "ancient technical machine", "technical machine evolution",
    "power tablet", "turbo patch", "bug catcher", "pokegear",
    "pokégear 3.0", "rotom phone", "ordinary rod", "hisuian heavy ball",
    "mysterious fossil", "unidentified fossil", "rare fossil",
    "devolution spray", "max elixir", "fighting fury belt",
    "muscle band", "choice band", "expert belt", "float stone",
    "air balloon", "cape of toughness", "big charm", "lucky helmet",
    "rocky helmet", "tool scrapper", "field blower", "startling megaphone",
    "lost vacuum", "super scoop up", "scoop up net", "scoop up cyclone",
    "counter catcher", "boss's orders", "cross switcher", "trekking shoes",
    "battle vip pass", "leafy camo poncho", "earthen vessel",
    "superior energy retrieval", "night stretcher", "buddy buddy poffin",
    "pokémon league headquarters", "ultra space", "mysterious treasure",
    "communication", "pokemon communication", "pokémon communication",
    "tag call", "evolution charm", "rare charm",
    # Popular Supporters
    "professor's research", "professors research", "professor research",
    "professor oak", "professor oak's new theory", "professor elm",
    "professor juniper", "professor sycamore", "professor kukui",
    "professor magnolia", "professor burnet", "professor turo",
    "professor sada", "professor rowan", "professor birch",
    "n", "judge", "marnie", "boss", "boss's orders",
    "cynthia", "steven", "sabrina", "koga", "giovanni",
    "lysandre", "guzma", "looker", "team flare grunt",
    "team rocket grunt", "team magma grunt", "team aqua grunt",
    "team galactic grunt", "team plasma grunt", "team skull grunt",
    "team yell grunt", "team star grunt",
    "pokemon breeder", "pokémon breeder", "pokemon fan club",
    "pokemon trader", "pokémon trader", "pokemon center lady",
    "pokemon ranger", "pokémon ranger", "pokemon collector",
    "hiker", "fisherman", "blacksmith", "hex maniac",
    "psychic", "brock", "misty", "lt surge", "erika",
    "blaine", "janine", "falkner", "bugsy", "whitney",
    "morty", "jasmine", "pryce", "clair", "will",
    "karen", "bruno", "lance", "lorelei", "agatha",
    "brock's grit", "misty's determination", "misty's favor",
    "bill", "mr fuji", "mr briney", "mr stone",
    "rosa", "hau", "hop", "nemona", "arven", "penny",
    "iono", "geeta", "raihan", "gordie", "melony",
    "bea", "allister", "opal", "kabu", "nessa",
    "milo", "leon", "piers", "peonia", "peony",
    "klara", "avery", "mustard", "honey",
    "colress", "team plasma n", "zinnia", "acerola",
    "gladion", "lillie", "lusamine", "faba", "wicke",
    "korrina", "diantha", "malva", "wikstrom", "drasna", "siebold",
    "shauna", "tierno", "trevor", "serena", "calem",
    "skyla", "cheren", "bianca", "alder", "iris",
    "clay", "elesa", "burgh", "lenora", "cilan",
    "volkner", "flint", "bertha", "aaron", "lucian",
    "cheryl", "mira", "riley", "buck", "marley",
    "crasher wake", "maylene", "candice", "fantina", "gardenia",
    "byron", "roark", "cyrus", "team galactic boss",
    "archie", "maxie", "norman", "roxanne", "brawly",
    "wattson", "flannery", "winona", "tate", "liza",
    "juan", "wallace", "sidney", "phoebe", "glacia",
    "drake", "wally",
    "welder", "green's exploration", "caitlin", "oleana",
    "mallow", "lana", "kiawe", "sophocles", "mina",
    "hapu", "olivia", "nanu", "acerola", "molayne",
    "kahili", "hala", "plumeria", "guzma",
    # Popular Stadiums
    "path to the peak", "lost city", "magma basin",
    "training court", "tower of darkness", "tower of waters",
    "rose tower", "turffield stadium", "circhester bath",
    "wyndon stadium", "glimwood tangle", "stow on side",
    "spikemuth", "hulbury", "motostoke", "hammerlocke",
    "giant hearth", "heat factory", "martial arts dojo",
    "wondrous labyrinth", "black market", "shrine of punishment",
    "life forest", "thunder mountain", "viridian forest",
    "pokemon center", "pokémon center", "dimension valley",
    "sky field", "silent lab", "rough seas", "scorched earth",
    "fighting stadium", "steel shelter", "fairy garden",
    "frozen city", "virbank city gym", "tropical beach",
    "computer room", "narrow gym", "celadon city gym",
    "saffron city gym", "vermilion city gym", "pewter city gym",
    "cerulean city gym", "fuchsia city gym", "cinnabar island gym",
    "ecruteak city gym", "goldenrod city gym", "azalea town gym",
    "violet city gym", "olivine city gym", "cianwood city gym",
    "mahogany town gym", "blackthorn city gym", "indigo plateau",
    "pokemon league", "pokémon league",
    "chateau de rosa", "poke stop", "pokéstop",
    "jubilife village", "galaxy headquarters", "obsidian fieldlands",
    "coronet highlands", "cobalt coastlands", "crimson mirelands",
    "alabaster icelands", "temple of sinnoh",
    "artazon", "cascarrafa", "levincia", "medali", "montenevera",
    "area zero", "poco path", "mesagoza", "paldean student",
    # Recent competitive staples (2023-2026)
    "earthen vessel", "super rod", "rescue board", "pal pad",
    "arven", "penny", "giacomo", "mela", "atticus", "ortega", "eri",
    "boss's command", "workers", "iono's intuition", "clavell",
    "scarlet and violet", "temporal forces", "surging sparks",
    "crown zenith", "brilliant stars", "astral radiance",
    "lost origin", "silver tempest", "paradox rift",
    # Popular vintage items (Base Set - Neo era)
    "bill", "item finder", "energy removal", "super energy removal",
    "gust of wind", "professor oak", "lass", "computer search",
    "imposter professor oak", "gambler", "nightly garbage run",
    "sprout tower", "rocket's hideout", "chaos gym",
    "the rocket's trap", "here comes team rocket",
    "pokemon breeder", "pokemon trader", "pokemon center",
    "pokémon breeder", "pokémon trader", "pokémon center",
    "gold berry", "miracle berry", "focus band",
    "berry", "pluspower", "defender", "pokemon march",
    # More gym leaders
    "falkner", "morty", "chuck", "pryce", "clair",
    "bugsy", "jasmine", "whitney", "chuck",
    # Modern staples
    "nest ball", "level ball", "ultra ball", "quick ball",
    "hisuian heavy ball", "heavy ball", "dive ball",
    "great ball", "friend ball", "moon ball", "lure ball",
    "love ball", "fast ball", "safari ball", "sport ball",
    "jet energy", "double turbo energy", "v guard energy",
    "forest seal stone", "beach court", "collapsed stadium",
    "crystal cave", "dark patch", "energy recycler",
    "evolution incense", "fog crystal", "irida",
    "grant", "melony", "raihan", "phoebe", "cheren's care",
    "team yell towel", "team yell's cheer", "tool jammer",
    "choice belt", "air balloon", "cape of toughness",
    "vitality band", "rocky helmet", "big charm",
    "lucky helmet", "exp. share", "exp share",
    # Ace Spec cards
    "computer search", "dowsing machine", "scramble switch",
    "life dew", "victory piece", "g booster", "g scope",
    "master ball", "scoop up cyclone", "rock guard",
    "prime catcher", "hero's cape", "maximum belt",
    "reboot pod", "survival brace", "unfair stamp",
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


def get_energy_card_names() -> set[str]:
    """Return the set of known energy card names."""
    return ENERGY_CARD_NAMES.copy()


def get_trainer_subtypes() -> set[str]:
    """Return the set of trainer subtypes."""
    return TRAINER_SUBTYPES.copy()


def get_trainer_card_names() -> set[str]:
    """Return the set of known trainer card names."""
    return TRAINER_CARD_NAMES.copy()
