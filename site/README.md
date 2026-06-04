# ASD Research Site

This folder is a static website generated from the local ASD research agent database.

Share `index.html` directly, or publish the whole `site/` folder with GitHub Pages, Netlify, Vercel, or any static web host.

Study-type subpages are generated under `topics/`, including `topics/therapy/`, `topics/non-therapy/`, and `topics/medication/`.

Regenerate it with:

```bash
python3 -m research_agent.cli export-site
```
