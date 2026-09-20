(function () {
  if (window.__circeusButtonGroup) return;
  window.__circeusButtonGroup = true;

  function groupFor(target) {
    return target.closest('[data-button-group]');
  }

  function itemFor(target, group) {
    var option = target.closest('.button-group-option');
    if (option && option.parentElement === group) return option;
    var button = target.closest('.btn');
    return button && button.parentElement === group ? button : null;
  }

  function items(group) {
    return Array.from(group.children).filter(function (child) {
      return child.matches('.btn, .button-group-option') &&
        !child.matches(':disabled, .button-group-option-disabled');
    });
  }

  function clearPress(group) {
    items(group).forEach(function (item) {
      if (item.dataset.buttonGroupWidth !== undefined) {
        item.style.width = item.dataset.buttonGroupWidth;
        delete item.dataset.buttonGroupWidth;
      }
      delete item.dataset.buttonGroupPressed;
    });
  }

  function press(item, group) {
    if (!item || group.classList.contains('button-group-connected')) return;
    clearPress(group);
    var siblings = items(group);
    var index = siblings.indexOf(item);
    if (index < 0) return;
    var neighbors = [siblings[index - 1], siblings[index + 1]].filter(Boolean);
    var scale = parseFloat(getComputedStyle(group).getPropertyValue('--button-group-press-scale')) || 1.15;
    var width = item.getBoundingClientRect().width;
    var expansion = width * (scale - 1);
    item.dataset.buttonGroupWidth = item.style.width;
    item.dataset.buttonGroupPressed = '';
    item.style.width = (width + expansion) + 'px';
    neighbors.forEach(function (neighbor) {
      var neighborWidth = neighbor.getBoundingClientRect().width;
      neighbor.dataset.buttonGroupWidth = neighbor.style.width;
      neighbor.style.width = Math.max(0, neighborWidth - expansion / neighbors.length) + 'px';
    });
  }

  function sync(group) {
    group.querySelectorAll('.button-group-input').forEach(function (input) {
      input.setAttribute('aria-checked', input.checked ? 'true' : 'false');
    });
  }

  document.addEventListener('pointerdown', function (event) {
    var group = groupFor(event.target);
    if (!group) return;
    var input = event.target.closest('.button-group-option')?.querySelector('.button-group-input');
    if (input) input.dataset.wasChecked = input.checked ? 'true' : 'false';
    press(itemFor(event.target, group), group);
  });

  document.addEventListener('pointerup', function (event) {
    var group = groupFor(event.target);
    if (group) clearPress(group);
  });
  document.addEventListener('pointercancel', function (event) {
    var group = groupFor(event.target);
    if (group) clearPress(group);
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
    var item = itemFor(event.target, group);
    if ((event.key === ' ' || event.key === 'Enter') && item) press(item, group);

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
      clearPress(group);
    }
  });

  document.addEventListener('keyup', function (event) {
    if (event.key !== ' ' && event.key !== 'Enter') return;
    var group = groupFor(event.target);
    if (group) clearPress(group);
  });

  document.querySelectorAll('[data-button-group]').forEach(sync);
  document.body.addEventListener('htmx:afterSwap', function (event) {
    event.target.querySelectorAll('[data-button-group]').forEach(sync);
  });
})();
