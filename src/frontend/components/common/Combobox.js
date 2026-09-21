(function () {
  if (window.__circeusCombobox) return;
  window.__circeusCombobox = true;

  function input(root) { return root.querySelector('.combobox__input'); }
  function list(root) { return root.querySelector('.combobox__list'); }
  function options(root) { return Array.from(root.querySelectorAll('.combobox__option')); }
  function shown(root) { return options(root).filter(function (o) { return !o.hidden; }); }

  function open(root) {
    list(root).hidden = false;
    input(root).setAttribute('aria-expanded', 'true');
  }

  function close(root) {
    list(root).hidden = true;
    input(root).setAttribute('aria-expanded', 'false');
    mark(root, null);
  }

  function filter(root) {
    var query = input(root).value.trim().toLowerCase();
    options(root).forEach(function (option) {
      option.hidden = query !== '' && !option.textContent.toLowerCase().includes(query);
    });
    open(root);
  }

  function mark(root, option) {
    options(root).forEach(function (o) {
      var active = o === option;
      o.setAttribute('aria-selected', String(active));
      o.classList.toggle('combobox__option--active', active);
    });
  }

  function choose(root, option) {
    input(root).value = option.textContent.trim();
    close(root);
    input(root).dispatchEvent(new Event('change', { bubbles: true }));
  }

  function move(root, step) {
    var visible = shown(root);
    if (!visible.length) return;
    var current = visible.indexOf(root.querySelector('.combobox__option--active'));
    var next = current < 0
      ? (step > 0 ? 0 : visible.length - 1)
      : (current + step + visible.length) % visible.length;
    mark(root, visible[next]);
    visible[next].scrollIntoView({ block: 'nearest' });
  }

  document.addEventListener('input', function (event) {
    var root = event.target.closest('[data-combobox]');
    if (root && event.target.matches('.combobox__input')) filter(root);
  });

  document.addEventListener('focusin', function (event) {
    var root = event.target.closest('[data-combobox]');
    if (root && event.target.matches('.combobox__input')) filter(root);
  });

  document.addEventListener('pointerdown', function (event) {
    var option = event.target.closest('.combobox__option');
    if (!option) return;
    var root = option.closest('[data-combobox]');
    if (!root) return;
    event.preventDefault();
    choose(root, option);
  });

  document.addEventListener('keydown', function (event) {
    var root = event.target.closest('[data-combobox]');
    if (!root || !event.target.matches('.combobox__input')) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (list(root).hidden) filter(root);
      move(root, 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      move(root, -1);
    } else if (event.key === 'Enter') {
      var active = root.querySelector('.combobox__option--active');
      if (active && !list(root).hidden) {
        event.preventDefault();
        choose(root, active);
      }
    } else if (event.key === 'Escape') {
      close(root);
    }
  });

  document.addEventListener('focusout', function (event) {
    var root = event.target.closest('[data-combobox]');
    if (root && !root.contains(event.relatedTarget)) close(root);
  });
})();
