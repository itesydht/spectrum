#!/usr/bin/env python3
"""Check retrofitted Substack posts against their pre-edit copies.
usage: verify_retrofit.py [slug ...]   (default: every slug with a saved copy)
Before-copies live outside the repo in ~/spectrum-retrofit/before/<slug>.html"""
import json, re, html, sys, pathlib, urllib.request, random
BEFORE = pathlib.Path.home() / "spectrum-retrofit" / "before"
PUB = "https://pulse.itesydht.com"
txt = lambda h: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
ADDED = ["Every story, one dial. Find the signal on Spectrum .", "Every story, one dial. Find the signal on Spectrum.",
         "Spectrum is the dial for the rest. Type a word, a name, or a feeling, and it finds the stories that match, plus the source material behind them.",
         "Behind this story : what it builds on and the source material.", "Behind this story: what it builds on and the source material.",
         "Find the next story →", "Find the next story."]
PART = re.compile(r"Part of (?:the |The )?[^.]{3,60}?(?:Series|Chronicles)[^.]{0,60}\.", re.I)
def get(slug):
    req = urllib.request.Request(f"{PUB}/api/v1/posts/{slug}?x={random.random()}", headers={"User-Agent": "spectrum-verify"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())
slugs = sys.argv[1:] or sorted(p.stem for p in BEFORE.glob("*.html"))
bad = 0
for slug in slugs:
    meta = json.loads((BEFORE / f"{slug}.json").read_text()); a = (BEFORE / f"{slug}.html").read_text()
    d = get(slug); b = d["body_html"]; ta, tb = txt(a), txt(b)
    links = re.findall(r'<a[^>]*href="(https://spectrum[^"]*)"[^>]*>(.*?)</a>', b, flags=re.S)
    links = [(u, txt(t)) for u, t in links]
    s = tb
    for x in ADDED: s = s.replace(x, "")
    ref = PART.sub("", ta)            # the old series line is allowed to disappear
    norm = lambda z: re.sub(r"\s+", " ", z).strip()
    tail = b[b.rfind("Uncomplicated systems"):]
    checks = {
        "meta": all(d[k] == meta[k] for k in ("title", "subtitle", "slug")) and d["post_date"] == meta["post_date"],
        "body": norm(s) == norm(ref),
        "tagline_once": b.count("Uncomplicated systems") == 1,
        "top_link": ("https://spectrum.itesydht.com", "Spectrum") in links,
        "button": ("https://spectrum.itesydht.com", "Find the next story →") in links,
        "behind": (f"https://spectrum.itesydht.com/#{slug}", "Behind this story") in links,
        "no_series_line": not PART.search(tb),
        "order": 0 <= tb.rfind("Uncomplicated systems") < tb.rfind("Find the next story.") < tb.rfind("Behind this story"),
        "one_widget": b.count("subscription-widget-wrap") == a.count("subscription-widget-wrap"),
        "no_new_emdash": b.count("—") <= a.count("—"),
        "no_italics_added": tail.count("<em>") == 0,
    }
    fails = [k for k, v in checks.items() if not v]
    untouched = norm(tb) == norm(ta)
    print(f"{'TODO' if untouched else ('OK  ' if not fails else 'FAIL')} {slug}" + ("" if untouched or not fails else "  -> " + ", ".join(fails)))
    bad += bool(fails) and not untouched
sys.exit(1 if bad else 0)
