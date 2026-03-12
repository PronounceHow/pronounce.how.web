#!/usr/bin/env python3
"""
categorize_words.py

Adds a "categories" field to word JSON files based on:
  1. Keyword suffix matching (e.g., -itis, -ectomy -> medical)
  2. Curated word lists per category
  3. Context sentence analysis (if the field exists)

A word can belong to multiple categories.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------
DATA_DIR = Path("/home/solcal/pronounceHow/pronounce-how-data/data/words")

# ---------------------------------------------------------------------------
# 1. SUFFIX RULES  (suffix -> list of categories)
#    Each entry is (suffix, [categories])
# ---------------------------------------------------------------------------
SUFFIX_RULES = [
    # Medical suffixes
    ("itis", ["medical"]),
    ("osis", ["medical"]),
    ("emia", ["medical"]),
    ("aemia", ["medical"]),
    ("ectomy", ["medical"]),
    ("otomy", ["medical"]),
    ("ostomy", ["medical"]),
    ("algia", ["medical"]),
    ("pathy", ["medical"]),
    ("plasty", ["medical"]),
    ("scopy", ["medical"]),
    ("rrhagia", ["medical"]),
    ("rrhoea", ["medical"]),
    ("rrhea", ["medical"]),
    ("trophy", ["medical"]),
    ("penia", ["medical"]),
    ("megaly", ["medical"]),
    ("malacia", ["medical"]),
    ("cyte", ["medical", "science"]),
    ("ectasia", ["medical"]),

    # Science suffixes
    ("ium", ["science"]),
    ("ide", ["science"]),
    ("ase", ["science"]),
    ("ene", ["science"]),
    ("yne", ["science"]),
    ("ane", ["science"]),
    ("ose", ["science"]),
    ("zyme", ["science"]),
    ("ogen", ["science"]),
    ("plasm", ["science"]),

    # Technology suffixes
    ("ware", ["technology"]),
    ("byte", ["technology"]),
    ("bit", ["technology"]),

    # Music suffixes
    ("ando", ["music"]),
    ("etto", ["music"]),
    ("issimo", ["music"]),
]

# Words that should NOT be matched by suffix rules (false positives)
SUFFIX_EXCLUSIONS = {
    # -ide: common words that aren't chemistry
    "abide", "aside", "beside", "bride", "confide", "decide", "divide",
    "guide", "hide", "inside", "outside", "override", "pride", "provide",
    "ride", "side", "slide", "stride", "tide", "wide", "collide", "reside",
    "preside", "coincide", "subside", "worldwide", "countryside", "suicide",
    "homicide", "genocide", "bide", "chide", "glide", "snide",
    # -ase: common words that aren't enzymes
    "base", "case", "chase", "database", "erase", "phase", "phrase",
    "purchase", "vase", "lease", "please", "release", "increase", "decrease",
    "crease", "grease", "cease",
    # -ane: common words that aren't chemistry
    "arcane", "bane", "cane", "crane", "dane", "humane", "hurricane",
    "insane", "jane", "lane", "mane", "membrane", "mundane", "pane",
    "plane", "profane", "sane", "vane", "wane", "inane", "airplane",
    # -ene: common words that aren't chemistry
    "scene", "serene", "gene", "hygiene", "irene", "intervene", "diane",
    # -yne: common words that aren't chemistry
    "wayne", "tyne", "shane",
    # -ose: common words that aren't chemistry
    "close", "chose", "dose", "hose", "nose", "pose", "prose", "purpose",
    "rose", "suppose", "those", "whose", "compose", "dispose", "expose",
    "impose", "oppose", "propose", "verbose", "diagnose", "morose",
    "comatose", "grandiose", "choose", "loose", "goose", "moose", "noose",
    "tease", "ease", "disease", "disclose", "pantyhose",
    # -ase: more exclusions
    "staircase", "suitcase", "showcase",
    # -ide: more exclusions
    "aide", "alongside", "backside", "upside", "riverside", "merseyside",
    "nationwide", "statewide", "backslide", "jose",
    # -ium: common words that aren't elements
    "medium", "stadium", "premium", "podium", "gymnasium", "aquarium",
    "auditorium", "compendium", "consortium", "curriculum", "delirium",
    "emporium", "millennium", "opium", "symposium",
    "trivium", "cranium", "atrium", "belgium", "pentium", "valium",
    # -ane: more exclusions
    "aeroplane", "brisbane", "adelaide",
    # -ogen: not science
    "rogen",
    # -ware: not tech
    "aware", "beware", "ware", "wares", "warfare", "delaware",
    # -bit: not tech
    "bit", "habit", "rabbit", "inhabit", "exhibit", "prohibit", "gambit",
    "orbit", "hobbit", "obit",
    # -ando: not music
    "commando", "orlando", "fernando",
    # -etto: not music
    "ghetto", "stiletto",
    # Medical suffix exclusions
    "trophy", "atrophy",  # -trophy can be non-medical
}

# ---------------------------------------------------------------------------
# 2. CURATED WORD LISTS  (category -> set of words)
# ---------------------------------------------------------------------------
CURATED_WORDS = {
    "medical": {
        "diagnosis", "symptom", "prescription", "surgery", "therapy",
        "vaccine", "anatomy", "antibiotic", "cardiac", "pharmaceutical",
        "stethoscope", "anesthesia", "anaesthesia", "biopsy", "catheter",
        "chemotherapy", "cholesterol", "clinical", "congenital", "dermatology",
        "dialysis", "dosage", "epidemic", "epidural", "fracture",
        "hemorrhage", "haemorrhage", "hypertension", "immunization",
        "inflammation", "insulin", "malignant", "metastasis", "neurological",
        "oncology", "ophthalmology", "orthopedic", "orthopaedic", "pathology",
        "pediatric", "paediatric", "placebo", "prognosis", "prosthesis",
        "psychiatry", "radiology", "rehabilitation", "scalpel", "surgeon",
        "triage", "ultrasound", "vaccination", "ventilator", "physician",
        "pharynx", "larynx", "trachea", "esophagus", "oesophagus",
        "aorta", "femur", "tibia", "fibula", "sternum", "pelvis",
        "thyroid", "pancreas", "spleen", "appendix", "tendon", "ligament",
        "cartilage", "vertebra", "vertebrae", "bronchial", "pulmonary",
        "renal", "hepatic", "cerebral", "gastrointestinal", "intravenous",
        "subcutaneous", "benign", "chronic", "acute", "asymptomatic",
        "ambulance", "paramedic", "tourniquet", "syringe", "suture",
        "tracheotomy", "mastectomy", "appendectomy", "hysterectomy",
        "pneumonia", "tuberculosis", "diabetes", "alzheimer", "parkinson",
        "epilepsy", "asthma", "eczema", "psoriasis", "aneurysm",
        "gangrene", "sepsis", "edema", "oedema", "abscess", "lesion",
        "tumor", "tumour", "cyst", "polyp", "hernia",
    },
    "legal": {
        "attorney", "plaintiff", "defendant", "verdict", "litigation",
        "statute", "jurisdiction", "testimony", "subpoena", "affidavit",
        "acquittal", "adjudicate", "advocate", "allegation", "amendment",
        "arbitration", "arraignment", "bail", "barrister", "clemency",
        "compliance", "contempt", "conviction", "counsel", "courtroom",
        "cross-examine", "custody", "deposition", "embezzlement", "estoppel",
        "extradition", "felony", "fiduciary", "foreclosure", "habeas",
        "hearsay", "indictment", "injunction", "jurisprudence", "juror",
        "larceny", "lawsuit", "legislature", "libel", "magistrate",
        "misdemeanor", "negligence", "notarize", "ordinance", "paralegal",
        "parole", "perjury", "petition", "precedent", "probation",
        "prosecution", "quorum", "recidivism", "remand", "restitution",
        "slander", "solicitor", "sovereign", "stipulation", "tribunal",
        "unconstitutional", "warrant", "judiciary", "appellant", "appellate",
        "tort", "plaintiff", "litigant", "deposition", "jurisprudence",
    },
    "culinary": {
        "cuisine", "recipe", "saute", "sauté", "broccoli", "quinoa",
        "croissant", "jalapeno", "jalapeño", "filet", "fillet",
        "gnocchi", "bruschetta", "espresso", "cappuccino", "latte",
        "macchiato", "prosciutto", "risotto", "focaccia", "ciabatta",
        "baguette", "brioche", "crepe", "crêpe", "soufflé", "souffle",
        "ratatouille", "bouillabaisse", "béarnaise", "béchamel",
        "vinaigrette", "hors", "charcuterie", "crudités", "canapé",
        "consommé", "crouton", "gratin", "meringue", "mousse",
        "pâté", "pate", "sorbet", "tartare", "terrine", "velouté",
        "ceviche", "guacamole", "quesadilla", "tortilla", "burrito",
        "enchilada", "tamale", "chimichurri", "chorizo", "paella",
        "gazpacho", "sangria", "tempura", "wasabi", "sashimi",
        "edamame", "ramen", "udon", "tofu", "kimchi",
        "bibimbap", "pho", "baklava", "hummus", "falafel",
        "tahini", "tzatziki", "gyro", "shawarma", "naan",
        "tandoori", "masala", "turmeric", "cardamom", "cinnamon",
        "saffron", "coriander", "cumin", "oregano", "thyme",
        "rosemary", "basil", "parsley", "cilantro", "dill",
        "tarragon", "chive", "nutmeg", "paprika", "cayenne",
        "habanero", "serrano", "chipotle", "ancho", "poblano",
        "mozzarella", "parmesan", "gruyere", "camembert", "brie",
        "roquefort", "gorgonzola", "gouda", "provolone", "mascarpone",
        "ricotta", "pecorino", "manchego", "emmental", "fontina",
        "ravioli", "linguine", "penne", "fettuccine", "tagliatelle",
        "rigatoni", "orzo", "lasagna", "lasagne", "macaroni",
        "spaghetti", "farfalle", "fusilli", "cannelloni", "tortellini",
        "goulash", "stroganoff", "couscous", "pilaf", "polenta",
        "arugula", "endive", "radicchio", "fennel", "shallot",
        "leek", "zucchini", "aubergine", "courgette",
        "artichoke", "asparagus", "bok", "caramel",
    },
    "animals": {
        "gyrfalcon", "chameleon", "cheetah", "crocodile", "dolphin",
        "elephant", "falcon", "gazelle", "leopard", "jaguar",
        "hippopotamus", "rhinoceros", "giraffe", "kangaroo", "koala",
        "platypus", "orangutan", "chimpanzee", "gorilla", "baboon",
        "hyena", "coyote", "dingo", "jackal", "lynx",
        "cougar", "puma", "panther", "ocelot", "armadillo",
        "porcupine", "hedgehog", "badger", "weasel", "otter",
        "beaver", "mongoose", "meerkat", "chinchilla", "capybara",
        "iguana", "gecko", "salamander", "tortoise", "alligator",
        "anaconda", "python", "cobra", "viper", "rattlesnake",
        "pelican", "flamingo", "toucan", "macaw", "cockatoo",
        "penguin", "albatross", "heron", "egret", "osprey",
        "peregrine", "condor", "vulture", "pheasant", "partridge",
        "quail", "grouse", "ibis", "stork", "crane",
        "manatee", "walrus", "narwhal", "orca", "porpoise",
        "barracuda", "piranha", "stingray", "seahorse", "octopus",
        "squid", "jellyfish", "starfish", "lobster", "crayfish",
        "tarantula", "scorpion", "centipede", "millipede", "cicada",
        "mantis", "caterpillar", "chrysalis", "cocoon", "butterfly",
        "dragonfly", "firefly", "beetle", "mosquito", "cockroach",
    },
    "technology": {
        "algorithm", "bandwidth", "cache", "database", "ethernet",
        "firmware", "gigabyte", "hardware", "interface", "kernel",
        "latency", "malware", "network", "opcode", "protocol",
        "query", "router", "software", "throughput", "upload",
        "virtual", "widget", "bluetooth", "broadband", "browser",
        "compiler", "cryptography", "cybersecurity", "debugging",
        "decryption", "download", "encryption", "executable", "firewall",
        "framework", "gigahertz", "hashtag", "hyperlink", "javascript",
        "kilobyte", "linux", "localhost", "megabyte", "metadata",
        "microprocessor", "middleware", "nanotechnology", "opensource",
        "overclocking", "permalink", "pixel", "podcast", "ransomware",
        "recursive", "scalability", "semiconductor", "server", "smartphone",
        "streaming", "subroutine", "terabyte", "transistor", "url",
        "username", "virtualization", "vpn", "webpage", "wifi",
        "wireless", "xml", "api", "ascii", "binary",
        "boolean", "byte", "cloud", "cpu", "data",
        "digital", "domain", "emoji", "favicon", "gui",
        "http", "https", "html", "ip", "iteration",
        "json", "lambda", "loop", "machine", "module",
        "node", "object", "parameter", "queue", "ram",
        "runtime", "script", "syntax", "token", "unicode",
        "variable", "webhook", "xpath", "yaml", "zip",
    },
    "music": {
        "allegro", "baritone", "crescendo", "forte", "melody",
        "orchestra", "rhythm", "soprano", "tempo", "accelerando",
        "adagio", "andante", "arpeggio", "cadence", "cantata",
        "cello", "chorale", "chord", "clarinet", "clef",
        "concerto", "contralto", "counterpoint", "diminuendo", "dissonance",
        "duet", "ensemble", "falsetto", "fermata", "fortissimo",
        "fugue", "glissando", "harmony", "interlude", "legato",
        "libretto", "maestro", "mezzo", "nocturne", "oboe",
        "octave", "opera", "opus", "overture", "pianissimo",
        "piano", "pizzicato", "polyphony", "prelude", "presto",
        "quartet", "recital", "requiem", "resonance", "ritardando",
        "rondo", "scale", "scherzo", "serenade", "sforzando",
        "sonata", "staccato", "symphony", "syncopation", "treble",
        "tremolo", "trill", "tuning", "unison", "vibrato",
        "viola", "violin", "virtuoso", "vivace",
        "saxophone", "trombone", "trumpet", "tuba", "flute",
        "piccolo", "bassoon", "harpsichord", "timpani", "xylophone",
        "marimba", "glockenspiel", "tambourine", "cymbal", "accordion",
        "harmonica", "mandolin", "ukulele", "banjo", "sitar",
    },
    "science": {
        "molecule", "hypothesis", "photosynthesis", "chromosome", "nucleus",
        "electron", "proton", "neutron", "atom", "isotope",
        "catalyst", "entropy", "equilibrium", "evolution", "genome",
        "gravity", "inertia", "kinetic", "magnetism", "mitosis",
        "meiosis", "osmosis", "oxidation", "quantum", "radiation",
        "relativity", "thermodynamics", "velocity", "wavelength", "bacteria",
        "organism", "ecosystem", "biodiversity", "biome", "cellular",
        "chlorophyll", "cytoplasm", "deoxyribonucleic", "enzyme", "eukaryote",
        "prokaryote", "fermentation", "fission", "fusion", "genetics",
        "geothermal", "helium", "hydrogen", "lithium", "neon",
        "nitrogen", "oxygen", "phosphorus", "plutonium", "potassium",
        "silicon", "sodium", "sulfur", "sulphur", "uranium",
        "vanadium", "xenon", "yttrium", "zinc", "zirconium",
        "acetyl", "adenine", "allele", "amino", "amoeba",
        "anion", "antimatter", "baryon", "boson", "carbon",
        "centrifuge", "collider", "covalent", "cytosine", "diffusion",
        "electromagnetic", "exothermic", "endothermic", "fluorine", "guanine",
        "halogen", "ion", "kelvin", "lipid", "meson",
        "muon", "neutrino", "nucleotide", "peptide", "photon",
        "polymer", "quark", "reagent", "ribosome", "solvent",
        "spectroscopy", "stoichiometry", "thymine", "titration", "valence",
        "petroleum", "seismology", "geology", "meteorology", "paleontology",
        "astronomy", "astrophysics", "cosmology", "taxonomy", "botany",
        "zoology", "microbiology", "biochemistry", "biophysics", "neuroscience",
    },
    "sports": {
        "athlete", "tournament", "championship", "gymnasium", "marathon",
        "triathlon", "decathlon", "pentathlon", "javelin", "discus",
        "hurdle", "relay", "sprint", "archery", "badminton",
        "basketball", "boxing", "cricket", "cycling", "diving",
        "equestrian", "fencing", "football", "golf", "gymnastics",
        "handball", "hockey", "judo", "karate", "lacrosse",
        "luge", "polo", "rowing", "rugby", "sailing",
        "skiing", "snowboard", "soccer", "softball", "squash",
        "surfing", "swimming", "taekwondo", "tennis", "volleyball",
        "weightlifting", "wrestling", "biathlon", "bobsled", "canoeing",
        "curling", "dressage", "slalom", "freestyle", "goaltender",
        "goalkeeper", "halfback", "midfielder", "quarterback", "referee",
        "umpire", "striker", "defender", "forward", "pitcher",
        "batter", "catcher", "outfielder", "infielder", "shortstop",
        "overtime", "penalty", "scoreboard", "stadium", "podium",
    },
    "business": {
        "entrepreneur", "acquisition", "amortization", "bankruptcy",
        "capitalization", "commodity", "conglomerate", "consortium",
        "corporation", "debenture", "depreciation", "diversification",
        "dividend", "equity", "fiduciary", "franchise", "futures",
        "hedge", "incorporation", "inflation", "insolvency", "investment",
        "leverage", "liability", "liquidation", "merger", "monopoly",
        "mortgage", "portfolio", "procurement", "revenue", "securities",
        "shareholder", "subsidiary", "venture", "wholesale", "arbitrage",
        "audit", "brokerage", "collateral", "deficit", "expenditure",
        "fiscal", "foreclosure", "gdp", "incentive", "index",
        "insurance", "interest", "inventory", "invoice", "ipo",
        "lease", "liability", "margin", "nasdaq", "overhead",
        "payroll", "pension", "profit", "prospectus", "quota",
        "recession", "refinance", "remuneration", "royalty", "tariff",
        "turnover", "underwrite", "valuation", "yield",
    },
    "education": {
        "curriculum", "syllabus", "pedagogy", "dissertation", "thesis",
        "valedictorian", "salutatorian", "baccalaureate", "commencement",
        "matriculation", "accreditation", "alumnus", "alumni", "alumna",
        "alumnae", "academia", "academic", "collegiate", "dean",
        "doctorate", "enrollment", "faculty", "fraternity", "graduate",
        "honors", "honours", "interdisciplinary", "kindergarten", "lecture",
        "literacy", "montessori", "prerequisite", "professor", "provost",
        "registrar", "scholarship", "semester", "seminar", "sophomore",
        "sorority", "superintendent", "tenure", "tuition", "tutorial",
        "undergraduate", "university", "valedictorian", "vocational",
    },
    "clothing": {
        "boutique", "chiffon", "corduroy", "couture", "crochet",
        "denim", "embroidery", "haute", "linen", "lingerie",
        "organza", "polyester", "satin", "sequin", "suede",
        "taffeta", "tulle", "tweed", "velvet", "cashmere",
        "chinos", "camisole", "cardigan", "charmeuse", "chemise",
        "chenille", "dungarees", "gabardine", "gingham", "haberdashery",
        "jacquard", "jersey", "khaki", "lycra", "moccasin",
        "negligee", "nylon", "paisley", "pashmina", "peignoir",
        "plaid", "rayon", "sateen", "silk", "spandex",
        "stiletto", "tuxedo", "viscose", "beret", "fedora",
        "cravat", "ascot", "bodice", "bolero", "bustier",
        "corset", "epaulette", "jodhpurs", "kaftan", "kimono",
        "lederhosen", "leotard", "sarong", "sari",
    },
}

# ---------------------------------------------------------------------------
# 3. CONTEXT SENTENCE KEYWORDS  (category -> keywords to search for)
# ---------------------------------------------------------------------------
CONTEXT_KEYWORDS = {
    "medical": {
        "doctor", "hospital", "patient", "medical", "clinical", "health",
        "disease", "treatment", "surgery", "diagnosis", "symptoms",
        "medicine", "physician", "nurse", "therapy", "prescription",
        "condition", "chronic", "infection", "blood", "organ",
    },
    "legal": {
        "court", "judge", "law", "legal", "attorney", "lawyer", "trial",
        "jury", "statute", "criminal", "prosecution", "defense", "defence",
        "rights", "constitutional", "plaintiff", "defendant",
    },
    "culinary": {
        "cook", "cooking", "kitchen", "recipe", "dish", "food", "meal",
        "restaurant", "chef", "bake", "baking", "ingredient", "flavor",
        "flavour", "seasoning", "spice", "dessert", "sauce", "soup",
        "salad", "pasta", "bread", "cheese",
    },
    "animals": {
        "animal", "species", "wildlife", "habitat", "zoo", "mammal",
        "reptile", "bird", "fish", "insect", "predator", "prey",
        "endangered", "creature", "nest", "aquatic", "marine",
    },
    "technology": {
        "computer", "software", "programming", "digital", "internet",
        "technology", "code", "coding", "tech", "cyber", "online",
        "electronic", "device", "system", "network",
    },
    "music": {
        "music", "musical", "musician", "song", "instrument", "orchestra",
        "band", "concert", "compose", "composer", "sing", "singing",
        "played", "perform", "performance", "note", "notes",
    },
    "science": {
        "science", "scientific", "experiment", "laboratory", "lab",
        "research", "chemical", "chemistry", "physics", "biology",
        "element", "compound", "reaction", "theory", "cell", "cells",
    },
    "sports": {
        "sport", "sports", "game", "match", "team", "player", "coach",
        "score", "win", "championship", "league", "compete", "competition",
        "athletic", "race", "training",
    },
    "business": {
        "business", "company", "corporate", "market", "financial", "finance",
        "economy", "economic", "invest", "investment", "stock", "trade",
        "profit", "revenue", "bank", "banking",
    },
    "education": {
        "school", "student", "teacher", "university", "college", "education",
        "academic", "study", "studies", "class", "classroom", "learning",
        "degree", "course", "lecture", "campus",
    },
    "clothing": {
        "fashion", "clothing", "wear", "wearing", "fabric", "garment",
        "textile", "dress", "outfit", "designer", "style", "sew",
        "sewing", "tailor", "wardrobe",
    },
}


def check_suffix(word: str) -> list[str]:
    """Return list of categories matched by suffix rules."""
    if word in SUFFIX_EXCLUSIONS:
        return []

    categories = []
    lower = word.lower()
    for suffix, cats in SUFFIX_RULES:
        if lower.endswith(suffix) and len(lower) > len(suffix):
            categories.extend(cats)
    return list(set(categories))


def check_curated(word: str) -> list[str]:
    """Return list of categories from curated word lists."""
    categories = []
    lower = word.lower()
    for category, word_set in CURATED_WORDS.items():
        if lower in word_set:
            categories.append(category)
    return categories


def check_context(context_sentence: str) -> list[str]:
    """Return list of categories inferred from context sentence keywords."""
    if not context_sentence:
        return []

    categories = []
    lower = context_sentence.lower()
    words_in_sentence = set(lower.split())

    for category, keywords in CONTEXT_KEYWORDS.items():
        for kw in keywords:
            if kw in words_in_sentence:
                categories.append(category)
                break
    return categories


def categorize_word(word: str, context_sentence: str = "") -> list[str]:
    """Combine all categorization approaches and return sorted unique list."""
    cats = set()
    cats.update(check_suffix(word))
    cats.update(check_curated(word))
    cats.update(check_context(context_sentence))
    return sorted(cats)


def main():
    if not DATA_DIR.is_dir():
        print(f"ERROR: Data directory not found: {DATA_DIR}")
        sys.exit(1)

    total_files = 0
    categorized_count = 0
    category_counts = defaultdict(int)
    errors = []

    # Walk through all letter subdirectories
    for letter_dir in sorted(DATA_DIR.iterdir()):
        if not letter_dir.is_dir():
            continue

        for json_file in sorted(letter_dir.glob("*.json")):
            total_files += 1

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                errors.append(f"  Error reading {json_file}: {e}")
                continue

            word = data.get("word", json_file.stem)
            context_sentence = data.get("context_sentence", "")

            categories = categorize_word(word, context_sentence)

            if categories:
                # Remove old categories field if it exists, so we place it fresh
                data.pop("categories", None)

                # Insert categories field after 'status' (or at a reasonable place)
                # Rebuild the dict to maintain key order
                new_data = {}
                inserted = False
                for key, value in data.items():
                    new_data[key] = value
                    if key == "status" and not inserted:
                        new_data["categories"] = categories
                        inserted = True
                if not inserted:
                    # Fallback: insert before 'variants' or at end
                    new_data["categories"] = categories

                with open(json_file, "w", encoding="utf-8") as f:
                    f.write(json.dumps(new_data, indent=2, ensure_ascii=False) + "\n")

                categorized_count += 1
                for cat in categories:
                    category_counts[cat] += 1
            else:
                # If no categories found, make sure we remove any stale ones
                if "categories" in data:
                    del data["categories"]
                    with open(json_file, "w", encoding="utf-8") as f:
                        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # ---------------------------------------------------------------------------
    # Print statistics
    # ---------------------------------------------------------------------------
    print("=" * 60)
    print("  Word Categorization Results")
    print("=" * 60)
    print(f"  Total word files scanned:  {total_files}")
    print(f"  Words categorized:         {categorized_count}")
    print(f"  Words uncategorized:       {total_files - categorized_count}")
    print()
    print("  Breakdown by category:")
    print("  " + "-" * 40)
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat:<20s} {count:>6d}")
    print("  " + "-" * 40)
    print(f"    {'TOTAL':<20s} {sum(category_counts.values()):>6d}")
    print()

    if errors:
        print(f"  Errors encountered: {len(errors)}")
        for err in errors[:10]:
            print(err)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
        print()

    print("=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
