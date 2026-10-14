/**
 * The library panel inside the drawing editor.
 *
 * It saves the current selection as a reusable asset and inserts one back. The
 * server decides what the signed-in user may see — an administrator sees every
 * library, a world master sees their own world's — so the panel renders whatever
 * the API returns and offers nothing when that is nothing.
 */
export function createLibraryPanel(root, editor) {
  const panel = root.querySelector("[data-library]");
  const endpoint = panel?.dataset.libraryUrl;
  // The server decides whether this viewer may read any library at all. Without
  // that decision the panel does not even ask, so a page that offers no library
  // makes no request and reports no error.
  if (!panel || !endpoint) return {refresh() {}, load() {}};
  const librarySelect = panel.querySelector("[data-library-library]");
  const sectionSelect = panel.querySelector("[data-library-section]");
  const assetSelect = panel.querySelector("[data-library-asset]");
  const nameInput = panel.querySelector("[data-library-name]");
  const status = panel.querySelector("[data-library-status]");
  const insertButton = panel.querySelector("[data-library-insert]");
  const saveButton = panel.querySelector("[data-library-save]");
  let libraries = [], assets = [];

  function say(message) {
    status.textContent = message;
  }

  async function json(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {Accept: "application/json", ...(options.body ? {"Content-Type": "application/json"} : {})},
      ...options,
    });
    if (!response.ok) throw new Error(String(response.status));
    return response.status === 204 ? null : response.json();
  }

  function syncSections() {
    const library = libraries.find(entry => entry.id === librarySelect.value);
    const sections = library ? library.sections : [];
    sectionSelect.replaceChildren(...sections.map(section => new Option(section.name, section.id)));
    return sections.length > 0;
  }

  function syncAssets() {
    assetSelect.replaceChildren(...assets.map(asset => new Option(asset.name, asset.id)));
    // Inserting needs no selection; saving one does, and only when it is
    // actually editable.
    insertButton.disabled = !assets.length;
    saveButton.disabled = !sectionSelect.value || !editor.selection.length || !editor.canExecute("duplicate");
    panel.querySelector("[data-library-empty]").hidden = assets.length > 0;
  }

  async function loadAssets() {
    assets = [];
    if (!librarySelect.value) { syncAssets(); return; }
    // One bounded listing per library, filtered by section here: a section
    // change is a view change, not another round trip.
    try {
      const payload = await json(`/api/libraries/${librarySelect.value}/assets?page_size=100`);
      const all = Array.isArray(payload.data) ? payload.data : [];
      assets = sectionSelect.value ? all.filter(asset => asset.sectionId === sectionSelect.value) : all;
    } catch (error) {
      assets = [];
      say("Non è stato possibile leggere gli elementi.");
    }
    syncAssets();
  }

  async function loadLibraries() {
    try {
      const payload = await json(endpoint);
      libraries = Array.isArray(payload) ? payload : [];
    } catch (error) {
      libraries = [];
      say("Libreria non disponibile per questo account.");
    }
    librarySelect.replaceChildren(...libraries.map(library => new Option(library.name, library.id)));
    if (!libraries.length) say("Nessuna libreria disponibile per questo account.");
    if (syncSections()) await loadAssets();
    else syncAssets();
  }

  async function insert() {
    if (!assetSelect.value) return;
    try {
      const asset = await json(`/api/libraries/${librarySelect.value}/assets/${assetSelect.value}`);
      if (!editor.insertFragment(asset.fragment.nodes)) { say("L’elemento non è stato inserito."); return; }
      say(`Inserito «${asset.name}».`);
    } catch (error) {
      say("Non è stato possibile inserire l’elemento.");
    }
  }

  async function saveSelection() {
    const name = nameInput.value.trim();
    if (!name || !sectionSelect.value) { say("Dai un nome all’elemento e scegli una sezione."); return; }
    const fragment = editor.selectionFragment();
    if (!fragment) { say("Seleziona almeno un oggetto da salvare."); return; }
    try {
      await json(`/api/libraries/${librarySelect.value}/assets`, {
        method: "POST",
        body: JSON.stringify({sectionId: sectionSelect.value, name, fragment}),
      });
      nameInput.value = "";
      say(`Salvato «${name}».`);
      await loadAssets();
    } catch (error) {
      say("Non è stato possibile salvare: controlla nome, sezione e permessi.");
    }
  }

  librarySelect.addEventListener("change", async () => { syncSections(); await loadAssets(); });
  sectionSelect.addEventListener("change", loadAssets);
  insertButton.addEventListener("click", insert);
  saveButton.addEventListener("click", saveSelection);
  root.addEventListener("input", syncAssets);

  return {
    refresh() { syncAssets(); },
    load: loadLibraries,
  };
}
