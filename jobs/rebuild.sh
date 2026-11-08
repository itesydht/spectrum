#!/bin/bash
# Rebuild data/posts.json from the live archive and push if anything moved.
# Installed on Tycho as a launchd job (jobs/com.itesydht.spectrum.rebuild.plist).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
git pull -q --ff-only
if python3 build.py --check >/dev/null 2>&1; then
  echo "$(date -u +%FT%TZ) unchanged"; exit 0
fi
python3 build.py
git add data/posts.json
git -c user.name="Tycho" -c user.email="eddy@pobox.com" commit -q -m "Rebuild index: $(python3 -c "import json;print(len(json.load(open('data/posts.json'))['posts']))") stories

Job: spectrum-rebuild"
git push -q
echo "$(date -u +%FT%TZ) pushed"
