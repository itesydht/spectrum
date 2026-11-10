# Spectrum copy

Working record of the words on the site, the alternatives considered, and why. Edit here first, then mirror into `index.html` (`COPY` object) or `README`. House style follows `story-workshop/process/writing-style.md` and `edit-patterns.md`: no em dashes; no sentence ends on a preposition, linking verb, or weak function word; fragments in pairs or triplets; offer, don't command.

## Names (decided 2026-11-09)

| Thing | Chosen | Considered | Why |
|---|---|---|---|
| Site | Spectrum | Cartographer, Library, Corpus, Reference, Archive, Knowledge | Pulse is the signal; Spectrum is the whole band. Radio family. |
| Stories view (nav, both sites) | Story Locator | All Stories, Story Finder, Find a Story, Tune In, Story Intelligence | Verb beats noun; "Locator" sounds like it came off the same panel as Pulse and Spectrum. "Finder" sounds like a Mac. "Intelligence" collides with the Intelligence Series. |
| Library view (nav, both sites) | Source Material | Library, Shelf, Reading List, Reference Material, Behind the Stories, The Shelf | What the stories were made from, not what you consult. Only true of the behind/namesake cards, so the view opens on those 23 with "Everything I've read" one chip away. |
| Library chips | Source material · Everything I've read · Namesakes · Behind the stories · shelves | All | Default chip must agree with the nav label. |
| Post button (Substack template) | Find the next story → | Every story, one dial →; More like this → | Action for readers who don't know the name yet; the line under it does the naming. |
| Line under the button | Spectrum: every story, the series they belong to, and the source material behind them. | | |

## Story Locator headline and lede

Chosen:

> **Every story. One dial.**
> Find the signal. {N} Tuesdays so far: health, family, leadership, and an AI crew on a Mac Mini. A word, a name, or a feeling, and the dial narrows to the stories that match.

{N} is `posts.length` spelled out, so it stays true after every Tuesday rebuild.

Considered: "Find the story you're looking for." (ends on "for", retired 2026-11-09); "Find the signal." as the headline; "Thirty-four Tuesdays." as a count headline in the Substack subtitle style; lede ending "…to the stories that carry it" (ends on "it").

## Source Material headline and lede

Chosen:

> **The sources behind the stories.**
> {M} that shaped how I think, and the names they gave this place: Holden, Skippy, Tycho, Bob. Each card says which stories it stands behind. Everything else I've listened to is one chip away.

{M} is the count of cards in the behind or namesakes bands. "Sources", not "books": podcasts and videos are coming.

Considered: "The source material behind the stories."; "The books behind the stories." (too narrow once podcasts land); "Where the names came from." (true for namesakes only); lede with "books and series for now, podcasts next" (reads like a roadmap; the cards can show format instead).

## Post blocks (revised 2026-11-09, after the first retrofit)

The end button used to deep link to the story's own card, which showed a reader the story they had just finished. Split into two jobs:

- Top line: "Every story, one dial. Find the signal on Spectrum." → `https://spectrum.itesydht.com` (fixed).
- End block: bold "Find the next story.", the "Spectrum is the dial for the rest…" paragraph, button "Find the next story →" → `https://spectrum.itesydht.com` (fixed, never edited per story).
- Under the button, one centered text line: "Behind this story: what it builds on and the source material." with "Behind this story" linked to `https://spectrum.itesydht.com/#<slug>` (the only per-story edit).
- On Spectrum, the story card carries "Browse all stories" beside "Read the story" so a deep link is never a dead end.

## Source Material default (revised 2026-11-10)

The view now opens on everything (67), with the source cards (behind a story or a namesake) sorted to the top, instead of opening filtered to those 23. Eddy: landing on a filtered list "feels a little bit off." The "Source material" chip still filters to the 23. Lede: "{N} I've listened to. The {M} that shaped a story or gave this place a name come first: Holden, Skippy, Tycho, Bob. Each card says which stories it stands behind."

## Open

- Why-lines for the 23 source cards (Eddy to dictate).
- Button label may change once we see click-through.
