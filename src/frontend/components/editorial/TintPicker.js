/* The tint picker's local behaviour (REQ-0008/T01).
 *
 * Choosing a tint updates the trigger's swatch and name and closes the
 * popover; persisting the choice belongs to the autosave integration, not to
 * the control. Escape, light dismiss and the focus return come from the native
 * popover (the panel borrows the menu's positioning only).
 */
(function () {
  if (window.__circeusTintPicker) return;
  window.__circeusTintPicker = true;

  function close(panel) {
    if (panel && panel.matches(':popover-open')) panel.hidePopover();
  }

  function paint(root, value, label) {
    var swatch = root.querySelector('.tint-picker__swatch');
    var name = root.querySelector('[data-tint-name]');
    if (swatch) swatch.style.setProperty('--c', 'var(--' + value + ')');
    if (name) name.textContent = label || value;
  }

  function labelFor(root, value) {
    var radio = root.querySelector(
      'input[type="radio"][value="' + value + '"]'
    );
    return radio ? radio.getAttribute('aria-label') : null;
  }

  document.addEventListener('change', function (event) {
    var radio = event.target.closest('[data-tint-picker] input[type="radio"]');
    if (radio) {
      var root = radio.closest('[data-tint-picker]');
      var hidden = root.querySelector('[data-tint-value]');
      if (hidden) {
        /* The hidden input is the one registered autosave field. */
        hidden.value = radio.value;
        hidden.dispatchEvent(new Event('change', { bubbles: true }));
      }
      paint(root, radio.value, radio.getAttribute('aria-label'));
      close(root.querySelector('.tint-picker__panel'));
      return;
    }
    /* A restored, applied or server-refreshed value repaints the control. */
    var field = event.target.closest('[data-tint-value]');
    if (!field) return;
    var picker = field.closest('[data-tint-picker]');
    var checked = picker.querySelector(
      'input[type="radio"][value="' + field.value + '"]'
    );
    if (checked) checked.checked = true;
    paint(picker, field.value, labelFor(picker, field.value));
  });
})();
