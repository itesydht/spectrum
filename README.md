# Spectrum

Every story from [I Tried Everything So You Don't Have To](https://pulse.itesydht.com), on one dial.
Pulse is the Tuesday transmission; Spectrum is the whole band.

Live: https://spectrum.itesydht.com (Cloudflare Pages, deploys from `main`).

## How it works

- `build.py` walks the published archive through Substack's public post API (newest to oldest, following `previous_post_slug`), extracts facts (title, subtitle, date, series, excerpt, key lines, cross-links), and writes `data/posts.json`. Facts come from the archive; nothing is hand-filed.
- `data/tags.json` is the human layer: `slug -> [keywords]`. Edit freely. A new story shows up untagged until it gets a line here (the build prints which ones).
- `data/library.json` is the library (books, podcasts, talks). Each entry links to the stories it sits behind:

  ```json
  { "kind": "book", "band": "behind|namesakes|library", "title": "...", "author": "...", "year": 2016, "status": "reading|finished|",
    "url": "https://...", "why": "one line on why it's on the shelf",
    "tags": ["systems thinking"], "stories": ["the-simplest-system"] }
  ```

- `index.html` is the whole site: no build step, no framework. It fetches `data/posts.json` and filters in the browser.

## Rebuild

Runs on Tycho (the egress proxy elsewhere blocks the publication host):

```
python3 build.py          # rebuild data/posts.json
python3 build.py --check  # exit 1 if a rebuild would change it
```

A Tuesday-afternoon cron runs the build and commits when `--check` says something moved.
