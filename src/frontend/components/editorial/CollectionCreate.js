/* The collection create entry's phone placement.
 *
 * Below 700px the entry leaves the grid and becomes the collection's action
 * row above it; at 701px and above it is the grid's last cell, as on desktop.
 * The node is moved, never cloned, so there is one button, one POST and one
 * accessible name. The moved entry carries `data-collection-action`, which the
 * stylesheet turns into the compact row. Focus survives a move that happens
 * while the entry has it. Without this script the entry keeps the markup's
 * grid position.
 */
(function () {
  if (window.__rootGdrCollectionCreate) return;
  window.__rootGdrCollectionCreate = true;

  var PHONE = window.matchMedia("(max-width: 700px)");

  function gridFor(create) {
    var parent = create.parentElement;
    if (parent && parent.classList.contains("grid")) return parent;
    var next = create.nextElementSibling;
    return next && next.classList.contains("grid") ? next : null;
  }

  function place(create) {
    var grid = gridFor(create);
    if (!grid) return;
    var focused = document.activeElement === create;
    var above = PHONE.matches;
    var moved = false;
    if (above && create.parentElement === grid) {
      grid.parentNode.insertBefore(create, grid);
      moved = true;
    } else if (!above && create.parentElement !== grid) {
      grid.appendChild(create);
      moved = true;
    }
    create.toggleAttribute("data-collection-action", above);
    if (moved && focused) create.focus();
  }

  function placeAll(root) {
    (root || document).querySelectorAll(".collection-create").forEach(place);
  }

  placeAll();
  PHONE.addEventListener("change", function () {
    placeAll();
  });
  document.body.addEventListener("htmx:afterSwap", function (event) {
    placeAll(event.target);
  });
})();
