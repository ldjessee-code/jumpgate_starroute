# Bug: full screen does not fill a large monitor

Recorded 2026-09-28. Not fixed. Needs a layout review before another pass.

## What happened

On a large desktop monitor, the in-app Full screen control (the button on the map, not the browser’s own full screen) hid the header and footer, then left the map as a short strip across the top. Legend on the left, plot in the middle, route controls on the right. The rest of the window underneath was empty.

That is the opposite of full screen. The plot, legend, and controls should fill the monitor.

The page was http://127.0.0.1:8050/ with the 309-star map. From was Sol, To was TOI-4336 A, 11 jumps. The window was wide (on the order of 3800 pixels).

## What should happen

- Full screen is only for the Map tab. Who lives where and Choose the stars stay normal scrolling pages. Docs and Home already scroll and should be left alone.
- While Full screen is on, the map area fills the window: legend, plot, and route controls, edge to edge, no empty band under the plot.
- While Full screen is off, the plot stays about as tall as it is wide, and the Map page scrolls. A narrow window folds Route, Legend, and Save into one line each.

## Where to look

Styles are in `starroute/web/static/css/app.css`. The button only toggles `body.map-fullscreen` in `starroute/web/static/js/app.js`. It does not use the browser full-screen API.

`#star-map` is `position: absolute`, so it does not give `.map-stage` a height. Outside full screen the stage gets its height from `aspect-ratio: 1 / 1`. In full screen that ratio is turned off (`body.map-fullscreen .map-stage` sets `height: auto`), and `body.map-first main` is also `height: auto` unless a later rule wins. A `height: 100%` on the card then has no parent height to use, so the row stays as tall as the side controls. That matches the short strip in the screenshot.

Earlier the same layout also collapsed when a short route was chosen (`main { margin: 0 auto }` on a flex column) and, on a narrow window, squeezed the plot into a thin line. Those two were patched. This full-screen fill is still broken. Do not stack another override on the old ones without checking the whole height chain: `body.map-fullscreen` → `main` → `#screen-map` → `.map-layout` → `.map-card` → `.map-work` → `.map-stage` → `#star-map`.
