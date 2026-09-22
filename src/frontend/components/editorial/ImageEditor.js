(function () {
  if (window.__rootGdrImageEditor) return;
  window.__rootGdrImageEditor = true;

  // The confirmation dialog is one shared element; each action sets its own
  // copy and stores the request it should run when confirmed.
  var confirmActions = new WeakMap();

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

  function setStatus(root, message, error) {
    var status = root.querySelector("[data-image-status]");
    if (!status) return;
    status.textContent = message;
    status.dataset.state = error ? "error" : "";
  }

  function revisionContentUrl(root, revisionId) {
    return root.dataset.historyUrl + "/" + revisionId + "/content";
  }

  // Replace the visible media without a reload: the fallback face is hidden
  // while an uploaded image is shown, and shown again when the image is gone.
  function setCurrentImage(root, url) {
    var surface = root.querySelector("[data-image-surface]");
    if (!surface) return;
    var overlay = surface.querySelector(".image-editor__overlay");
    var image = surface.querySelector("[data-image-current]");
    var fallback = surface.querySelector(".image-editor__fallback");
    if (url) {
      if (!image) {
        image = document.createElement("img");
        image.className = "image-editor__image";
        image.alt = root.dataset.imageLabel || "";
        image.dataset.imageCurrent = "";
        surface.insertBefore(image, overlay);
      }
      image.src = url;
      if (fallback) fallback.hidden = true;
    } else {
      if (image) image.remove();
      if (fallback) fallback.hidden = false;
    }
    if (overlay) overlay.textContent = url ? "Cambia immagine" : "Carica immagine";
    var clear = root.querySelector("[data-image-clear]");
    if (clear) clear.hidden = !url;
  }

  // A metadata change leaves an uploaded image untouched; when the generated
  // fallback is visible, its tint and the selected symbol mark are updated from
  // the response so the face reflects the persisted document.
  function renderFace(root, updated) {
    if (root.querySelector("[data-image-current]")) return;
    var face = root.querySelector(".face");
    if (!face) return;
    if (updated.tint) face.style.setProperty("--c", "var(--" + updated.tint + ")");
    var mark = root.querySelector(
      "[data-image-choices] .choice-grid__input:checked + .choice-grid__mark"
    );
    var target = face.querySelector(".face__emoji, .face__shape");
    if (!mark || !target) return;
    target.innerHTML = mark.innerHTML;
    if (target.classList.contains("face__emoji")) {
      target.setAttribute("aria-label", mark.textContent.trim());
    }
  }

  function syncMedia(root, payload) {
    var current = payload.data.find(function (revision) { return revision.is_current; });
    setCurrentImage(root, current ? revisionContentUrl(root, current.id) : null);
  }

  function openConfirm(root, config, opener) {
    var dialog = root.querySelector("[data-image-confirm]");
    var run = dialog.querySelector("[data-image-confirm-run]");
    dialog.querySelector(".dialog-title").textContent = config.title;
    dialog.querySelector("[data-image-confirm-message]").textContent = config.message;
    run.querySelector(".btn-label").textContent = config.confirmLabel;
    run.classList.toggle("btn-danger", config.destructive);
    run.classList.toggle("btn-secondary", !config.destructive);
    confirmActions.set(dialog, config.action);
    window.rootGdrDialog.open(dialog, opener);
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
    actions.appendChild(actionButton("Ripristina", "image-history-restore", function (event) {
      openConfirm(root, {
        title: "Ripristina immagine",
        message: "Ripristinare questa immagine? Diventerà l’immagine corrente.",
        confirmLabel: "Ripristina",
        destructive: false,
        action: function () {
          return request(base + "/" + revision.id + "/restore", {method: "POST"});
        },
      }, event.currentTarget);
    }, revision.is_current));
    actions.appendChild(actionButton("Elimina", "image-history-delete", function (event) {
      var suffix = revision.is_current ? "?clear=true" : "";
      openConfirm(root, {
        title: "Elimina revisione",
        message: "Eliminare definitivamente questa revisione? L’operazione non è reversibile.",
        confirmLabel: "Elimina",
        destructive: true,
        action: function () {
          return request(base + "/" + revision.id + suffix, {method: "DELETE"});
        },
      }, event.currentTarget);
    }));
    row.appendChild(actions);
    return row;
  }

  async function loadHistory(root) {
    var list = root.querySelector("[data-image-history-list]");
    if (!list) return null;
    list.replaceChildren();
    announce(root, "", false);
    try {
      var payload = await request(root.dataset.historyUrl + "/");
      if (!payload.data.length) {
        var empty = document.createElement("p");
        empty.className = "image-editor__empty";
        empty.textContent = "Non ci sono ancora immagini nello storico.";
        list.appendChild(empty);
      } else {
        payload.data.forEach(function (revision) { list.appendChild(revisionRow(root, revision)); });
      }
      return payload;
    } catch (error) {
      announce(root, error.message, true);
      return null;
    }
  }

  // After a confirmed mutation the revision list and the visible media are
  // rebuilt from the API, so nothing reloads the page.
  async function refresh(root) {
    var payload = await loadHistory(root);
    if (payload) syncMedia(root, payload);
    return payload;
  }

  async function upload(root, file) {
    if (!file) return;
    var body = new FormData();
    body.append("image", file, file.name);
    setStatus(root, "Caricamento…", false);
    try {
      var updated = await request(root.dataset.uploadUrl, {method: "PUT", body: body});
      root.dataset.version = updated.version;
      var url = updated.imageUrl ? updated.imageUrl + "?v=" + updated.version : null;
      setCurrentImage(root, url);
      setStatus(root, "Salvato", false);
    } catch (error) { setStatus(root, error.message, true); }
  }

  function mount(root) {
    if (root.dataset.enhanced === "true") return;
    root.dataset.enhanced = "true";
    if (root.dataset.editable !== "true") return;

    var input = root.querySelector("[data-image-input]");
    var surface = root.querySelector("[data-image-surface]");
    var form = root.querySelector("[data-image-form]");
    var confirmDialog = root.querySelector("[data-image-confirm]");

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

    confirmDialog.querySelector("[data-image-confirm-run]").addEventListener("click", async function () {
      var action = confirmActions.get(confirmDialog);
      if (!action) return;
      window.rootGdrDialog.setPending(confirmDialog, true);
      try {
        await action();
        window.rootGdrDialog.close(confirmDialog);
        await refresh(root);
      } catch (error) {
        window.rootGdrDialog.setPending(confirmDialog, false);
        window.rootGdrDialog.showError(confirmDialog, error.message);
      }
    });

    root.querySelector("[data-image-clear]")?.addEventListener("click", function (event) {
      openConfirm(root, {
        title: "Rimuovi immagine",
        message: "Rimuovere l’immagine corrente? Rimarrà nello storico.",
        confirmLabel: "Rimuovi",
        destructive: true,
        action: function () {
          return request(root.dataset.historyUrl + "/current", {method: "DELETE"});
        },
      }, event.currentTarget);
    });

    root.querySelectorAll("[data-image-choices] input").forEach(function (choice) {
      choice.addEventListener("change", async function () {
        var choices = choice.closest("[data-image-choices]");
        setStatus(root, "Salvataggio…", false);
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
          renderFace(root, updated);
          setStatus(root, "Salvato", false);
        } catch (error) { setStatus(root, error.message, true); }
      });
    });
  }

  function mountAll(scope) {
    (scope || document).querySelectorAll("[data-image-editor]").forEach(mount);
  }

  // The history trigger can live outside the editor (the world cover places it
  // in the section heading), so opening it is delegated to the document and the
  // dialog id links the trigger back to its editor.
  document.addEventListener("click", function (event) {
    if (!(event.target instanceof Element)) return;
    var trigger = event.target.closest("[data-image-history-open]");
    if (!trigger) return;
    var dialogId = trigger.getAttribute("data-dialog-open");
    var dialog = dialogId ? document.getElementById(dialogId) : null;
    var root = (dialog && dialog.closest("[data-image-editor]")) ||
      trigger.closest("[data-image-editor]");
    if (root) loadHistory(root);
  });

  mountAll();
  document.body.addEventListener("htmx:afterSwap", function (event) { mountAll(event.target); });
})();
