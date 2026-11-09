#!/usr/bin/env python3
"""Build data/posts.json for Spectrum from the live Substack archive.

Walks the published chain newest -> oldest via Substack's public post API,
extracts the facts the page needs (title, subtitle, date, series, excerpt,
key lines, cross-links), merges the human-curated layers (data/tags.json,
data/library.json), and writes data/posts.json.

Facts come from the archive. Judgment (tags, shelf) stays in files you edit.
Run on Tycho; the egress proxy elsewhere blocks pulse.itesydht.com.

    python3 build.py            # rebuild
    python3 build.py --check    # exit 1 if posts.json would change (for cron)
"""
import html, json, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PUB = "https://pulse.itesydht.com"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UA = {"User-Agent": "spectrum-build/1.0 (+https://spectrum.itesydht.com)"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def newest_slug():
    d = get(f"{PUB}/api/v1/archive?sort=new&limit=1")
    posts = d["posts"] if isinstance(d, dict) else d
    return posts[0]["slug"]

SERIES_RE = re.compile(r'<p[^>]*>\s*Part of\s+<a[^>]*href="[^"]*/p/([a-z0-9-]+)(?:#(?:%C2%A7|§)?([a-z0-9-]+))?"[^>]*>\s*(?:the\s+)?([^<]+?)\s*</a>', re.I)
LINK_RE = re.compile(r'href="https?://pulse\.itesydht\.com/p/([a-z0-9-]+)(?:[#?][^"]*)?"', re.I)
EXT_RE = re.compile(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
SKIP_HOSTS = ("pulse.itesydht.com", "substack.com", "substackcdn.com", "amazonaws.com", "spectrum.itesydht.com")
PARA_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
BOLD_RE = re.compile(r"<strong>(.*?)</strong>", re.S)
STOP = set("""a an the and or but if then so of to in on at by for from with without into onto over under about
as is are was were be been being am do does did done have has had having will would can could should shall may might
must not no nor yes it its this that these those there here where when why how what which who whom whose i me my mine
we us our you your he him his she her they them their one ones all any some each every few more most other such only
own same than too very just also even still again back out up down off than then once because while after before
than very really thing things way ways lot lots got get gets getting go goes going went come comes came make makes made
like said say says take took know knew think thought see saw look looked use used using new old first last next much
many well good bad big small long short right left around through between against during within along across""".split())
TERM_RE = re.compile(r"[a-z0-9][a-z0-9'-]+")

def terms_of(text, limit=700):
    """Unique body words a reader might type, minus stopwords; what the story says somewhere."""
    seen, out = set(), []
    for w in TERM_RE.findall(text.lower()):
        w = w.strip("'-")
        if len(w) < 3 or w in STOP or w.isdigit() or w in seen:
            continue
        seen.add(w); out.append(w)
        if len(out) >= limit:
            break
    return sorted(out)

def extract(post):
    body = post.get("body_html") or ""
    series = None
    m = SERIES_RE.search(body)
    if m:
        series = {"name": m.group(3).strip(), "slug": m.group(1), "anchor": m.group(2)}
    paras = [strip_html(p) for p in PARA_RE.findall(body)]
    full_text = " ".join(paras)
    paras = [p for p in paras if p and not p.lower().startswith("part of ") and len(p) > 40]
    excerpt = paras[0] if paras else (post.get("subtitle") or "")
    if len(excerpt) > 230:
        cut = excerpt[:230]
        excerpt = cut[: cut.rfind(" ")] + "…"
    links = []
    for s in LINK_RE.findall(body):
        if s != post["slug"] and s not in links:
            links.append(s)
    cites = []
    for href, text in EXT_RE.findall(body):
        if any(h in href for h in SKIP_HOSTS):
            continue
        label = strip_html(text)
        if not label or href in [c["url"] for c in cites]:
            continue
        host = re.sub(r"^www\.", "", href.split("/")[2])
        cites.append({"url": href.split("?utm")[0], "label": label[:80], "host": host})
    bold = []
    for b in BOLD_RE.findall(body):
        t = strip_html(b)
        if t and t not in bold:
            bold.append(t)
    return {
        "slug": post["slug"],
        "url": f"{PUB}/p/{post['slug']}",
        "title": (post.get("title") or "").strip(),
        "subtitle": (post.get("subtitle") or "").strip(),
        "date": post["post_date"][:10],
        "wordcount": post.get("wordcount"),
        "cover_image": post.get("cover_image"),
        "series": series,
        "excerpt": excerpt,
        "links_to": links,
        "cites": cites,
        "bold_lines": bold[:6],
        "keywords": [],
        "terms": terms_of(full_text),
        "_text": full_text,
        "_type": post.get("type"),
    }

def walk():
    slug = newest_slug()
    out, seen, pages = [], set(), []
    while slug and slug not in seen:
        seen.add(slug)
        p = get(f"{PUB}/api/v1/posts/{slug}")
        rec = extract(p)
        (pages if p.get("type") == "page" else out).append(rec)
        slug = p.get("previous_post_slug")
        time.sleep(0.2)
    return out, pages

def series_index(slugs, known):
    """Parse each series page into sections -> ordered post slugs."""
    result = []
    for slug in slugs:
        p = get(f"{PUB}/api/v1/posts/{slug}")
        body = p.get("body_html") or ""
        sections, current = [], None
        # headings open sections; links inside add posts
        for tok in re.finditer(r"<h[23][^>]*(?:id=\"([^\"]*)\")?[^>]*>(.*?)</h[23]>|href=\"https?://pulse\.itesydht\.com/p/([a-z0-9-]+)[^\"]*\"", body, re.S | re.I):
            if tok.group(2) is not None:
                name = strip_html(tok.group(2))
                current = {"name": name, "anchor": tok.group(1) or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "posts": []}
                sections.append(current)
            elif tok.group(3) and tok.group(3) in known and tok.group(3) != slug:
                tgt = current if current else (sections.append({"name": strip_html(p.get("title") or ""), "anchor": None, "posts": []}) or sections[-1])
                if tok.group(3) not in tgt["posts"]:
                    tgt["posts"].append(tok.group(3))
                current = current or tgt
        sections = [s for s in sections if s["posts"]]
        result.append({
            "slug": slug, "title": (p.get("title") or "").strip(), "heading": strip_html(p.get("subtitle") or ""),
            "url": f"{PUB}/p/{slug}", "type": "page", "updated": (p.get("updated_at") or "")[:10],
            "sections": sections, "posts": [s for sec in sections for s in sec["posts"]],
        })
    return result

def _main_title(t):
    return re.split(r"[:(]", t or "")[0].strip()

def auto_cite(posts, library):
    """Populate each library card's `cited` from story text. Hand-set cites in
    shelf/decisions.json survive; this only adds. Title-case titles match
    case-sensitively (so 'never finished' in prose is not Goggins); authors and
    explicit `match` terms match case-insensitively."""
    from collections import Counter
    author_n = Counter(a.strip() for x in library for a in (x.get("author") or "").split(",") if a.strip())
    for b in library:
        mention, name = [], []
        names = {_main_title(b.get("title"))} | {_main_title(t.get("title")) for t in b.get("titles", [])}
        for n in names:
            if len(n) >= 6 and len(n.split()) >= 2 and n[0].isupper():
                mention.append(re.compile(r"\b" + re.escape(n) + r"\b"))
        for a in (b.get("author") or "").split(","):
            a = a.strip()
            if len(a) >= 5 and author_n[a] == 1:       # an author with several books here is ambiguous; skip
                mention.append(re.compile(r"\b" + re.escape(a) + r"\b", re.I))
        for m in b.get("match", []):
            if len(m) >= 4:
                name.append(re.compile(r"\b" + re.escape(m) + r"\b", re.I))
        cited = list(b.get("cited", []))            # hand-set cites are mentions
        named_in = []
        for r in posts:
            if any(p.search(r["_text"]) for p in mention):
                if r["slug"] not in cited: cited.append(r["slug"])
            elif any(p.search(r["_text"]) for p in name):
                if r["slug"] not in cited: cited.append(r["slug"])
                named_in.append(r["slug"])
        b["cited"] = cited
        b["named_in"] = named_in

def prerender(posts, library):
    """Plain HTML list inside <noscript> so crawlers and non-JS clients see the index."""
    from html import escape as h
    idx = ROOT / "index.html"
    s = idx.read_text()
    a, z = "<!-- prerender -->", "<!-- /prerender -->"
    if a not in s or z not in s:
        return
    rows = ["<h2>Stories</h2><ol>"]
    for p in sorted(posts, key=lambda r: -r["n"]):
        rows.append(f'<li><a href="{h(p["url"])}">{h(p["title"])}</a>' + (f' <em>{h(p["subtitle"])}</em>' if p.get("subtitle") else "") + (f'<br>{h(p.get("synopsis") or p.get("excerpt") or "")}' ) + "</li>")
    rows.append("</ol><h2>Library</h2><ul>")
    for bk in library:
        rows.append(f'<li><a href="{h(bk.get("url") or "")}">{h(bk["title"])}</a> · {h(bk.get("author") or "")} · {h(bk.get("shelf") or "")}</li>')
    rows.append("</ul>")
    new = a + "\n" + "\n".join(rows) + "\n" + z
    s = s[: s.index(a)] + new + s[s.index(z) + len(z):]
    idx.write_text(s)

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default

def main(check=False):
    posts, pages = walk()
    posts.sort(key=lambda r: r["date"])
    for i, r in enumerate(posts, 1):
        r["n"] = i
    known = {r["slug"] for r in posts}
    # Series pages are listed in data/series_pages.json so the bands survive
    # even when no post carries a "Part of the ... series" line any more.
    series_slugs = list(load_json(DATA / "series_pages.json", []))
    for r in posts:
        if r["series"] and r["series"]["slug"] not in series_slugs:
            series_slugs.append(r["series"]["slug"])
    for pg in pages:
        if pg["slug"] not in series_slugs and any(l in known for l in pg["links_to"]):
            series_slugs.append(pg["slug"])
    series = series_index(series_slugs, known)

    tags = load_json(DATA / "tags.json", {})
    untagged = []
    for r in posts:
        r["keywords"] = tags.get(r["slug"], [])
        if not r["keywords"]:
            untagged.append(r["slug"])
        r.pop("_type", None)
    synopses = load_json(DATA / "synopses.json", {})
    for r in posts:
        r["synopsis"] = synopses.get(r["slug"], "")
    library = load_json(DATA / "library.json", [])
    auto_cite(posts, library)
    for r in posts:
        r.pop("_text", None)

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "publication": {"name": "I Tried Everything So You Don't Have To", "url": PUB},
        "theme": {"bg": "#1C1C1E", "pop": "#B8860B", "headings": "Lora"},
        "series": series,
        "posts": posts,
        "library": library,
    }
    target = DATA / "posts.json"
    old = load_json(target, {})
    changed = {k: v for k, v in out.items() if k != "generated"} != {k: v for k, v in old.items() if k != "generated"}
    if check:
        print(f"{len(posts)} posts; {'CHANGED' if changed else 'unchanged'}")
        sys.exit(1 if changed else 0)
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    prerender(posts, library)
    print(f"wrote {target.relative_to(ROOT)}: {len(posts)} posts, {len(series)} series, {len(library)} in the library")
    if untagged:
        print(f"untagged ({len(untagged)}), add to data/tags.json: {', '.join(untagged)}")

if __name__ == "__main__":
    main(check="--check" in sys.argv)
