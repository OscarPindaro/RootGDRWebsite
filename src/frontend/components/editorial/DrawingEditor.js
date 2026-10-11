/* Loads the drawing editor bundle on demand.

   The controller is a bundled module (it imports the geometry, scene and
   renderer), so it is built by esbuild into /static/js/drawings.js like the
   Markdown editor. This loader is what the component declares, so a page that
   renders the workspace — and only that page — fetches the bundle. */
(function () {
  if (window.__rootGdrDrawingBundle) return;
  window.__rootGdrDrawingBundle = true;
  var script = document.createElement("script");
  script.src = "/static/js/drawings.js";
  script.defer = true;
  document.body.appendChild(script);
})();
