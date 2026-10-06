(function () {
  if (window.__circeusTooltip) return;
  window.__circeusTooltip = true;

  var surface = document.createElement('div');
  surface.className = 'tooltip-surface';
  surface.setAttribute('role', 'tooltip');
  surface.setAttribute('popover', 'manual');
  document.body.appendChild(surface);
  var active = null;

  function position() {
    if (!active) return;
    var anchor = active.getBoundingClientRect();
    var gap = 8;
    var left = anchor.left + (anchor.width - surface.offsetWidth) / 2;
    var top = anchor.top - surface.offsetHeight - gap;
    var position = active.dataset.tooltipPosition;
    if (position === 'bottom' || top < gap) top = anchor.bottom + gap;
    left = Math.max(gap, Math.min(left, window.innerWidth - surface.offsetWidth - gap));
    surface.style.left = left + 'px';
    surface.style.top = top + 'px';
  }

  function show(anchor) {
    active = anchor;
    surface.textContent = anchor.dataset.tooltip;
    position();
    /* The surface is a popover, and popover operations cannot overlap: a menu
       opening or closing in the same turn (a trigger click, the focus coming
       back when it closes) must not race the tooltip. Reveal on the next
       frame, and only if this anchor is still the active one. */
    if (!surface.matches(':popover-open')) {
      requestAnimationFrame(function () {
        if (active !== anchor || surface.matches(':popover-open')) return;
        surface.showPopover();
        position();
        surface.classList.add('tooltip-surface-visible');
      });
      return;
    }
    surface.classList.add('tooltip-surface-visible');
  }

  function hide(anchor) {
    if (anchor && anchor !== active) return;
    surface.classList.remove('tooltip-surface-visible');
    if (surface.matches(':popover-open')) surface.hidePopover();
    active = null;
  }

  document.addEventListener('pointerover', function (event) {
    var anchor = event.target.closest('[data-tooltip]');
    if (anchor && !anchor.contains(event.relatedTarget)) show(anchor);
  });
  document.addEventListener('pointerout', function (event) {
    var anchor = event.target.closest('[data-tooltip]');
    if (anchor && !anchor.contains(event.relatedTarget)) hide(anchor);
  });
  document.addEventListener('focusin', function (event) {
    var anchor = event.target.closest('[data-tooltip]');
    if (anchor) show(anchor);
  });
  document.addEventListener('focusout', function (event) {
    var anchor = event.target.closest('[data-tooltip]');
    if (anchor && !anchor.contains(event.relatedTarget)) hide(anchor);
  });
  /* The tooltip yields to a menu: the menu takes the popover stack (and the
     focus), and the two must never show in the same turn. */
  document.addEventListener('toggle', function (event) {
    if (event.target.matches && event.target.matches('[data-menu]')) hide();
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') hide();
  });
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
})();
