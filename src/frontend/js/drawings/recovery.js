export function createRecovery(root, editor) {
  const owner = root.dataset.ownerId, id = root.dataset.drawingId;
  if (!owner || !id) return {schedule() {}, flush() {}, confirmed() {}};
  const key = `rootgdr:drawing-draft:${owner}:${id}`;
  const banner = root.querySelector("[data-drawing-recovery]");
  const message = root.querySelector("[data-recovery-message]");
  const dialog = root.querySelector("#drawing-navigation");
  const navigationMessage = dialog.querySelector("[data-navigation-message]");
  let timer = null, available = null, target = null, ignoring = false;
  try {
    const raw = localStorage.getItem(key);
    if (raw && raw.length <= 2097152) {
      const record = JSON.parse(raw);
      if (record.format === 1 && record.owner === owner && record.id === id && Number.isFinite(record.time) && Number.isInteger(record.state?.version)) available = record;
    }
  } catch (error) { message.textContent = "Archivio locale non disponibile o bozza non leggibile."; banner.hidden = false; }
  if (available) {
    root.dataset.recoveryPending = "true";
    const stale = available.state.version !== editor.state().version;
    const expired = Date.now() - available.time > 7 * 86400000;
    message.textContent = stale ? "Bozza locale di una versione diversa: riprendi e salva come copia, senza sovrascrivere il server." : expired ? "Bozza locale più vecchia di sette giorni: verifica prima di salvarla." : "È disponibile lavoro locale recuperabile, non ancora salvato sul server.";
    banner.hidden = false;
  }

  function flush() {
    clearTimeout(timer);
    if (ignoring || available) return;
    const state = editor.state();
    if (!editor.unsaved()) return;
    try {
      const data = JSON.stringify({format:1, owner, id, time:Date.now(), state});
      if (data.length > 2097152) throw new Error("Draft exceeds recovery limit");
      localStorage.setItem(key,data);
    } catch (error) { message.textContent = "La bozza locale non è recuperabile: salva sul server prima di uscire."; banner.hidden = false; }
  }

  root.querySelector("[data-recovery-restore]").addEventListener("click", async () => {
    if (!available) return;
    const button = root.querySelector("[data-recovery-restore]");
    button.disabled = true;
    try {
      const response = await fetch("/api/drawings/validate", {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json"}, body:JSON.stringify(available.state.scene)});
      if (!response.ok) throw new Error("Recovery is unavailable");
      const scene = await response.json();
      editor.restore({...available.state, scene});
      available = null; delete root.dataset.recoveryPending; banner.hidden = true; editor.redraw(); flush();
    } catch (error) { message.textContent = "Bozza non ripristinata: verifica accesso, formato e connessione. Il lavoro locale è conservato."; }
    finally { button.disabled = false; }
  });
  root.querySelector("[data-recovery-discard]").addEventListener("click", () => {
    try { localStorage.removeItem(key); available = null; delete root.dataset.recoveryPending; banner.hidden = true; editor.redraw(); }
    catch (error) { message.textContent = "Non è stato possibile scartare la bozza locale."; }
  });

  function request(href, opener) {
    if (!editor.unsaved() && !editor.pending()) return false;
    flush(); target = href;
    navigationMessage.textContent = editor.pending() ? "Attendi il salvataggio in corso." : "La bozza locale non equivale a un salvataggio sul server.";
    dialog.querySelector("[data-navigation-discard]").disabled = editor.pending();
    window.rootGdrDialog.open(dialog,opener);
    return true;
  }
  function leave() { ignoring = true; editor.leave(); window.location.assign(target); }
  dialog.querySelector("[data-navigation-save]").addEventListener("click", async () => {
    const button = dialog.querySelector("[data-navigation-save]");
    button.disabled = true;
    const saved = await editor.save();
    button.disabled = false;
    if (saved) { flush(); leave(); }
    else navigationMessage.textContent = "Uscita annullata: il server non ha confermato il salvataggio. Completa eventuali bozze e riprova.";
  });
  dialog.querySelector("[data-navigation-discard]").addEventListener("click", () => {
    if (editor.pending()) return;
    try { localStorage.removeItem(key); available = null; leave(); }
    catch (error) { navigationMessage.textContent = "Impossibile scartare la bozza. Rimani qui e salva."; }
  });
  document.addEventListener("click", event => {
    const anchor = event.target.closest?.("a[href]");
    if (!anchor || event.button || event.ctrlKey || event.metaKey || anchor.target === "_blank" || anchor.hasAttribute("download") || anchor.getAttribute("href").startsWith("#")) return;
    const url = new URL(anchor.href,window.location.href);
    if (url.origin !== window.location.origin) return;
    if (request(url.href,anchor)) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, true);
  window.addEventListener("rootgdr:navigate", event => { if (request(event.detail.href,document.activeElement)) event.preventDefault(); });
  window.addEventListener("pagehide",flush);
  return {schedule() { clearTimeout(timer); timer = setTimeout(flush,300); }, flush, confirmed() {
    if (editor.unsaved()) { flush(); return; }
    try { localStorage.removeItem(key); } catch (error) { message.textContent = "Salvato sul server; cache locale non eliminata."; banner.hidden = false; }
  }};
}
