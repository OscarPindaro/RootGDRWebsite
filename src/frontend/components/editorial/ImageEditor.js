(function () {
  if (window.__rootGdrImageEditor) return;
  window.__rootGdrImageEditor = true;

  function errorMessage(status) {
    if (status === 401 || status === 403) return "Non hai i permessi per modificare questa immagine.";
    if (status === 413) return "L’immagine è troppo grande.";
    if (status === 409) return "La scheda è cambiata. Ricarica la pagina e riprova.";
    if (status === 422) return "Il file non è un’immagine PNG, JPEG, GIF o WebP valida.";
    return "Non è stato possibile completare l’operazione. Riprova.";
  }

  async function request(url, options) {
    var response = await fetch(url, Object.assign({
      credentials: "same-origin",
      headers: {Accept: "application/json"},
    }, options || {}));
    if (!response.ok) throw new Error(errorMessage(response.status));
    return response.status === 204 ? null : response.json();
  }

  function announce(root, message, error) {
    var output = root.querySelector("[data-image-error]") || root.querySelector("[data-image-status]");
    if (!output) return;
    output.textContent = message;
    output.hidden = !message;
    output.dataset.state = error ? "error" : "";
  }

  function actionButton(label, testId, action, disabled) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-secondary btn-sm";
    button.textContent = label;
    button.dataset.testid = testId;
    button.disabled = Boolean(disabled);
    button.addEventListener("click", action);
    return button;
  }

  function revisionRow(root, revision) {
    var base = root.dataset.historyUrl;
    var row = document.createElement("article");
    row.className = "image-editor__revision";
    row.dataset.testid = "image-history-revision";
    row.dataset.revisionId = revision.id;

    var image = document.createElement("img");
    image.className = "image-editor__thumb";
    image.src = base + "/" + revision.id + "/content";
    image.alt = "Anteprima " + revision.filename;
    row.appendChild(image);

    var meta = document.createElement("div");
    meta.className = "image-editor__revision-meta";
    var name = document.createElement("p");
    name.className = "image-editor__revision-name";
    name.textContent = revision.filename;
    var detail = document.createElement("p");
    detail.className = "image-editor__revision-detail";
    var date = new Intl.DateTimeFormat("it-IT", {dateStyle: "medium", timeStyle: "short"}).format(new Date(revision.created_at));
    detail.textContent = date + " · " + (revision.uploaded_by_name || "Utente eliminato");
    meta.append(name, detail);
    if (revision.is_current) {
      var current = document.createElement("span");
      current.className = "image-editor__current";
      current.textContent = "Immagine corrente";
      meta.appendChild(current);
    }
    row.appendChild(meta);

    var actions = document.createElement("div");
    actions.className = "image-editor__revision-actions";
    actions.appendChild(actionButton("Ripristina", "image-history-restore", async function () {
      if (!window.confirm("Ripristinare questa immagine?")) return;
      try {
        await request(base + "/" + revision.id + "/restore", {method: "POST"});
        location.reload();
      } catch (error) { announce(root, error.message, true); }
    }, revision.is_current));
    actions.appendChild(actionButton("Elimina", "image-history-delete", async function () {
      if (!window.confirm("Eliminare definitivamente questa revisione?")) return;
      try {
        var suffix = revision.is_current ? "?clear=true" : "";
        await request(base + "/" + revision.id + suffix, {method: "DELETE"});
        location.reload();
      } catch (error) { announce(root, error.message, true); }
    }));
    row.appendChild(actions);
    return row;
  }

  async function loadHistory(root) {
    var list = root.querySelector("[data-image-history-list]");
    list.replaceChildren();
    announce(root, "", false);
    try {
      var payload = await request(root.dataset.historyUrl + "/");
      if (!payload.data.length) {
        var empty = document.createElement("p");
        empty.className = "image-editor__empty";
        empty.textContent = "Non ci sono ancora immagini nello storico.";
        list.appendChild(empty);
        return;
      }
      payload.data.forEach(function (revision) { list.appendChild(revisionRow(root, revision)); });
    } catch (error) { announce(root, error.message, true); }
  }

  async function upload(root, file) {
    if (!file) return;
    var body = new FormData();
    body.append("image", file, file.name);
    announce(root, "Caricamento…", false);
    try {
      await request(root.dataset.uploadUrl, {method: "PUT", body: body});
      location.reload();
    } catch (error) { announce(root, error.message, true); }
  }

  function mount(root) {
    if (root.dataset.enhanced === "true") return;
    root.dataset.enhanced = "true";
    if (root.dataset.editable !== "true") return;

    var input = root.querySelector("[data-image-input]");
    var surface = root.querySelector("[data-image-surface]");
    var form = root.querySelector("[data-image-form]");
    var dialog = root.querySelector("[data-image-history-dialog]");
    var opener = root.querySelector("[data-image-history-open]");
    var close = root.querySelector("[data-image-history-close]");

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      upload(root, input.files[0]);
    });
    input.addEventListener("change", function () { upload(root, input.files[0]); });
    surface.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      input.click();
    });
    ["dragenter", "dragover"].forEach(function (name) {
      surface.addEventListener(name, function (event) {
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
        surface.dataset.dragging = "true";
      });
    });
    ["dragleave", "drop"].forEach(function (name) {
      surface.addEventListener(name, function (event) {
        event.preventDefault();
        delete surface.dataset.dragging;
      });
    });
    surface.addEventListener("drop", function (event) {
      upload(root, event.dataTransfer && event.dataTransfer.files[0]);
    });

    opener.addEventListener("click", function () {
      dialog.showModal();
      loadHistory(root);
      close.focus();
    });
    close.addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("close", function () { opener.focus(); });
    root.querySelector("[data-image-clear]")?.addEventListener("click", async function () {
      if (!window.confirm("Rimuovere l’immagine corrente? Rimarrà nello storico.")) return;
      try {
        await request(root.dataset.historyUrl + "/current", {method: "DELETE"});
        location.reload();
      } catch (error) { announce(root, error.message, true); }
    });

    root.querySelectorAll("[data-image-choices] input").forEach(function (choice) {
      choice.addEventListener("change", async function () {
        var choices = choice.closest("[data-image-choices]");
        var status = root.querySelector("[data-image-status]");
        status.textContent = "Salvataggio…";
        try {
          var payload = {};
          payload[choice.name] = choice.value;
          payload.expected_version = Number(root.dataset.version);
          var updated = await request(choices.dataset.autosaveUrl, {
            method: "PATCH",
            headers: {Accept: "application/json", "Content-Type": "application/json"},
            body: JSON.stringify(payload),
          });
          root.dataset.version = updated.version;
          status.textContent = "Salvato";
          location.reload();
        } catch (error) { announce(root, error.message, true); }
      });
    });
  }

  function mountAll(scope) {
    (scope || document).querySelectorAll("[data-image-editor]").forEach(mount);
  }

  mountAll();
  document.body.addEventListener("htmx:afterSwap", function (event) { mountAll(event.target); });
})();
