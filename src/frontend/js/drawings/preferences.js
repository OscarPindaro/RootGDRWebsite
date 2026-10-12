/**
 * Editor preferences that survive a reload.
 *
 * They are browser-local and scoped to the signed-in user, like the recovery
 * draft: a preference is a convenience, not part of the drawing, so it does not
 * travel with the document and needs no server round trip. A reader that cannot
 * reach storage gets the fallback, never an exception.
 */
export function createPreferences(root) {
  const owner = root.dataset.ownerId || "anon";
  const key = name => `rootgdr:drawing:${owner}:${name}`;

  function read(name, fallback) {
    try {
      const raw = localStorage.getItem(key(name));
      if (raw === null) return fallback;
      const value = JSON.parse(raw);
      if (typeof fallback === "boolean") return value === true;
      return fallback === "dots" || fallback === "lines" ? (value === "dots" ? "dots" : "lines") : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function write(name, value) {
    try {
      localStorage.setItem(key(name), JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  return {read, write};
}
