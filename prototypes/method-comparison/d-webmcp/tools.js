/* Registers the study's actions through the real WebMCP polyfill.
 *
 * The polyfill installs the bridge on `document.modelContext`; the specification
 * also names `navigator.modelContext`, so both are checked. If neither can be
 * registered against, the page keeps a local registry so the tool contracts can
 * still be reviewed — the note in the panel says which path is active.
 */
(() => {
  const api = document.modelContext || navigator.modelContext;
  const local = new Map();
  const note = document.querySelector("[data-api-note]");
  const list = document.querySelector("[data-tool-list]");
  const status = document.querySelector("[data-status]");
  let bridged = Boolean(api && typeof api.registerTool === "function");

  const say = (text) => {
    status.textContent = text;
  };

  const tools = [
    {
      name: "planning.setCardMode",
      description:
        "Choose how NPC references are shown: an always-open quick reference, or a front/reverse card.",
      inputSchema: {
        type: "object",
        properties: { mode: { type: "string", enum: ["open", "flip"] } },
        required: ["mode"],
      },
      sample: { mode: "flip" },
      execute: ({ mode }) => {
        const button = document.querySelector(`[data-mode="${mode}"]`);
        if (!button) throw new Error(`Unknown mode: ${mode}`);
        button.click();
        return { mode, cardMode: document.querySelector("[data-npc]").dataset.mode };
      },
    },
    {
      name: "planning.toggleTrack",
      description:
        "Mark or clear one box of an NPC damage track. State is demonstration-only and resets on reload.",
      inputSchema: {
        type: "object",
        properties: {
          npc: { type: "string" },
          track: { type: "string", enum: ["fatigue", "wounds"] },
          box: { type: "integer", minimum: 0 },
          checked: { type: "boolean" },
        },
        required: ["npc", "track", "box", "checked"],
      },
      sample: { npc: "ada", track: "wounds", box: 0, checked: true },
      execute: ({ npc, track, box, checked }) => {
        const input = document.querySelector(`[data-track="${npc}:${track}:${box}"]`);
        if (!input) throw new Error(`No track box ${npc}:${track}:${box}`);
        input.checked = checked;
        input.dispatchEvent(new Event("change", { bubbles: true }));
        return { npc, track, box, checked: input.checked };
      },
    },
    {
      name: "planning.openImage",
      description:
        "Open the image-modification surface for an NPC. Opens the dialog; it does not flip the card.",
      inputSchema: {
        type: "object",
        properties: { npc: { type: "string" } },
        required: ["npc"],
      },
      sample: { npc: "ada" },
      execute: ({ npc }) => {
        const card = document.querySelector(`[data-npc="${npc}"]`);
        if (!card) throw new Error(`No NPC ${npc}`);
        card.querySelector("[data-open-image]").click();
        return { npc, open: document.getElementById("image-dialog").open };
      },
    },
    {
      name: "planning.readView",
      description: "Read the current presentation mode and marked track boxes.",
      inputSchema: { type: "object", properties: {} },
      sample: {},
      execute: () => ({
        mode: document.querySelector("[data-npc]").dataset.mode,
        marked: [...document.querySelectorAll("[data-track]")]
          .filter((input) => input.checked)
          .map((input) => input.dataset.track),
      }),
    },
  ];

  for (const tool of tools) {
    local.set(tool.name, tool);
    if (!bridged) continue;
    try {
      api.registerTool(tool);
    } catch (error) {
      bridged = false;
      note.dataset.error = String(error);
    }
  }

  note.textContent = bridged
    ? "API reale attiva: gli strumenti sono registrati sul document.modelContext installato dal polyfill."
    : "API non disponibile in questo contesto: registro locale usato per rivedere i contratti degli strumenti.";
  note.dataset.bridged = String(bridged);

  for (const tool of tools) {
    const item = document.createElement("li");
    item.dataset.tool = tool.name;
    const schema = JSON.stringify(tool.inputSchema);
    item.innerHTML = `<strong></strong><p class="hint"></p><p><code></code></p>`;
    item.querySelector("strong").textContent = tool.name;
    item.querySelector(".hint").textContent = tool.description;
    item.querySelector("code").textContent = schema;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn";
    button.textContent = "Esegui";
    button.addEventListener("click", async () => {
      const result = await call(tool.name, tool.sample);
      say(`${tool.name} → ${JSON.stringify(result)}`);
    });
    item.append(button);
    list.append(item);
  }

  async function call(name, args) {
    const tool = local.get(name);
    if (!tool) throw new Error(`Unknown tool: ${name}`);
    return tool.execute(args);
  }

  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-mode]").forEach((other) => {
        other.setAttribute("aria-pressed", String(other === button));
      });
      document.querySelector("[data-npc]").dataset.mode = button.dataset.mode;
      document.querySelectorAll("[data-tracks]").forEach((tracks) => {
        tracks.hidden = button.dataset.mode === "flip";
      });
    });
  });

  const dialog = document.getElementById("image-dialog");
  document.querySelector("[data-open-image]").addEventListener("click", () => dialog.showModal());
  document.querySelector("[data-close-dialog]").addEventListener("click", () => dialog.close());

  window.__planningTools = { names: [...local.keys()], call, bridged };
})();
