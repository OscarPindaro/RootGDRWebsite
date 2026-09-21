(function () {
  if (window.__circeusButtonGroup) return;
  window.__circeusButtonGroup = true;

  function groupFor(target) {
    return target.closest('[data-button-group]');
  }

  function sync(group) {
    group.querySelectorAll('.button-group-input').forEach(function (input) {
      input.setAttribute('aria-checked', input.checked ? 'true' : 'false');
    });
  }

  // Pressing never changes geometry; the only thing pointerdown records is
  // whether the option was already checked, so a second click can clear an
  // optional single selection.
  document.addEventListener('pointerdown', function (event) {
    var input = event.target.closest('.button-group-option')?.querySelector('.button-group-input');
    if (input) input.dataset.wasChecked = input.checked ? 'true' : 'false';
  });

  document.addEventListener('click', function (event) {
    var input = event.target.closest('.button-group-option')?.querySelector('.button-group-input');
    if (!input || input.type !== 'radio') return;
    var group = groupFor(input);
    if (!group || group.hasAttribute('data-button-group-required')) return;
    if (input.dataset.wasChecked === 'true') {
      event.preventDefault();
      input.checked = false;
      input.dispatchEvent(new Event('change', {bubbles: true}));
    }
    delete input.dataset.wasChecked;
  });

  document.addEventListener('change', function (event) {
    if (!event.target.matches('.button-group-input')) return;
    sync(groupFor(event.target));
  });

  document.addEventListener('keydown', function (event) {
    var group = groupFor(event.target);
    if (!group) return;

    var input = event.target.closest('.button-group-input');
    if (!input) return;
    var enabled = Array.from(group.querySelectorAll('.button-group-input:not(:disabled)'));
    var index = enabled.indexOf(input);
    var next = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % enabled.length;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + enabled.length) % enabled.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = enabled.length - 1;
    if (next !== null && enabled.length) {
      enabled[next].focus();
      if (input.type === 'radio') {
        enabled[next].checked = true;
        enabled[next].dispatchEvent(new Event('change', {bubbles: true}));
      }
      event.preventDefault();
      return;
    }
    if (event.key === ' ' && input.type === 'radio' && input.checked &&
        !group.hasAttribute('data-button-group-required')) {
      event.preventDefault();
      input.checked = false;
      input.dispatchEvent(new Event('change', {bubbles: true}));
    }
  });

  document.querySelectorAll('[data-button-group]').forEach(sync);
  document.body.addEventListener('htmx:afterSwap', function (event) {
    event.target.querySelectorAll('[data-button-group]').forEach(sync);
  });
})();
