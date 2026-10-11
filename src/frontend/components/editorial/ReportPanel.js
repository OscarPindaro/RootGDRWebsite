/* Loads the report panel bundle on demand.

   The controller renders the page to a PNG, so it is built by esbuild into
   /static/js/report.js like the other editors. This loader is what the
   component declares, so a page that renders the panel fetches the bundle. */
(function () {
  if (window.__rootGdrReportBundle) return;
  window.__rootGdrReportBundle = true;
  var script = document.createElement("script");
  script.src = "/static/js/report.js";
  script.defer = true;
  document.body.appendChild(script);
})();
