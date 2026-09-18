# Static preview

Open `index.html` or `../starroute/web/static/app.html` in a browser.

No virtualenv. The 3D map is Plotly.js plus shipped JSON snapshots. The
crowded pack boots from `default-map.js`; the toolbar switches among
`crowded`, `sparse`, and `lonely_humans` under
`../starroute/web/static/presets/`. Python is only required to regenerate
those packs (`python -m starroute build-presets`).
