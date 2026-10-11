export function createCanvasPalette(root, editor) {
  const dialog = root.querySelector("#drawing-command-dialog");
  const input = dialog.querySelector("[data-canvas-command-input]");
  const list = dialog.querySelector("[data-canvas-command-options]");
  const guided = dialog.querySelector("[data-canvas-command-action]");
  const output = dialog.querySelector("[data-canvas-command-status]");
  let mode = "compact", active = 0, choices = [];

  function commands() {
    return editor.actions().filter(action => !action.id.startsWith("tool-") && !action.id.startsWith("preset-") && action.id !== "ellipse-parameter");
  }

  function position() {
    if (!dialog.open) return;
    const canvas = root.querySelector("[data-drawing-artboard]").getBoundingClientRect();
    const box = dialog;
    box.style.left = Math.max(8, Math.min(canvas.x + canvas.width / 2 - box.offsetWidth / 2, window.innerWidth - box.offsetWidth - 8)) + "px";
    box.style.top = Math.max(8, Math.min(canvas.y + 16, window.innerHeight - box.offsetHeight - 8)) + "px";
  }

  function render() {
    const term = input.value.trim().toLocaleLowerCase();
    choices = commands().filter(action => action.label.toLocaleLowerCase().includes(term) || action.id.includes(term));
    active = Math.max(0, Math.min(active, choices.length - 1));
    list.replaceChildren(...choices.map((action, index) => {
      const option = document.createElement("li");
      option.className = "drawing-editor__command-option";
      option.id = `canvas-command-option-${index}`;
      option.textContent = action.label;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(index === active));
      option.setAttribute("aria-disabled", String(!action.enabled));
      option.addEventListener("click", () => apply(action.id));
      return option;
    }));
    if (choices.length) input.setAttribute("aria-activedescendant", `canvas-command-option-${active}`);
    else input.removeAttribute("aria-activedescendant");
    const previous = guided.value;
    guided.replaceChildren(...commands().map(action => {
      const option = new Option(action.label, action.id);
      option.disabled = !action.enabled;
      return option;
    }));
    if ([...guided.options].some(option => option.value === previous)) guided.value = previous;
    output.textContent = choices.length ? "Unità vettoriali della tavola. Scegli un comando." : "Nessun comando corrisponde al testo.";
    position();
  }

  function setMode(next) {
    if (!["compact", "guided"].includes(next)) return;
    mode = next;
    dialog.querySelectorAll("[data-canvas-mode]").forEach(button => {
      const selected = button.dataset.canvasMode === mode;
      button.classList.toggle("btn-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    dialog.querySelector("[data-canvas-compact]").hidden = mode !== "compact";
    dialog.querySelector("[data-canvas-guided]").hidden = mode !== "guided";
    position();
  }

  function apply(id) {
    if (!editor.execute(id)) { output.textContent = "Comando non disponibile o parametri non validi."; return; }
    window.rootGdrDialog.close(dialog);
  }

  input.addEventListener("input", () => { active = 0; render(); });
  input.addEventListener("keydown", event => {
    if (["ArrowDown", "ArrowUp"].includes(event.key) && choices.length) {
      event.preventDefault();
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
      render();
    } else if (event.key === "Enter" && choices[active]) {
      event.preventDefault();
      apply(choices[active].id);
    }
  });
  dialog.querySelectorAll("[data-canvas-mode]").forEach(button => button.addEventListener("click", () => setMode(button.dataset.canvasMode)));
  dialog.querySelector("[data-canvas-command-apply]").addEventListener("click", () => apply(guided.value));
  setMode(mode);
  window.addEventListener("resize", position);

  return {
    open(opener) { render(); window.rootGdrDialog.open(dialog, opener); position(); (mode === "compact" ? input : guided).focus(); },
    get mode() { return mode; },
    get draft() { return {mode, text:input.value, action:guided.value}; },
  };
}
