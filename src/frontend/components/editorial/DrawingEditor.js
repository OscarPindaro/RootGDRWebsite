/* The drawing editor's client side: explicit save.

   The drawing tools arrive in later tickets; this script owns the one thing
   that must be right from the start — the document on the server is never
   advanced except by a save the server acknowledged, and a conflicting save is
   never applied silently.

   The scene itself is embedded as JSON by the component. This script keeps the
   last acknowledged server value and its version, sends the whole document on
   an explicit save, and reports dirty state, failures and conflicts.
*/
(function () {
  if (window.__rootGdrDrawingEditor) return;
  window.__rootGdrDrawingEditor = true;

  function sceneOf(root) {
    var script = root.querySelector("[data-drawing-scene]");
    if (!script) return null;
    try {
      return JSON.parse(script.textContent);
    } catch (error) {
      return null;
    }
  }

  function status(root, message, state) {
    // The page owns one save indicator (common.SaveIndicator, in layout.Page);
    // the drawing editor is another writer of it, not a second indicator.
    var output = document.querySelector("[data-autosave-status]");
    if (!output) return;
    output.textContent = message;
    output.hidden = !message;
    if (state) output.dataset.state = state;
    else delete output.dataset.state;
  }

  function announce(root, message) {
    var output = root.querySelector("[data-drawing-error]");
    if (!output) return;
    output.textContent = message;
    output.hidden = !message;
  }

  function errorMessage(statusCode) {
    if (statusCode === 401 || statusCode === 403)
      return "Non hai i permessi per modificare questo disegno.";
    if (statusCode === 404) return "Il disegno non esiste più.";
    if (statusCode === 409)
      return "Il disegno è cambiato in un'altra scheda. Ricarica la pagina per vedere la versione più recente.";
    if (statusCode === 422) return "Il disegno non è valido e non è stato salvato.";
    return "Non è stato possibile salvare. Riprova.";
  }

  function createEditor(root) {
    var scene = sceneOf(root);
    var savedScene = scene ? JSON.stringify(scene) : null;
    var savedVersion = Number(root.dataset.version || 0) || null;
    var saveUrl = root.dataset.saveUrl || null;
    var inFlight = false;

    function isDirty() {
      return Boolean(scene) && JSON.stringify(scene) !== savedScene;
    }

    function refresh() {
      root.dataset.dirty = isDirty() ? "true" : "false";
      if (root.dataset.saving === "true") return;
      status(root, isDirty() ? "Modifiche non salvate" : "Salvato", isDirty() ? "dirty" : "saved");
    }

    async function save() {
      if (!saveUrl || !scene || inFlight) return;
      inFlight = true;
      root.dataset.saving = "true";
      status(root, "Salvataggio…", "saving");
      announce(root, "");
      var saved = false;
      try {
        var response = await fetch(saveUrl, {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ expectedVersion: savedVersion, scene: scene }),
        });
        if (!response.ok) {
          announce(root, errorMessage(response.status));
          return;
        }
        var updated = await response.json();
        savedScene = JSON.stringify(updated.scene);
        savedVersion = updated.version;
        saved = true;
      } catch (error) {
        announce(root, "Rete non raggiungibile. Il disegno non è stato salvato.");
      } finally {
        inFlight = false;
        delete root.dataset.saving;
        // A failed save must never read as "Salvato": the local scene is kept,
        // and the status says so.
        if (saved) refresh();
        else status(root, "Non salvato", "error");
      }
    }

    return { save: save, isDirty: isDirty, refresh: refresh };
  }

  function mount(root) {
    if (root.dataset.drawingMounted === "true") return;
    if (root.dataset.readonly === "true") return;
    root.dataset.drawingMounted = "true";
    var editor = createEditor(root);
    root.__drawingEditor = editor;

    var saveButton = root.querySelector("[data-testid='drawing-save']");
    if (saveButton) saveButton.addEventListener("click", function () { editor.save(); });

    root.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        editor.save();
      }
    });

    window.addEventListener("beforeunload", function (event) {
      if (!editor.isDirty()) return;
      event.preventDefault();
      event.returnValue = "";
    });

    editor.refresh();
  }

  function mountAll() {
    document.querySelectorAll("[data-drawing-editor]").forEach(mount);
  }

  mountAll();
  document.body.addEventListener("htmx:afterSwap", mountAll);
})();
