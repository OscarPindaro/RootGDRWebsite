const root = document.querySelector("[data-planning]");

if (root) {
  const feedback = root.querySelector("[data-planning-feedback]");
  const announce = (text) => {
    feedback.textContent = `${text} Nessun dato viene salvato.`;
  };
  const refreshCards = () => {
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
  root.addEventListener("change", (event) => {
    if (!event.target.matches("[data-track]")) return;
    const key = event.target.dataset.track;
    root.querySelectorAll("[data-track]").forEach((box) => {
      if (box.dataset.track === key) box.checked = event.target.checked;
    });
    announce("Tracciato modificato per questa prova.");
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
