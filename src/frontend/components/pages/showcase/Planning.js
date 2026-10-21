const root = document.querySelector("[data-planning]");

if (root) {
  const marked = new Map();
  const feedback = root.querySelector("[data-planning-feedback]");
  const announce = (text) => {
    feedback.textContent = `${text} Nessun dato viene salvato.`;
  };
  const refreshCards = () => {
    // A swapped fixture inherits current marks instead of resetting the demo.
    root.querySelectorAll("[data-track]").forEach((box) => {
      if (marked.has(box.dataset.track)) box.checked = marked.get(box.dataset.track);
      else marked.set(box.dataset.track, box.checked);
    });
    const flipping = root.dataset.cardMode === "flip";
    root.querySelectorAll("[data-npc]").forEach((card) => {
      const back = card.dataset.face === "back";
      card.querySelector("[data-card-front]").hidden = flipping && back;
      card.querySelector("[data-card-back]").hidden = flipping && !back;
      card.querySelector("[data-card-controls]").hidden = !flipping;
      const button = card.querySelector("[data-card-flip]");
      button.setAttribute("aria-expanded", String(back));
      button.querySelector(".btn-label").textContent = back ? "Torna al fronte" : "Gira scheda";
    });
  };
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-reference-open]")) {
      const panel = root.querySelector("[data-reference-panel]");
      panel.hidden = false;
      panel.querySelector("input").focus();
      announce("Bozza di riferimento aperta; il risultato originale resta intatto.");
      return;
    }
    if (event.target.closest("[data-reference-correct]")) {
      const name = root.querySelector("[name='planning-reference-name']").value.trim();
      root.querySelector("[data-reference-result]").textContent =
        name ? `Nome atteso: ${name}. Bozza locale corretta; originale conservato.` : "Scrivi il nome atteso.";
      return;
    }
    if (event.target.closest("[data-demo-undo]")) {
      const blocked = root.querySelector("[name='planning-later-edit']").checked;
      root.querySelector("[data-undo-result]").textContent = blocked
        ? "Annullamento bloccato: una modifica successiva deve essere riconciliata."
        : "Richiesta annullata nella prova. Nessun dato reale e cambiato.";
      return;
    }
    const reputation = event.target.closest("[data-reputation-delta]");
    if (reputation) {
      const value = reputation.closest("[data-reputation]").querySelector("[data-reputation-value]");
      value.textContent = Math.max(-3, Math.min(3, Number(value.textContent) + Number(reputation.dataset.reputationDelta)));
      announce("Reputazione corretta manualmente per questa prova.");
      return;
    }
    const choice = event.target.closest("[data-card-mode-choice]");
    if (choice) {
      root.dataset.cardMode = choice.dataset.cardModeChoice;
      root.querySelectorAll("[data-card-mode-choice]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button === choice));
      });
      refreshCards();
      announce("Presentazione cambiata; i tracciati restano gli stessi.");
      return;
    }
    const flip = event.target.closest("[data-card-flip]");
    const card = event.target.closest("[data-npc]");
    const interactive = event.target.closest("button, input, label, a, select, textarea, fieldset");
    if (card && root.dataset.cardMode === "flip" && (flip || !interactive)) {
      card.dataset.face = card.dataset.face === "back" ? "front" : "back";
      refreshCards();
    }
  });
  root.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.matches("[data-demo-request]")) {
      event.preventDefault();
      const response = root.querySelector("[data-demo-response]");
      response.hidden = false;
      root.querySelector("[data-request-echo]").textContent =
        new FormData(form).get("planning-request");
      announce("Risultato preregistrato mostrato, senza chiamare un modello.");
    } else if (form.matches("[data-demo-evaluation]")) {
      event.preventDefault();
      const count = Number(new FormData(form).get("planning-produced-count"));
      root.querySelector("[data-produced-count]").textContent = String(count);
      const verdict = root.querySelector("[data-evaluation-verdict]");
      verdict.dataset.passed = String(count === 1);
      verdict.textContent = count === 1
        ? "Controlli esatti superati nella prova. Giudizio illustrativo: 4/5. Nessuna esecuzione reale."
        : "Non superato: numero di personaggi diverso da 1. Il giudizio illustrativo 4/5 non annulla questo errore.";
    } else if (form.matches("[data-demo-settings]")) {
      event.preventDefault();
      root.querySelector("[data-settings-version]").textContent =
        "Bozza illustrativa v2. Le richieste precedenti restano su v1; nessun prompt attivo e cambiato.";
    }
  });
  root.addEventListener("change", (event) => {
    if (event.target.matches("[data-demo-files]")) {
      root.querySelector("[data-demo-file-list]").textContent =
        Array.from(event.target.files).map((file) => file.name).join(" / ") || "Nessun file scelto.";
      announce("Nomi degli allegati mostrati soltanto nel browser.");
      return;
    }
    if (event.target.matches("#planning-view")) {
      window.location.href = `/components/planning?view=${encodeURIComponent(event.target.value)}`;
      return;
    }
    if (!event.target.matches("[data-track]")) return;
    const key = event.target.dataset.track;
    marked.set(key, event.target.checked);
    root.querySelectorAll("[data-track]").forEach((box) => {
      if (box.dataset.track === key) box.checked = event.target.checked;
    });
    announce("Tracciato modificato per questa prova.");
  });
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (root.contains(event.target)) refreshCards();
  });
  const resolution = root.querySelector("[data-resolution-form]");
  if (resolution) {
    resolution.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!resolution.reportValidity()) return;
      root.querySelector("[data-resolution-text]").textContent =
        new FormData(resolution).get("planning-resolution");
      root.querySelector("[data-resolution]").hidden = false;
      root.querySelector("[data-conflict-status]").textContent = "Risolto";
      const dialog = resolution.closest("dialog");
      // Use the real close control so the shared Dialog restores its opener.
      dialog.querySelector("[data-dialog-close]").click();
      announce("Risoluzione mostrata nella storia.");
    });
  }
  refreshCards();
}
