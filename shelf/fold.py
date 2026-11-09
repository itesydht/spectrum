#!/usr/bin/env python3
"""Fold the parsed Audible export (shelf/audible.json) into data/library.json.

Series are the unit: one card per series with its titles underneath; a
standalone book is a card with one title. Facts (titles, authors, finished
state, Audible URLs, series summaries) come from the export. Eddy's words
(why, named, band overrides, stories) come from the existing library.json and
are preserved across re-folds. Exclusions live in EXCLUDE below.
"""
import json, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "shelf" / "audible.json"
SUMS = ROOT / "shelf" / "series-summaries.json"   # series notes lifted from the Audible export
OUT = ROOT / "data" / "library.json"

# Eddy's decisions from the curation page (exact Audible titles to leave out, plus card edits).
DECISIONS = json.load(open(ROOT / "shelf" / "decisions.json")) if (ROOT / "shelf" / "decisions.json").exists() else {}
EXCLUDE = set(DECISIONS.get("exclude_titles", []))
# Eddy's own shelves, lifted from story-workshop/reference/cultural-profile.md by shelf/shelves.py
SHELVES = json.load(open(ROOT / "shelf" / "shelves.json")) if (ROOT / "shelf" / "shelves.json").exists() else {}
SHELF_OVERRIDES = {  # titles newer than the cultural profile, or ones its matcher misses
    "Never Finished": "Psychology / Mental Performance", "Can't Hurt Me": "Psychology / Mental Performance",
    "The Artist's Way": "Psychology / Mental Performance", "This Is Your Brain on Food": "Health / Performance",
    "Children of Time": "Science Fiction", "All Systems Red": "Science Fiction", "Quantum Earth": "Science Fiction",
    "Dungeon Crawler Carl": "Science Fiction", "The Silo Saga": "Science Fiction", "Cryptonomicon": "Science Fiction",
}
def shelf_for(card):
    if card["title"] in SHELF_OVERRIDES: return SHELF_OVERRIDES[card["title"]]
    names = [card["title"]] + [t["title"] for t in card["titles"]]
    for shelf, entries in SHELVES.items():
        for e in entries:
            el = e.lower()
            for n in names:
                nl = n.lower()
                if nl.startswith(el[:18]) or el.startswith(nl[:18]) or (len(el) > 8 and el in nl):
                    return shelf
    return "Fiction / Other"   # Eddy's own catch-all shelf
FICTION_STANDALONE = {"Cryptonomicon","Starship Troopers","Roadkill","The Singularity Trap","Temporal","Artemis",
    "Project Hail Mary","The Wandering Earth","Oona Out of Order","A Good Marriage","Feedback"}
NONFICTION_SERIES = {"12 Rules for Life","Extreme Ownership","Toltec Wisdom"}
SERIES_ALIAS = {  # fold label variants into one card
    "The Dune Sequence":"Dune","Dune 7":"Dune","DUNE: Caladan Trilogy":"Dune","DUNE: Prelude to Dune":"Dune",
    "DUNE: Legends of Dune":"Dune","DUNE: The Schools of Dune Trilogy":"Dune",
    "The Remembrance of Earth's Past":"Remembrance of Earth's Past (Three-Body)",
}
AUTHOR_FIX = {"Dune":"Frank Herbert; Brian Herbert & Kevin J. Anderson"}

def series_of(r):
    s = r["series"]
    if s.startswith("Not shown"): return ""
    s = re.sub(r"\s*\(Book.*\)$", "", s).strip()
    return SERIES_ALIAS.get(s, s)

def book_no(r):
    m = re.search(r"\(Book (\d+)\)", r["series"]); return int(m.group(1)) if m else 999

def short_title(t):
    t = re.sub(r"\s*\((Third|Second|First|\d+(st|nd|rd|th)|30th|25th)[^)]*Edition[^)]*\)", "", t)
    t = re.sub(r":\s*(Third|Second)\s+Edition.*$", "", t)
    head = t.split(":")[0].strip()
    return head if len(head) >= 8 else t.strip()

def clean_author(a):
    return a.split(",")[0].split(" — ")[0].replace(" - translator","").strip()

HYPE = re.compile(r"(best.?sell|copies sold|#1|million|award|now a major|new york times|instant|phenomen|international|languages|translated|wall street journal|usa today)", re.I)
def clean_blurb(d):
    d = re.sub(r"^[A-Z0-9 #'’,.!-]{12,}(?=[A-Z][a-z])", "", d).strip()   # leading ALL-CAPS marketing
    parts = re.split(r"(?<=[.!?])\s+", d)
    while parts and HYPE.search(parts[0]) and len(parts) > 1: parts.pop(0)
    return " ".join(parts).strip()

def summaries():
    raw = json.load(open(SUMS)) if SUMS.exists() else {}
    return {SERIES_ALIAS.get(k, k): v for k, v in raw.items()}

def main():
    rows = json.load(open(SRC))
    old = {}
    try:
        for e in json.load(open(OUT)): old[e["title"]] = e
    except FileNotFoundError: pass
    sums = summaries()
    cards = {}
    for r in rows:
        title = r["title"]; ser = series_of(r)
        key = ser or short_title(title)
        if title in EXCLUDE: continue
        c = cards.setdefault(key, {"title": key if ser else short_title(title), "kind": "series" if ser else "book", "author": clean_author(r["author"]),
            "narrator": r["narrator"].split(",")[0].strip(), "titles": [], "url": r["url"], "summary": sums.get(key, ""),
            "bands": [], "why": "", "named": "", "stories": [], "tags": []})
        if not ser:
            d = clean_blurb(r["desc"])
            c["summary"] = c["summary"] or (d[:260].rsplit(" ",1)[0] + "…" if len(d) > 260 else d)
        c["titles"].append({"title": short_title(title) if ser else title, "n": book_no(r), "finished": r["finished"],
            "in_progress": bool(r["remaining"] and "left" in r["remaining"] and not r["finished"]), "url": r["url"]})
    out = []
    for key, c in cards.items():
        c["titles"].sort(key=lambda t: (t["n"], t["title"]))
        c["count"] = len(c["titles"]); c["finished"] = sum(t["finished"] for t in c["titles"])
        c["in_progress"] = sum(t["in_progress"] for t in c["titles"])
        if c["count"] == 1:
            c["url"] = c["titles"][0]["url"]
            if c["kind"] == "series":   # a one-book "series" is just a book
                c["kind"] = "book"; c["title"] = short_title(c["titles"][0]["title"]); key = c["title"]
                c["summary"] = sums.get(c["title"]) or c["summary"]
        c["author"] = AUTHOR_FIX.get(key, c["author"])
        fiction = (c["kind"] == "series" and key not in NONFICTION_SERIES) or key in FICTION_STANDALONE or c["title"] in FICTION_STANDALONE or c["title"] in {"Children of Time","All Systems Red","Dungeon Crawler Carl","The Hitchhiker's Guide to the Galaxy"}
        c["bands"] = ["fiction" if fiction else "nonfiction"]
        # carry Eddy's layer forward (match on card title or any member title)
        prev = old.get(key) or next((old[t["title"]] for t in c["titles"] if t["title"] in old), None) \
            or next((v for k, v in old.items() if k.lower() in key.lower() or key.lower() in k.lower()), None)
        if prev:
            for f in ("why", "named", "stories", "tags", "status", "year"):
                if prev.get(f): c[f] = prev[f]
            if prev.get("band") == "behind" or c["stories"]: c["bands"].append("behind")
            if prev.get("band") == "namesakes" or c.get("named"): c["bands"].append("namesakes")
        dec = DECISIONS.get("cards", {}).get(key) or DECISIONS.get("cards", {}).get(c["title"])
        c["cited"] = []
        if dec:
            for f in ("why", "named", "tags", "stories", "cited"):
                if dec.get(f): c[f] = dec[f]
            c["bands"] = [c["bands"][0]] + [b for b in dec.get("bands", []) if b in ("behind", "namesakes")]
        if c["cited"] and "behind" not in c["bands"]: c["bands"].append("behind")
        c["bands"] = list(dict.fromkeys(c["bands"]))
        c["shelf"] = shelf_for(c)
        out.append(c)
    # keep hand-added entries that aren't in Audible (podcasts, videos)
    for k, e in old.items():
        if e.get("kind") not in ("book", "series", None) and not any(c["title"] == k for c in out):
            e.setdefault("bands", [e.get("band", "nonfiction")]); out.append(e)
    order = {"namesakes":0,"behind":1,"nonfiction":2,"fiction":3}
    out.sort(key=lambda c: (min(order.get(b,9) for b in c["bands"]), -c.get("finished",0), c["title"].lower()))
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"{len(out)} cards; {sum(c.get('count',1) for c in out)} titles; "
          f"{sum(1 for c in out if c['kind']=='series')} series; excluded {len(EXCLUDE)} titles")
    print("no summary:", [c["title"] for c in out if not c.get("summary")][:12])
main()
