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

const VARIANT_WORDS = {
  triangle_right_right: ["rect", "rectangle", "rettangolo", "right", "destra"],
  triangle_right_left: ["left", "sinistra"],
  triangle_isosceles: ["isoscele", "isosceles"],
  triangle_equilateral: ["equilatero", "equilateral"],
};

/** The accepted shape a second Enter would create, or null. */
function shapeOf(kind) {
  return SHAPES.find(shape => shape.kind === kind) || null;
}

/**
 * The compact grammar, in two stages.
 *
 * Before a shape is accepted the text names one (`trian` → `triangolo`). After
 * it, the text refines it: a size for the bounding box, a vertex count for a
 * regular polygon, and for a triangle a variant word. Order does not matter, so
 * `130 isoscele` and `isoscele 130` agree.
 */
export function parseCompact(text, acceptedKind = null) {
  const term = String(text).trim().toLocaleLowerCase().replace(/\s+/g, " ");
  if (!acceptedKind) return term ? shapeOf(SHAPES.find(shape => shape.aliases.includes(term))?.kind) : null;
  const shape = shapeOf(acceptedKind);
  if (!shape) return null;
  if (!term) return {kind: acceptedKind, size: null, sides: null};
  let size = null, sides = null, kind = acceptedKind;
  for (const word of term.split(" ")) {
    const number = Number(word);
    if (word !== "" && Number.isFinite(number)) {
      if (acceptedKind === "regular_polygon") {
        if (!Number.isInteger(number) || number < 3 || number > 32) return null;
        sides = number;
      } else {
        if (number <= 0 || number > 100000) return null;
        size = number;
      }
      continue;
    }
    const variant = Object.keys(VARIANT_WORDS).find(candidate => VARIANT_WORDS[candidate].includes(word));
    if (variant && acceptedKind.startsWith("triangle_")) { kind = variant; continue; }
    if (shape.aliases.includes(word)) continue;
    return null;
  }
  return {kind, size, sides};
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
  const panel = root.querySelector("#drawing-command-dialog");
  const input = panel.querySelector("[data-canvas-command-input]");
  const list = panel.querySelector("[data-canvas-command-options]");
  const guided = panel.querySelector("[data-canvas-command-action]");
  const parameterInput = panel.querySelector("[data-canvas-command-parameters]");
  const output = panel.querySelector("[data-canvas-command-status]");
  const preview = panel.querySelector("[data-canvas-preview]");
  let mode = "compact", active = 0, choices = [], acceptedKind = null, dirty = false, opener = null;

  function commands() {
    return editor.actions().filter(action => !action.id.startsWith("tool-") && !action.id.startsWith("preset-"));
  }

  function guidedParameters() {
    const fields = panel.querySelector(`[data-guided-fields='${guided.value}']`);
    if (!fields) return parseNumericCommand(guided.value + " " + parameterInput.value)?.parameters;
    const values = Object.fromEntries([...fields.querySelectorAll("[data-guided-field]")].map(field => [field.dataset.guidedField, field.type === "number" ? field.valueAsNumber : field.value]));
    if (guided.value === "parent") values.parent ||= null;
    if (guided.value === "ellipse-parameter") values.field = "rx";
    return values;
  }

  function updateGuided() {
    if (mode !== "guided" || panel.hidden) { preview.toggleAttribute("hidden", true); return; }
    const action = commands().find(action => action.id === guided.value);
    panel.querySelectorAll("[data-guided-fields]").forEach(fields => {
      const selected = fields.dataset.guidedFields === guided.value;
      fields.hidden = !selected;
      if (!selected) return;
      const kind = fields.querySelector("[data-guided-field='kind']");
      if (kind && !kind.options.length) kind.replaceChildren(...SHAPES.map(shape => new Option(shape.label, shape.kind)));
      const parent = fields.querySelector("[data-guided-field='parent']");
      if (parent) { const previous = parent.value; parent.replaceChildren(...editor.parents().map(option => new Option(option.label, option.value))); if ([...parent.options].some(option => option.value === previous)) parent.value = previous; }
      if (!fields.dataset.initialized) {
        const defaults = fields.dataset.guidedFields === "create-preset" ? {...editor.defaults(), kind:"triangle_isosceles"} : fields.dataset.guidedFields === "move" ? {dx:0,dy:0} : fields.dataset.guidedFields === "ellipse-parameter" ? {value:editor.ellipse()?.rx || 50} : {};
        fields.querySelectorAll("[data-guided-field]").forEach(field => { if (defaults[field.dataset.guidedField] !== undefined) field.value = defaults[field.dataset.guidedField]; });
        fields.dataset.initialized = "true";
      }
    });
    const custom = Boolean(panel.querySelector(`[data-guided-fields='${guided.value}']`));
    parameterInput.closest("label").hidden = custom || !action?.parameters;
    const supported = ["create-preset", "geometry", "move", "parent", "align", "ellipse-parameter"].includes(guided.value);
    const parameters = guidedParameters(), predicted = supported && action?.enabled && (!action.parameters || parameters !== undefined) ? editor.preview(guided.value, parameters) : null;
    preview.toggleAttribute("hidden", !predicted);
    panel.querySelector("[data-canvas-command-apply]").disabled = !action?.enabled || (supported && !predicted);
    if (predicted) {
      preview.setAttribute("viewBox", `0 0 ${predicted.artboard.width} ${predicted.artboard.height}`);
      renderScene(preview, predicted, {selection:[], selectedId:null, viewport:[1,0,0,1,0,0], mode:"select", tool:"select", preview:true});
    }
    if (mode === "guided") output.textContent = predicted ? "Anteprima locale · nessuna modifica fino ad Applica. Le unità sono quelle della tavola." : supported ? "Parametri non validi o operazione non disponibile per la selezione." : "Scegli un’azione e applicala.";
  }

  /** What the accepted shape plus the current text would create, or null. */
  function acceptedPlan() {
    const parsed = parseCompact(input.value, acceptedKind);
    if (!parsed) return null;
    const shape = shapeOf(parsed.kind);
    const plan = {kind: parsed.kind, label: shape.label, sides: parsed.sides};
    if (parsed.size !== null) plan.size = parsed.size;
    return plan;
  }

  function describe(plan) {
    const parts = [plan.label];
    if (plan.size !== undefined) parts.push(String(Math.round(plan.size)));
    if (plan.sides) parts.push(`${plan.sides} lati`);
    return parts.join(" › ");
  }

  function render() {
    const term = input.value.trim().toLocaleLowerCase();
    const parsed = acceptedPlan();
    const candidates = acceptedKind?.startsWith("triangle_") ? SHAPES.filter(shape => shape.kind.startsWith("triangle_")) : SHAPES;
    const suggestions = acceptedKind ? candidates : candidates.filter(shape => !term || shape.label.toLocaleLowerCase().includes(term) || shape.aliases.some(alias => alias.startsWith(term)));
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
    output.textContent = mode === "guided" ? "" : acceptedKind
      ? parsed ? `${describe(parsed)} · riquadro ${Math.round(parsed.size ?? defaults.width)} unità. Invio crea; Escape annulla.` : "Variante sconosciuta: correggi il testo o premi Escape."
      : choices.length ? "Invio accetta una forma; dopo puoi indicare misura, lati o variante. Un secondo Invio crea." : "Nessun comando corrisponde al testo.";
    updateGuided();
  }

  function setMode(next) {
    if (!["compact", "guided"].includes(next)) return;
    mode = next;
    panel.querySelectorAll("[data-canvas-mode]").forEach(button => {
      const selected = button.dataset.canvasMode === mode;
      button.classList.toggle("btn-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    panel.querySelector("[data-canvas-compact]").hidden = mode !== "compact";
    panel.querySelector("[data-canvas-guided]").hidden = mode !== "guided";
    render();
  }

  function reset() {
    acceptedKind = null; input.value = ""; active = 0; dirty = false;
  }

  function close() {
    panel.hidden = true;
    reset();
    if (opener && document.contains(opener)) opener.focus();
  }

  function apply(id, parameters) {
    if (!editor.execute(id, parameters)) { output.textContent = "Comando non disponibile o parametri non validi."; return; }
    close();
  }

  function choose(action) {
    if (action.kind) { dirty = true; acceptedKind = action.kind; input.value = ""; active = 0; render(); input.focus(); }
    else if (action.parameters === true) { output.textContent = "Indica i parametri numerici del comando."; }
    else apply(action.id, action.parameters);
  }

  function create() {
    const plan = acceptedPlan();
    if (!plan) return;
    apply("create-preset", {kind: plan.kind, width: plan.size ?? undefined, sides: plan.sides ?? undefined});
  }

  input.addEventListener("input", () => { dirty = Boolean(input.value || acceptedKind); active = 0; render(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (["ArrowDown", "ArrowUp"].includes(event.key) && choices.length) {
      event.preventDefault();
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
      if (acceptedKind && choices[active].kind) {
        acceptedKind = choices[active].kind;
        input.value = "";
        active = 0;
      }
      render();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (acceptedKind) create();
      else if (choices[active]) choose(choices[active]);
    }
  });
  panel.querySelectorAll("[data-canvas-mode]").forEach(button => button.addEventListener("click", () => setMode(button.dataset.canvasMode)));
  panel.querySelector("[data-canvas-command-close]").addEventListener("click", close);
  guided.addEventListener("change", render);
  panel.querySelectorAll("[data-guided-field]").forEach(field => { field.addEventListener("input", () => {dirty = true; updateGuided();}); field.addEventListener("change", updateGuided); });
  parameterInput.addEventListener("input", updateGuided);
  panel.querySelector("[data-canvas-command-apply]").addEventListener("click", () => {
    const action = commands().find(action => action.id === guided.value);
    const parameters = guidedParameters();
    if (action?.parameters && parameters === undefined) { output.textContent = "Parametri non validi: usa numeri finiti, un gruppo o un allineamento."; return; }
    apply(guided.value, parameters);
  });
  panel.addEventListener("keydown", event => { if (event.key === "Escape") { event.preventDefault(); close(); } });
  setMode(mode);

  return {
    open(source) {
      opener = source || null;
      panel.hidden = false;
      render();
      (mode === "compact" ? input : guided).focus();
    },
    get isOpen() { return !panel.hidden; },
    get mode() { return mode; },
    restore(draft) {
      if (!draft || typeof draft.text !== "string" || draft.text.length > 255) return;
      input.value = draft.text; acceptedKind = shapeOf(draft.kind) ? draft.kind : null;
      if (commands().some(action => action.id === draft.action)) guided.value = draft.action;
      parameterInput.value = typeof draft.parameters === "string" ? draft.parameters.slice(0,255) : "";
      for (const fields of panel.querySelectorAll('[data-guided-fields]')) {
        const entry = Array.isArray(draft.fields) ? draft.fields.slice(0,10).find(item => item?.action === fields.dataset.guidedFields) : null;
        if (!entry) continue;
        fields.dataset.initialized = "true";
        fields.querySelectorAll('[data-guided-field]').forEach(field => { const value = entry.values?.[field.dataset.guidedField]; if (typeof value === 'string' && value.length <= 255) field.value = value; });
      }
      dirty = Boolean(draft.dirty); setMode(draft.mode);
    },
    get draft() { return {mode, text:input.value, action:guided.value, parameters:parameterInput.value, kind:acceptedKind, dirty, fields:[...panel.querySelectorAll('[data-guided-fields]')].map(fields => ({action:fields.dataset.guidedFields,values:Object.fromEntries([...fields.querySelectorAll('[data-guided-field]')].map(field => [field.dataset.guidedField,field.value]))}))}; },
  };
}
