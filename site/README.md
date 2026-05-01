# site/

A small static site that explains the project visually. No build step.

## Open locally

Just double-click `index.html`, or:

```powershell
cd site
py -m http.server 8000
# open http://localhost:8000
```

## Pages

- `index.html` — overview, hero, quickstart, why two providers
- `architecture.html` — three-stage agent loop, schemas, provider details
- `cost.html` — pricing table, routing, budget enforcement, evals
- `sample.html` — rendered preview of the agent's actual output

## Stack

- TailwindCSS via CDN (no build)
- `assets/styles.css` for design tokens, code blocks, diagram
- `assets/main.js` for active-nav highlight and copy buttons
- Inter + JetBrains Mono via Google Fonts

## Publishing

The whole `site/` folder is static. To serve it from GitHub Pages:
Settings → Pages → Source: `main` branch, `/site` folder.
