"""Fill in book descriptions from Open Library for library cards whose Audible
blurb is missing or thin. Cached in shelf/blurbs.json; safe to re-run."""
import json, re, sys, time, urllib.request, urllib.parse, pathlib
HERE = pathlib.Path(__file__).parent
CACHE = HERE / "blurbs.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "spectrum.itesydht.com (library enrich)"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read())

def ol_description(title, author):
    q = urllib.parse.urlencode({"title": title, "author": author or "", "limit": 3, "fields": "key,title,author_name"})
    docs = get(f"https://openlibrary.org/search.json?{q}").get("docs", [])
    for d in docs:
        w = get(f"https://openlibrary.org{d['key']}.json")
        desc = w.get("description")
        if isinstance(desc, dict): desc = desc.get("value")
        if desc and len(desc) > 120:
            return re.sub(r"\s+", " ", re.sub(r"\[.*?\]\(.*?\)|https?://\S+|-{3,}.*$", "", desc, flags=re.S)).strip()
    return ""

def main_title(t): return re.split(r"[:(]", t)[0].strip()

lib = json.load(open(HERE.parent / "data" / "library.json"))
todo = [b for b in lib if b["kind"] == "book" and b["title"] not in cache]
for b in todo:
    try:
        cache[b["title"]] = ol_description(main_title(b["title"]), b.get("author", ""))
        print(("ok  " if cache[b["title"]] else "miss"), b["title"][:50])
    except Exception as e:
        print("err ", b["title"][:50], e)
    time.sleep(0.6)
CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
print(f"{sum(1 for v in cache.values() if v)} of {len(cache)} have descriptions")
