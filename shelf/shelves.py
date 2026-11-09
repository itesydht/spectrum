#!/usr/bin/env python3
"""Lift Eddy's book shelves from story-workshop/reference/cultural-profile.md into shelf/shelves.json.
Each '### Section' under 'Books / Audible' becomes a shelf; bold series names and 'Title — Author.' lines become entries."""
import json, re, sys, pathlib
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "~/projects/story-workshop/reference/cultural-profile.md").expanduser()
OUT = pathlib.Path(__file__).resolve().parent / "shelves.json"
txt = SRC.read_text(encoding="utf-8")
body = txt[txt.index("## Books / Audible"):]
body = body[:body.index("## What This Tells You")] if "## What This Tells You" in body else body
shelves, cur = {}, None
for line in body.splitlines():
    m = re.match(r"^### (.+?)\s*$", line)
    if m:
        cur = re.sub(r"\s*—.*$", "", m.group(1)).strip(); shelves[cur] = []; continue
    if not cur or not line.strip(): continue
    b = re.match(r"^\*\*(.+?)\s*\(", line) or re.match(r"^\*\*(.+?)\*\*", line)
    if b:
        shelves[cur].append(b.group(1).replace(" Universe", "").strip()); continue
    for part in re.split(r"\.\s+(?=[A-Z])", line.strip()):
        t = re.sub(r"\s*—.*$", "", part).strip(" .")
        t = re.sub(r"\s*\(x2.*\)$", "", t)
        if len(t) > 3 and not t.lower().startswith(("all ", "full ", "this is", "and more", "apple series", "ai characters", "not till", "outland", "earthside")):
            shelves[cur].append(t)
json.dump(shelves, open(OUT, "w"), indent=1, ensure_ascii=False)
print({k: len(v) for k, v in shelves.items()})
