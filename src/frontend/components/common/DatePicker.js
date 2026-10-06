/* The desktop calendar over the native date field (REQ-0007/T02).
 *
 * The native input stays the canonical value: typed entry always works, an
 * invalid entry simply leaves it empty, and the grid only writes a date the
 * server can store. Dates are handled as local calendar dates (never UTC), so a
 * leap day and a month or year boundary are what they look like.
 */
(function () {
  if (window.__circeusDatePicker) return;
  window.__circeusDatePicker = true;

  var MONTHS = new Intl.DateTimeFormat('it-IT', { month: 'long', year: 'numeric' });
  var TODAY = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' });

  function iso(date) {
    var pad = function (value) { return String(value).padStart(2, '0'); };
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
  }

  function parse(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
    if (!match) return null;
    var date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return date.getMonth() === Number(match[2]) - 1 ? date : null;
  }

  function state(root) {
    if (!root.__dateState) {
      var input = root.querySelector('[data-date-input]');
      var current = parse(input.value) || new Date();
      root.__dateState = {
        month: new Date(current.getFullYear(), current.getMonth(), 1),
        focus: iso(parse(input.value) || new Date()),
      };
    }
    return root.__dateState;
  }

  function value(root) {
    return root.querySelector('[data-date-input]').value;
  }

  function render(root) {
    var data = state(root);
    var grid = root.querySelector('[data-date-grid]');
    var selected = value(root);
    var today = iso(new Date());
    grid.textContent = '';
    root.querySelector('[data-date-month]').textContent = MONTHS.format(data.month);
    var first = new Date(data.month.getFullYear(), data.month.getMonth(), 1);
    var offset = (first.getDay() + 6) % 7;
    var start = new Date(first);
    start.setDate(first.getDate() - offset);
    for (var index = 0; index < 42; index += 1) {
      var day = new Date(start);
      day.setDate(start.getDate() + index);
      var key = iso(day);
      var cell = document.createElement('button');
      cell.type = 'button';
      cell.className = 'date-picker__day';
      cell.setAttribute('role', 'gridcell');
      cell.dataset.date = key;
      cell.textContent = String(day.getDate());
      if (day.getMonth() !== data.month.getMonth()) cell.dataset.outside = 'true';
      if (key === today) cell.setAttribute('aria-current', 'date');
      cell.setAttribute('aria-selected', key === selected ? 'true' : 'false');
      cell.tabIndex = key === data.focus ? 0 : -1;
      if (key === today) cell.title = 'Oggi, ' + TODAY.format(day);
      grid.appendChild(cell);
    }
  }

  function focusDay(root, key) {
    var data = state(root);
    var cell = root.querySelector('[data-date-grid] [data-date="' + key + '"]');
    if (!cell) {
      var target = parse(key);
      if (!target) return;
      data.month = new Date(target.getFullYear(), target.getMonth(), 1);
      render(root);
      cell = root.querySelector('[data-date-grid] [data-date="' + key + '"]');
      if (!cell) return;
    }
    data.focus = key;
    root.querySelectorAll('[data-date-grid] .date-picker__day').forEach(function (node) {
      node.tabIndex = node === cell ? 0 : -1;
    });
    cell.focus();
  }

  function choose(root, key) {
    var input = root.querySelector('[data-date-input]');
    input.value = key;
    state(root).focus = key;
    /* The autosave listens for the change; the popover closes itself. */
    input.dispatchEvent(new Event('change', { bubbles: true }));
    var panel = root.querySelector('.date-picker__panel');
    if (panel && panel.matches(':popover-open')) panel.hidePopover();
  }

  function shiftMonth(root, delta) {
    var data = state(root);
    var target = new Date(data.month.getFullYear(), data.month.getMonth() + delta, 1);
    data.month = target;
    var day = parse(data.focus) || target;
    data.focus = iso(new Date(target.getFullYear(), target.getMonth(), Math.min(day.getDate(), 28)));
    render(root);
  }

  document.addEventListener('click', function (event) {
    var open = event.target.closest('[data-date-open]');
    if (open) {
      var root = open.closest('[data-date-picker]');
      var input = root.querySelector('[data-date-input]');
      var current = parse(input.value) || new Date();
      root.__dateState = {
        month: new Date(current.getFullYear(), current.getMonth(), 1),
        focus: iso(current),
      };
      render(root);
      var panel = root.querySelector('.date-picker__panel');
      panel.showPopover();
      var cell = panel.querySelector('[data-date="' + root.__dateState.focus + '"]');
      if (cell) cell.focus();
      return;
    }
    var root = event.target.closest('[data-date-picker]');
    if (!root) return;
    if (event.target.closest('[data-date-prev]')) { shiftMonth(root, -1); return; }
    if (event.target.closest('[data-date-next]')) { shiftMonth(root, 1); return; }
    if (event.target.closest('[data-date-today]')) { choose(root, iso(new Date())); return; }
    if (event.target.closest('[data-date-clear]')) { choose(root, ''); return; }
    var day = event.target.closest('[data-date-grid] .date-picker__day');
    if (day) choose(root, day.dataset.date);
  });

  document.addEventListener('keydown', function (event) {
    var cell = event.target.closest && event.target.closest('[data-date-grid] .date-picker__day');
    if (!cell) return;
    var root = cell.closest('[data-date-picker]');
    var data = state(root);
    var current = parse(cell.dataset.date);
    if (!current) return;
    var move = null;
    if (event.key === 'ArrowLeft') move = -1;
    if (event.key === 'ArrowRight') move = 1;
    if (event.key === 'ArrowUp') move = -7;
    if (event.key === 'ArrowDown') move = 7;
    if (event.key === 'Home') move = -((current.getDay() + 6) % 7);
    if (event.key === 'End') move = 6 - ((current.getDay() + 6) % 7);
    if (event.key === 'PageUp') { event.preventDefault(); shiftMonth(root, -1); focusDay(root, data.focus); return; }
    if (event.key === 'PageDown') { event.preventDefault(); shiftMonth(root, 1); focusDay(root, data.focus); return; }
    if (move !== null) {
      event.preventDefault();
      var target = new Date(current);
      target.setDate(current.getDate() + move);
      focusDay(root, iso(target));
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(root, cell.dataset.date);
    }
  });
})();
