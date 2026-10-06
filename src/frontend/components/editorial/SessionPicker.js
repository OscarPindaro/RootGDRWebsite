/* The session picker's local behaviour (REQ-0010/T03).
 *
 * The filter hides what does not match and is not selected, so a chosen
 * session never disappears from view. Every checkbox writes the hidden multiple
 * select that the autosave owns and announces the change, so the story's
 * session list is one field, saved with the rest of the metadata.
 */
(function () {
  if (window.__circeusSessionPicker) return;
  window.__circeusSessionPicker = true;

  function options(root) {
    return Array.prototype.slice.call(
      root.querySelectorAll('[data-session-option]')
    );
  }

  function syncValue(root) {
    var value = root.querySelector('[data-session-value]');
    if (!value) return;
    var chosen = {};
    root.querySelectorAll('[data-session-choice]:checked').forEach(function (box) {
      chosen[box.value] = true;
    });
    Array.prototype.forEach.call(value.options, function (option) {
      option.selected = Boolean(chosen[option.value]);
    });
    value.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function applyFilter(root) {
    var filter = root.querySelector('[data-session-filter]');
    var needle = (filter ? filter.value : '').trim().toLowerCase();
    var visible = 0;
    options(root).forEach(function (item) {
      var box = item.querySelector('[data-session-choice]');
      var text = item.textContent.trim().toLowerCase();
      var matches = !needle || text.indexOf(needle) !== -1;
      var keep = matches || (box && box.checked);
      item.hidden = !keep;
      if (keep) visible += 1;
    });
    var empty = root.querySelector('[data-session-empty]');
    if (empty) empty.hidden = visible !== 0;
  }

  document.addEventListener('input', function (event) {
    var filter = event.target.closest('[data-session-filter]');
    if (filter) applyFilter(filter.closest('[data-session-picker]'));
  });

  document.addEventListener('change', function (event) {
    var choice = event.target.closest('[data-session-choice]');
    if (choice) {
      var root = choice.closest('[data-session-picker]');
      syncValue(root);
      applyFilter(root);
      return;
    }
    /* An applied value (a restored draft) repaints the boxes. */
    var value = event.target.closest('[data-session-value]');
    if (!value) return;
    var picker = value.closest('[data-session-picker]');
    var selected = {};
    Array.prototype.forEach.call(value.options, function (option) {
      if (option.selected) selected[option.value] = true;
    });
    picker.querySelectorAll('[data-session-choice]').forEach(function (box) {
      box.checked = Boolean(selected[box.value]);
    });
    applyFilter(picker);
  });
})();
