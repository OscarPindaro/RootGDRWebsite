import { render as renderScene } from "./render.js";

const SHAPES = [
  {kind:"triangle_isosceles", label:"Triangolo · isoscele", aliases:["triangle", "triangolo", "isosceles", "isoscele"]},
  {kind:"triangle_equilateral", label:"Triangolo · equilatero", aliases:["equilateral", "equilatero"]},
  {kind:"triangle_right_right", label:"Triangolo rettangolo · angolo a destra", aliases:["right", "destra", "rect right", "rettangolo destra", "right triangle"]},
  {kind:"triangle_right_left", label:"Triangolo rettangolo · angolo a sinistra", aliases:["left", "sinistra", "rect left", "rettangolo sinistra"]},
  {kind:"rectangle", label:"Rettangolo", aliases:["rectangle", "rettangolo", "rect"]},
  {kind:"square", label:"Quadrato", aliases:["square", "quadrato"]},
  {kind:"circle", label:"Cerchio", aliases:["circle", "cerchio"]},
  {kind:"ellipse", label:"Ellisse", aliases:["ellipse", "ellisse"]},
  {kind:"regular_polygon", label:"Poligono regolare", aliases:["polygon", "poligono", "poligono regolare"]},
];

export function parseCompact(text, currentKind = null) {
  const term = String(text).trim().toLocaleLowerCase().replace(/\s+/g, " ");
  if (!term) return SHAPES.find(shape => shape.kind === currentKind) || null;
  if (currentKind?.startsWith("triangle_")) {
    const words = term.split(" ");
    const right = ["rect", "rectangle", "rettangolo", "right", "destra", "left", "sinistra", "triangle", "triangolo"];
    if (words.every(word => right.includes(word)) && words.some(word => ["rect", "rectangle", "rettangolo", "right", "destra", "left", "sinistra"].includes(word))) {
      return SHAPES.find(shape => shape.kind === (words.some(word => ["left", "sinistra"].includes(word)) ? "triangle_right_left" : "triangle_right_right"));
    }
  }
  return SHAPES.find(shape => shape.aliases.includes(term)) || null;
}

export function parseNumericCommand(text) {
  const [token, ...values] = String(text).trim().split(/\s+/), raw = token.toLocaleLowerCase();
  const command = {sposta:"move", dimensioni:"size", posizione:"position", angolo:"angle", perno:"pivot", raggio:"radius", allinea:"align", genitore:"parent", "ellipse-parameter":"radius"}[raw] || raw;
  if (command === "parent" && values.length === 1) return /^(?:[a-zA-Z0-9_-]{1,64})$/.test(values[0]) ? {id:"parent", label:"Genitore", parameters:{parent:["root", "scena"].includes(values[0].toLocaleLowerCase()) ? null : values[0]}} : null;
  if (command === "align" && values.length === 1) {
    const value = values[0].toLocaleLowerCase(), alignment = {sinistra:"left", destra:"right", alto:"top", basso:"bottom"}[value] || value;
    return ["left", "right", "top", "bottom", "center-x", "center-y", "distribute-x", "distribute-y"].includes(alignment) ? {id:"align", label:"Allinea", parameters:{alignment}} : null;
  }
  const numbers = values.map(Number);
  if (!numbers.every(Number.isFinite)) return null;
  if (command === "move" && numbers.length === 2) return {id:"move", label:"Sposta", parameters:{dx:numbers[0], dy:numbers[1]}};
  if (["size", "position", "pivot"].includes(command) && numbers.length === 2) {
    const fields = command === "size" ? ["width", "height"] : command === "position" ? ["x", "y"] : ["pivotX", "pivotY"];
    return {id:"geometry", label:"Geometria numerica", parameters:{[fields[0]]:numbers[0], [fields[1]]:numbers[1]}};
  }
  if (command === "angle" && numbers.length === 1) return {id:"geometry", label:"Angolo", parameters:{angle:numbers[0]}};
  if (command === "radius" && numbers.length === 1) return {id:"ellipse-parameter", label:"Raggio", parameters:{field:"rx", value:numbers[0]}};
  if (command === "geometry" && [4,5].includes(numbers.length)) return {id:"geometry", label:"Geometria numerica", parameters:{x:numbers[0],y:numbers[1],width:numbers[2],height:numbers[3], ...(numbers.length === 5 ? {angle:numbers[4]} : {})}};
  return null;
}

export function createCanvasPalette(root, editor) {
  const dialog = root.querySelector("#drawing-command-dialog");
  const input = dialog.querySelector("[data-canvas-command-input]");
  const list = dialog.querySelector("[data-canvas-command-options]");
  const guided = dialog.querySelector("[data-canvas-command-action]");
  const parameterInput = dialog.querySelector("[data-canvas-command-parameters]");
  const output = dialog.querySelector("[data-canvas-command-status]");
  const preview = dialog.querySelector("[data-canvas-preview]");
  let mode = "compact", active = 0, choices = [], acceptedKind = null;

  function commands() {
    return editor.actions().filter(action => !action.id.startsWith("tool-") && !action.id.startsWith("preset-"));
  }

  function position() {
    if (!dialog.open) return;
    const canvas = root.querySelector("[data-drawing-artboard]").getBoundingClientRect();
    dialog.style.left = Math.max(8, Math.min(canvas.x + canvas.width / 2 - dialog.offsetWidth / 2, window.innerWidth - dialog.offsetWidth - 8)) + "px";
    dialog.style.top = Math.max(8, Math.min(canvas.y + 16, window.innerHeight - dialog.offsetHeight - 8)) + "px";
  }

  function guidedParameters() {
    const panel = dialog.querySelector(`[data-guided-fields='${guided.value}']`);
    if (!panel) return parseNumericCommand(guided.value + " " + parameterInput.value)?.parameters;
    const values = Object.fromEntries([...panel.querySelectorAll("[data-guided-field]")].map(field => [field.dataset.guidedField, field.type === "number" ? field.valueAsNumber : field.value]));
    if (guided.value === "parent") values.parent ||= null;
    if (guided.value === "ellipse-parameter") values.field = "rx";
    return values;
  }

  function updateGuided() {
    if (mode !== "guided" || !dialog.open) { preview.toggleAttribute("hidden",true); return; }
    const action = commands().find(action => action.id === guided.value);
    dialog.querySelectorAll("[data-guided-fields]").forEach(panel => {
      const selected = panel.dataset.guidedFields === guided.value;
      panel.hidden = !selected;
      if (!selected) return;
      const kind = panel.querySelector("[data-guided-field='kind']");
      if (kind && !kind.options.length) kind.replaceChildren(...SHAPES.map(shape => new Option(shape.label,shape.kind)));
      const parent = panel.querySelector("[data-guided-field='parent']");
      if (parent) { const previous = parent.value; parent.replaceChildren(...editor.parents().map(option => new Option(option.label,option.value))); if ([...parent.options].some(option => option.value === previous)) parent.value = previous; }
      if (!panel.dataset.initialized) {
        const defaults = panel.dataset.guidedFields === "create-preset" ? {...editor.defaults(), kind:"triangle_isosceles"} : panel.dataset.guidedFields === "move" ? {dx:0,dy:0} : panel.dataset.guidedFields === "ellipse-parameter" ? {value:editor.ellipse()?.rx || 50} : {};
        panel.querySelectorAll("[data-guided-field]").forEach(field => { if (defaults[field.dataset.guidedField] !== undefined) field.value = defaults[field.dataset.guidedField]; });
        panel.dataset.initialized = "true";
      }
    });
    const custom = Boolean(dialog.querySelector(`[data-guided-fields='${guided.value}']`));
    parameterInput.closest("label").hidden = custom || !action?.parameters;
    const supported = ["create-preset", "geometry", "move", "parent", "align", "ellipse-parameter"].includes(guided.value);
    const parameters = guidedParameters(), predicted = supported && action?.enabled && (!action.parameters || parameters !== undefined) ? editor.preview(guided.value, parameters) : null;
    preview.toggleAttribute("hidden",!predicted);
    dialog.querySelector("[data-canvas-command-apply]").disabled = !action?.enabled || (supported && !predicted);
    if (predicted) {
      preview.setAttribute("viewBox", `0 0 ${predicted.artboard.width} ${predicted.artboard.height}`);
      renderScene(preview, predicted, {selection:[], selectedId:null, viewport:[1,0,0,1,0,0], mode:"select", tool:"select", preview:true});
    }
    if (mode === "guided") output.textContent = predicted ? "Anteprima locale · nessuna modifica fino ad Applica. Le unità sono quelle della tavola." : supported ? "Parametri non validi o operazione non disponibile per la selezione." : "Scegli un’azione e applicala.";
    position();
  }

  function render() {
    const term = input.value.trim().toLocaleLowerCase();
    const shapes = acceptedKind?.startsWith("triangle_") ? SHAPES.filter(shape => shape.kind.startsWith("triangle_")) : SHAPES;
    const parsed = parseCompact(input.value, acceptedKind);
    const suggestions = shapes.filter(shape => !term || shape.label.toLocaleLowerCase().includes(term) || shape.aliases.some(alias => alias.startsWith(term)) || parsed?.kind === shape.kind);
    choices = suggestions.map(shape => ({...shape, id:"create-preset", enabled:true}));
    if (!acceptedKind) {
      choices.push(...commands().filter(action => action.label.toLocaleLowerCase().includes(term) || action.id.includes(term)));
      const numeric = parseNumericCommand(input.value);
      if (numeric) {
        const action = commands().find(action => action.id === numeric.id);
        if (action) choices.unshift({...numeric, enabled:action.enabled, label:numeric.label + " · " + JSON.stringify(numeric.parameters)});
      }
    }
    active = Math.max(0, Math.min(active, choices.length - 1));
    list.replaceChildren(...choices.map((action, index) => {
      const option = document.createElement("li");
      option.className = "drawing-editor__command-option";
      option.id = `canvas-command-option-${index}`;
      option.textContent = action.label;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(index === active));
      option.setAttribute("aria-disabled", String(!action.enabled));
      option.addEventListener("click", () => choose(action));
      return option;
    }));
    input.setAttribute("aria-expanded", String(choices.length > 0));
    if (choices.length) input.setAttribute("aria-activedescendant", `canvas-command-option-${active}`);
    else input.removeAttribute("aria-activedescendant");
    const previous = guided.value;
    guided.replaceChildren(...commands().map(action => {
      const option = new Option(action.label, action.id);
      option.disabled = !action.enabled;
      return option;
    }));
    if ([...guided.options].some(option => option.value === previous)) guided.value = previous;
    parameterInput.closest("label").hidden = !commands().find(action => action.id === guided.value)?.parameters;
    const defaults = editor.defaults();
    output.textContent = mode === "guided" ? "Scegli un’azione e applicala. Unità vettoriali della tavola." : acceptedKind
      ? parsed ? `${parsed.label} · riquadro ${Math.round(defaults.width)} × ${Math.round(defaults.height)} unità, centro (${Math.round(defaults.x)}, ${Math.round(defaults.y)}). Invio crea; Escape annulla.` : "Variante sconosciuta: correggi il testo o premi Escape."
      : choices.length ? "Invio accetta una forma; un secondo Invio la crea. Dimensioni vettoriali adattate alla vista." : "Nessun comando corrisponde al testo.";
    updateGuided();
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
    render();
  }

  function apply(id, parameters) {
    if (!editor.execute(id, parameters)) { output.textContent = "Comando non disponibile o parametri non validi."; return; }
    acceptedKind = null; input.value = ""; active = 0;
    window.rootGdrDialog.close(dialog);
  }

  function choose(action) {
    if (action.kind) { acceptedKind = action.kind; input.value = ""; active = 0; render(); input.focus(); }
    else if (action.parameters === true) { output.textContent = "Indica i parametri numerici del comando."; }
    else apply(action.id, action.parameters);
  }

  input.addEventListener("input", () => { active = 0; render(); });
  input.addEventListener("keydown", event => {
    if (["ArrowDown", "ArrowUp"].includes(event.key) && choices.length) {
      event.preventDefault();
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
      if (acceptedKind && choices[active].kind) {
        acceptedKind = choices[active].kind;
        input.value = "";
        active = (acceptedKind.startsWith("triangle_") ? SHAPES.filter(shape => shape.kind.startsWith("triangle_")) : SHAPES).findIndex(shape => shape.kind === acceptedKind);
      }
      render();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (acceptedKind) {
        const parsed = parseCompact(input.value, acceptedKind);
        if (parsed) apply("create-preset", {kind:parsed.kind});
      } else if (choices[active]) choose(choices[active]);
    }
  });
  dialog.querySelectorAll("[data-canvas-mode]").forEach(button => button.addEventListener("click", () => setMode(button.dataset.canvasMode)));
  guided.addEventListener("change", render);
  dialog.querySelectorAll("[data-guided-field]").forEach(field => { field.addEventListener("input", updateGuided); field.addEventListener("change", updateGuided); });
  parameterInput.addEventListener("input", updateGuided);
  dialog.querySelector("[data-canvas-command-apply]").addEventListener("click", () => {
    const action = commands().find(action => action.id === guided.value);
    const parameters = guidedParameters();
    if (action?.parameters && parameters === undefined) { output.textContent = "Parametri non validi: usa numeri finiti, un gruppo o un allineamento."; return; }
    apply(guided.value, parameters);
  });
  dialog.addEventListener("close", () => { acceptedKind = null; input.value = ""; active = 0; });
  setMode(mode);
  window.addEventListener("resize", position);

  return {
    open(opener) { render(); window.rootGdrDialog.open(dialog, opener); updateGuided(); position(); (mode === "compact" ? input : guided).focus(); },
    get mode() { return mode; },
    get draft() { return {mode, text:input.value, action:guided.value, parameters:parameterInput.value, kind:acceptedKind}; },
  };
}
