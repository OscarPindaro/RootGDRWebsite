/* Loads the report panel bundle on demand.

   The controller renders the page to a PNG, so it is built by esbuild into
   /static/js/report.js like the other editors. This loader is what the
   component declares, so a page that renders the panel fetches the bundle.
   A failed request is not a loaded panel: the panel says so and offers one
   retry on the same page. */
(function () {
  if (window.__rootGdrReportBundle) return;
  var panel = document.getElementById("report-panel");
  if (panel === null) return;
  window.__rootGdrReportBundle = "loading";

  var status = panel.querySelector("[data-report-status]");
  var retry = null;
  var loading = false;
  var failed = false;

  function showFailure() {
    failed = true;
    if (status === null) return;
    status.textContent = "Non è stato possibile caricare la segnalazione.";
    status.dataset.state = "failed";
    if (retry === null) {
      retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-secondary btn-sm";
      retry.setAttribute("data-report-retry", "");
      retry.textContent = "Riprova";
      retry.addEventListener("click", load);
      status.after(retry);
    }
    retry.hidden = false;
  }

  function hideFailure() {
    if (retry !== null) retry.hidden = true;
    if (failed && status !== null) {
      status.textContent = "";
      delete status.dataset.state;
    }
    failed = false;
  }

  function load() {
    if (loading) return;
    loading = true;
    window.__rootGdrReportBundle = "loading";
    hideFailure();
    var script = document.createElement("script");
    script.src = "/static/js/report.js";
    script.defer = true;
    script.addEventListener("load", function () {
      loading = false;
      window.__rootGdrReportBundle = "ready";
      hideFailure();
    });
    script.addEventListener("error", function () {
      loading = false;
      window.__rootGdrReportBundle = "failed";
      showFailure();
    });
    document.body.appendChild(script);
  }

  load();
})();
