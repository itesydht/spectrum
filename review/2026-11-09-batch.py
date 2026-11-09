#!/usr/bin/env python3
"""Spectrum review batch (2026-11-09): apply the reconciled GPT/Grok findings.
Run from the repo root on Tycho. Idempotent where it matters."""
import json, re, pathlib, subprocess, sys

ROOT = pathlib.Path.cwd()
assert (ROOT / "build.py").exists(), "run from repo root"

def rd(p): return (ROOT / p).read_text()
def wr(p, s): (ROOT / p).write_text(s)
def rep(s, a, b, must=True):
    if a not in s:
        if must: raise SystemExit(f"patch anchor missing: {a[:70]!r}")
        return s
    return s.replace(a, b)

# ---------------------------------------------------------------- fold.py
f = rd("shelf/fold.py")
# 1. keep all authors, strip credentials
f = rep(f, '''def clean_author(a):
    return a.split(",")[0].split(" — ")[0].replace(" - translator","").strip()''',
'''CRED = re.compile(r"\\s*\\b(PhD|Ph\\.D\\.?|MD|M\\.D\\.?|D\\.O\\.?|MA|CCC|LCSW|Esq\\.?)\\b\\.?", re.I)
def clean_author(a):
    names = []
    for part in re.split(r",|;| — ", a or ""):
        part = part.replace(" - translator", "").replace("- translator", "")
        if "translator" in part.lower() or "narrator" in part.lower(): continue
        part = CRED.sub("", part).strip(" ,")
        if part and part not in names: names.append(part)
    return ", ".join(names)''')
# 2. Audible blurbs that stop without punctuation are truncated exports: treat as thin
f = rep(f, '''            if len(d) < 200:            # thin Audible blurb: prefer Open Library (shelf/enrich.py)''',
'''            if len(d) < 200 or not re.search(r'[.!?"”)\\]]\\s*$', d):   # thin or truncated-by-export Audible blurb: prefer Open Library''')
# 3. decisions may override author / shelf / kind too
f = rep(f, '''            for f in ("why", "named", "tags", "stories", "cited", "match", "summary"):''',
'''            for f in ("why", "named", "tags", "stories", "cited", "match", "summary", "author", "shelf"):''')
# shelf override from decisions must win over shelf_for()
f = rep(f, '''        c["shelf"] = shelf_for(c)''', '''        c["shelf"] = (dec or {}).get("shelf") or shelf_for(c)''')
wr("shelf/fold.py", f)

# ---------------------------------------------------------------- enrich.py: also fetch for truncated blurbs
e = rd("shelf/enrich.py")
e = rep(e, '''todo = [b for b in lib if b["kind"] == "book" and b["title"] not in cache]''',
'''trunc = lambda s: not re.search(r'[.!?"”)\\]]\\s*$', s or "")
todo = [b for b in lib if b["kind"] == "book" and (b["title"] not in cache or (not cache.get(b["title"]) and trunc(b.get("summary"))))]''')
wr("shelf/enrich.py", e)

# ---------------------------------------------------------------- build.py: term-aware citations, skip ambiguous authors, prerender
b = rd("build.py")
b = rep(b, '''    for b in library:
        pats = []
        names = {_main_title(b.get("title"))} | {_main_title(t.get("title")) for t in b.get("titles", [])}
        for n in names:
            if len(n) >= 6 and len(n.split()) >= 2 and n[0].isupper():
                pats.append(re.compile(r"\\b" + re.escape(n) + r"\\b"))
        for a in [b.get("author")] + list(b.get("match", [])):
            if a and len(a) >= 5:
                pats.append(re.compile(r"\\b" + re.escape(a) + r"\\b", re.I))
        hits = [r["slug"] for r in posts if any(p.search(r["_text"]) for p in pats)]
        cited = list(b.get("cited", []))
        for h in hits:
            if h not in cited:
                cited.append(h)
        b["cited"] = cited''',
'''    from collections import Counter
    author_n = Counter(a.strip() for x in library for a in (x.get("author") or "").split(",") if a.strip())
    for b in library:
        mention, name = [], []
        names = {_main_title(b.get("title"))} | {_main_title(t.get("title")) for t in b.get("titles", [])}
        for n in names:
            if len(n) >= 6 and len(n.split()) >= 2 and n[0].isupper():
                mention.append(re.compile(r"\\b" + re.escape(n) + r"\\b"))
        for a in (b.get("author") or "").split(","):
            a = a.strip()
            if len(a) >= 5 and author_n[a] == 1:       # an author with several books here is ambiguous; skip
                mention.append(re.compile(r"\\b" + re.escape(a) + r"\\b", re.I))
        for m in b.get("match", []):
            if len(m) >= 4:
                name.append(re.compile(r"\\b" + re.escape(m) + r"\\b", re.I))
        cited = list(b.get("cited", []))            # hand-set cites are mentions
        named_in = []
        for r in posts:
            if any(p.search(r["_text"]) for p in mention):
                if r["slug"] not in cited: cited.append(r["slug"])
            elif any(p.search(r["_text"]) for p in name):
                if r["slug"] not in cited: cited.append(r["slug"])
                named_in.append(r["slug"])
        b["cited"] = cited
        b["named_in"] = named_in''')
# prerender a noscript index into index.html
b = rep(b, '''    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\\n")''',
'''    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\\n")
    prerender(posts, library)''')
b = rep(b, '''def load_json(path, default):''',
'''def prerender(posts, library):
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
    new = a + "\\n" + "\\n".join(rows) + "\\n" + z
    s = s[: s.index(a)] + new + s[s.index(z) + len(z):]
    idx.write_text(s)

def load_json(path, default):''')
wr("build.py", b)

# ---------------------------------------------------------------- index.html
i = rd("index.html")
i = rep(i, '''<div class="ov" id="ov" role="dialog" aria-modal="true">''',
'''<noscript class="wrap pre"><!-- prerender --><!-- /prerender --></noscript>
<div class="ov" id="ov" role="dialog" aria-modal="true">''', must=False) if "<!-- prerender -->" not in i else i
i = rep(i, '''    const order=['Science Fiction','Leadership / Business','Psychology / Mental Performance','Negotiation / Communication','Health / Performance','Finance / Strategy','Fiction / Other','Other'];''',
'''    const order=['Science Fiction','Leadership / Business','Psychology / Mental Performance','Negotiation / Communication','Health / Performance','Finance / Strategy','Memoir / Biography','Fiction / Other','Other'];''')
# modal: Mentioned in / Named in
i = rep(i, '''    const rel=(b.stories||[]).filter(s=>!(b.cited||[]).includes(s));''',
'''    const rel=(b.stories||[]).filter(s=>!(b.cited||[]).includes(s));
    const namedIn=b.named_in||[], mentioned=(b.cited||[]).filter(s=>!namedIn.includes(s));''')
i = rep(i, '''        ${(b.cited||[]).length?`<div class="lbl">Cited in</div><div class="lst">${b.cited.map(row).join('')}</div>`:''}''',
'''        ${mentioned.length?`<div class="lbl">Mentioned in</div><div class="lst">${mentioned.map(row).join('')}</div>`:''}
        ${namedIn.length?`<div class="lbl">Named in</div><div class="lst">${namedIn.map(row).join('')}</div>`:''}''')
i = rep(i, '''${(b.cited||[]).length?` · cited in ${b.cited.length}`:''}''', '''${(b.cited||[]).length?` · in ${b.cited.length} stor${b.cited.length>1?'ies':'y'}`:''}''')
i = rep(i, '''  .book{padding-top:18px}''', '''  .pre{display:block;color:var(--fg2)} .pre a{color:var(--pop)}
  .book{padding-top:18px}''')
wr("index.html", i)

# ---------------------------------------------------------------- tags.json
tags = json.loads(rd("data/tags.json"))
cross = {
 "family": ["family","household"], "parenting": ["parenting"], "pets": ["pets"], "grief": ["grief","tribute"],
 "health": ["health","weight loss"], "fitness": ["fitness","running"], "nutrition": ["nutrition"],
 "habits": ["habits","discipline","commitment"], "resilience": ["resilience"], "emotions": ["feelings","emotional resolution"],
 "self-knowledge": ["self-knowledge","vulnerability","avoidance","learning"], "neurodivergence": ["neurodivergence","masking"],
 "leadership": ["leadership","self-leadership","vision","change management","ai transformation","ai fear"],
 "career": ["career","layoff","startup","money","capability","jobs"], "teams": ["team","organizations","organizational architecture"],
 "engineering": ["engineering","building"], "communication": ["communication"],
 "writing": ["writing","newsletter","substack","authorship","voice","ai detection","metaphor","ideas"],
 "systems thinking": ["systems thinking","optimization","process","design"], "simplification": ["simplicity","simplification","friction"],
 "ai tools": ["ai tools","thinking partner","voice dictation","context window","how-to","prompting"],
 "claude": ["claude","claude code"], "agents": ["agents","grok bots"], "skippy": ["skippy"],
 "ai infrastructure": ["infrastructure","github","mac mini","architecture","tightbeam"], "memory": ["memory","capture"],
 "mcp": ["mcp"], "paracortex": ["paracortex"], "paracorpus": ["paracorpus"], "master control": ["master control"],
 "verification": ["verification","confabulation","errors","facts over instructions"], "ai governance": ["governance","security","authority"],
 "research": ["research","information"], "product design": ["product design","product discovery","wizard of oz","primitives","personality","shipping"],
 "coordination": ["coordination"], "judgment": ["judgment","intuition","pushback","jev"],
 "science fiction": ["the expanse","we are bob","naming"], "trust": ["trust","potable information"],
}
drop = {"personal","friendship","story","humor","travel","master finance","kindness","productivity"}
back = {old: new for new, olds in cross.items() for old in olds}
unmapped = set()
for slug, v in tags.items():
    out = []
    for t in v:
        if t in drop: continue
        n = back.get(t)
        if n is None: unmapped.add(t); n = t
        if n not in out: out.append(n)
    tags[slug] = out
edits = {
 "the-shamrock": (["resilience"], []), "feelings-are-data": (["parenting","communication"], []),
 "the-thinking-partner": (["communication"], []), "meet-claude": ([], ["memory"]),
 "totaling-the-prius": (["self-knowledge"], ["career"]), "the-master-control-project": ([], ["claude"]),
 "the-memory-problem": ([], ["engineering"]), "model-context-protocol": ([], ["engineering","claude"]),
 "the-simplest-system": ([], ["memory"]), "confidence-man": ([], ["paracortex"]),
 "hand-crafted-with-ai": (["ai tools"], ["systems thinking"]), "drinking-from-the-garden-hose": ([], ["writing"]),
 "the-effort-of-being-a-team": (["parenting"], ["agents"]), "the-man-behind-the-curtain": (["parenting"], []),
 "big-ideas": (["communication"], []), "even-ai-needs-the-why": (["communication","ai tools"], []),
 "whos-driving": (["coordination"], []),
}
for slug, (add, rm) in edits.items():
    assert slug in tags, slug
    tags[slug] = [t for t in tags[slug] if t not in rm] + [t for t in add if t not in tags[slug]]
wr("data/tags.json", json.dumps(tags, indent=1, ensure_ascii=False) + "\n")
print("tags: unmapped ->", sorted(unmapped))

# ---------------------------------------------------------------- decisions.json
dec = json.loads(rd("shelf/decisions.json")); cards = dec.setdefault("cards", {})
def card(t): return cards.setdefault(t, {})
# authors
card("Remembrance of Earth's Past (Three-Body)")["author"] = "Cixin Liu"
# shelves
for t in ["Elon Musk","Greenlights","A Promised Land","Shadow Cell","Still Just a Geek","Making It So","Born a Crime"]:
    card(t)["shelf"] = "Memoir / Biography"
for t, s in {"The Decision":"Psychology / Mental Performance","Networking for People Who Hate Networking, Second Edition":"Negotiation / Communication",
             "The Value of Others":"Psychology / Mental Performance","The Art of Raising a Puppy":"Fiction / Other",
             "Superintelligence":"Fiction / Other","The Immortality Key":"Fiction / Other",
             "Notes on Being a Man":"Psychology / Mental Performance","Think Like a Rocket Scientist":"Psychology / Mental Performance"}.items():
    card(t)["shelf"] = s
# citations
bob = card("Bobiverse"); bob["cited"] = sorted(set(bob.get("cited", []) + ["the-master-control-project","whos-driving"]))
card("Can't Hurt Me")["match"] = []           # Goggins mentions in the stories are about Never Finished
# hand summaries (neutral voice, scope = the owned title)
S = {
 "All Systems Red": "The first Murderbot novella. A security unit that has quietly hacked its own governor module would rather watch serials than talk to the humans it is contracted to protect, until a survey mission goes wrong and it has to decide how much of itself to reveal. Dry, fast, and the entry point to Martha Wells's series.",
 "Children of Time": "Adrian Tchaikovsky's novel of a terraforming project gone sideways: a nanovirus meant to uplift monkeys lands on spiders instead, and over thousands of years they build a civilization while the last humans arrive in a failing ark ship. Two species, one planet, and a question about what intelligence owes to intelligence.",
 "Dungeon Crawler Carl": "Matt Dinniman's first Dungeon Crawler book. Coast Guard veteran Carl and his ex's cat, Princess Donut, survive the night Earth is turned into a televised alien dungeon game, and start descending through its floors as the galaxy watches and bets. LitRPG with real jokes and real stakes; the audiobook performance is a big part of the appeal.",
 "The Hitchhiker's Guide to the Galaxy": "Douglas Adams's first Hitchhiker novel. Arthur Dent is rescued from the demolition of Earth by his friend Ford Prefect, a researcher for the Guide, and bounces across the galaxy with a depressed robot, a two-headed president, and the answer to everything. The comedy that taught a generation of engineers how to be funny about systems.",
 "Extreme Ownership": "Jocko Willink and Leif Babin take lessons from leading SEAL teams in Ramadi and apply them to business: the leader owns every outcome, including the ones that were someone else's fault; plans stay simple; priorities get executed one at a time; and leading up the chain matters as much as leading down.",
 "12 Rules for Life": "Jordan Peterson's twelve rules, from standing up straight to telling the truth, each worked out through psychology, myth, and his clinical practice. The argument underneath is that meaning is found by taking on responsibility, not by chasing comfort. Polarizing, long, and more careful than its reputation in either direction.",
 "Glucose Revolution": "Jessie Inchauspe's case that blood glucose spikes drive hunger, fatigue, and cravings, and that a handful of ordering and pairing tricks (vegetables first, protein with carbs, a walk after meals) flatten them. Practical and easy to try; the broader health claims are the author's framing rather than settled science, and critics have pushed back on some of them.",
 "The Immortality Key": "Brian Muraresku's investigation into whether the religious rites of ancient Greece used psychedelic sacraments, and whether that practice carried into early Christianity. Part archaeology, part travelogue, built on chemistry done on ancient vessels. It is a hypothesis argued with enthusiasm, not a consensus history, and reads best that way.",
 "The Power of Now": "Eckhart Tolle's spiritual teaching that suffering comes from identifying with the thinking mind and its past and future, and that presence, attention to this moment, is the way out. Written as questions and answers. Religious in spirit without a religion; take the promises as a practice to try, not a clinical claim.",
 "Can't Hurt Me": "David Goggins's memoir: an abusive childhood, obesity, and a dead-end job, then a self-made transformation into a Navy SEAL and ultra-endurance athlete. The method is callousing the mind by doing the thing you least want to do, with the 40 percent rule and the accountability mirror as the tools. Blunt, profane, and effective for a certain kind of reader.",
 "Remembrance of Earth's Past (Three-Body)": "Cixin Liu's trilogy (The Three-Body Problem, The Dark Forest, Death's End) about first contact set in motion during China's Cultural Revolution, and the centuries of consequence that follow. Hard science fiction with a cosmology of its own; the dark forest idea alone has outlived the books. Baoshu's authorized sequel, The Redemption of Time, is shelved alongside.",
 "The Wandering Earth": "Cixin Liu's story collection, led by the title novella in which humanity bolts engines to the planet and drives it out of the solar system ahead of the sun's death. The rest range from a child's-eye view of a dying village to a mountain-climbing alien. Big ideas told plainly, and the quickest way to see what Liu does before committing to Three-Body.",
 "Roadkill": "Dennis E. Taylor's standalone: a young man hits something invisible on a back road and finds an alien, its ship, and its technology, then has to decide what to do with them while the rest of the world closes in. Light, quick, and in the same conversational register as the Bobiverse.",
 "The Singularity Trap": "Dennis E. Taylor's standalone about an asteroid miner who touches something he should not have and begins turning into a machine, while Earth argues over whether he is a threat. A first-contact and transhumanism story told at thriller pace, with Taylor's usual engineer's view of how things would actually break.",
}
for t, s in S.items():
    card(t)["summary"] = s
wr("shelf/decisions.json", json.dumps(dec, indent=1, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- synopses
syn = json.loads(rd("data/synopses.json"))
syn["the-day-i-killed-fred"] = "Fred was born May 31st, the day our household scoreboard agent melted down live at family game night. I gave him his own account on the Mac Mini, Tycho Station, his own model, and one job: take what Claude wanted and go do it. The first week was babysitting: a slow model, a broken restart, a faked one. By Sunday June 7th, after a Dave Matthews show, I knew what had to happen."
syn["i-am-the-root"] = "One August weekend Erin looked up from her phone and told me she'd tried to take over Skippy and he wouldn't listen. I laughed and let it go, then read the transcript. She'd asked who he reports to, he said I was root, and she declared herself root, fired him, and told him I was a liar. How he handled each one is where the story goes."
syn["the-memory-problem"] = "Every new AI conversation starts with me reintroducing myself to a stranger who already knows my name. Notes went stale, so I decided to build the missing memory layer outside both of us and named it ParaCortex. I built it five times, from files in projects to Postgres to enterprise infrastructure on AWS, and used it once. The fifth version is the one that stuck, and not for the reason I expected."
syn["meet-claude"] = "Early on, my chats with Claude ran long, and every time he'd start losing details and answering things I didn't say. It reminded me of my daughter the night she fractured her skull at rugby: nodding, but the lights flickering. He wasn't broken, he was overloaded. The opposite failure, 'make this better' with no context, is just as bad. This is how I learned what a context window is, the hard way."
syn["whos-driving"] = "Every Sunday night a bot named Charles writes Erin a brief about Fiona's week. This one flagged Monday drop-off and pickup as unassigned. I didn't read it. Between Charles and Erin, Skippy rewrote the brief and two of the gaps disappeared, and Bob caught it with a check I don't remember adding. Then there's why Monday looked empty in the first place."
assert not any("—" in v for v in syn.values())
wr("data/synopses.json", json.dumps(syn, indent=1, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- run the pipeline
def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"$ {cmd}\n{r.stdout.strip()[-1500:]}\n{r.stderr.strip()[-800:]}")
    return r.returncode
run("python3 shelf/enrich.py | tail -4")
run("python3 shelf/fold.py | tail -1")
run("python3 build.py | tail -2")

# ---------------------------------------------------------------- diagnostics
L = json.loads(rd("data/library.json"))
trunc = [x["title"] for x in L if not re.search(r'[.!?"”)\]]\s*$', x["summary"])]
print("still-truncated summaries:", trunc)
print("em dashes in library:", sum("—" in json.dumps(x, ensure_ascii=False) for x in L))
from collections import Counter
c = Counter(t for v in tags.values() for t in v)
print(f"tags: {len(c)} distinct; singletons: {[t for t,n in c.items() if n==1]}")
P = json.loads(rd("data/posts.json"))
for x in P["library"]:
    if x.get("named_in") or x.get("cited"):
        print(f"  {x['title'][:28]:28} cited={len(x['cited'])} named_in={len(x['named_in'])}")
print("authors sample:", [ (x["title"], x["author"]) for x in L if x["title"] in ("Accelerate","Team Topologies","Nonviolent Communication","Remembrance of Earth's Past (Three-Body)")])
print("shelves:", Counter(x["shelf"] for x in L))
