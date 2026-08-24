# OpenCamp Atlas — public site

Public marketing, support, privacy, and terms pages for **OpenCamp Atlas**,
a camping map for nomads, vanlifers, and RV travelers.

Live at <https://noktirnal42.github.io/opencamp-atlas/>

The app source is private. This repository holds only the public pages.

## Editing the legal pages

Do not edit `privacy.html`, `terms.html`, `community-rules.html`,
`moderation.html`, or `safety.html` by hand. They are generated from the
markdown in the app repository at `docs/legal/`, which is the single source
of truth:

```
python3 tools/build_legal_site.py --out /path/to/opencamp-atlas-site
```

The generator refuses to write a page that still contains an unfilled
placeholder, so a policy can never ship with a hole in it.

`index.html` and `support.html` are hand-written and edited here directly.
