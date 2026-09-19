const views = [...document.querySelectorAll('.view')];
const navItems = [...document.querySelectorAll('.nav-item[data-view]')];
const crumb = document.querySelector('#crumb');
const sidebar = document.querySelector('#sidebar');
const scrim = document.querySelector('#scrim');
const palette = document.querySelector('#palette');
const paletteInput = document.querySelector('#palette-input');

const viewNames = {
  home: 'I tuoi mondi',
  world: 'Fronte del Tuono',
  characters: 'Personaggi',
  places: 'Luoghi',
  sessions: 'Sessioni',
  stories: 'Storie',
  lore: 'Il mondo di gioco',
  rules: 'Regole e riferimenti'
};

function closeSidebar() {
  sidebar.classList.remove('open');
  scrim.classList.remove('open');
}

function closePalette() {
  palette.hidden = true;
}

function showView(name, updateHash = true) {
  const target = document.querySelector(`#${name}-view`);
  if (!target) return;
  views.forEach((view) => {
    view.hidden = view !== target;
  });
  crumb.textContent = viewNames[name];
  navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === name));
  document.body.dataset.view = name;
  closeSidebar();
  closePalette();
  if (updateHash && window.location.hash !== `#${name}`) history.pushState(null, '', `#${name}`);
  window.scrollTo({ top: 0, behavior: 'auto' });
}

function openSidebar() {
  sidebar.classList.add('open');
  scrim.classList.add('open');
}

function openPalette() {
  palette.hidden = false;
  paletteInput.value = '';
  setTimeout(() => paletteInput.focus(), 0);
}

document.addEventListener('click', (event) => {
  const control = event.target.closest('[data-view]');
  if (control) showView(control.dataset.view);
});
document.querySelector('#menu-toggle').addEventListener('click', (event) => {
  event.stopPropagation();
  openSidebar();
});
document.querySelector('#sidebar-close').addEventListener('click', closeSidebar);
document.querySelector('#palette-trigger').addEventListener('click', openPalette);
document.querySelector('#sidebar-search').addEventListener('click', (event) => {
  event.stopPropagation();
  closeSidebar();
  openPalette();
});
scrim.addEventListener('click', closeSidebar);
palette.addEventListener('click', (event) => {
  if (event.target === palette) closePalette();
});
window.addEventListener('hashchange', () => showView(window.location.hash.slice(1) || 'world', false));
document.addEventListener('keydown', (event) => {
  if ((event.altKey && event.code === 'Space') || (event.metaKey && event.key.toLowerCase() === 'k')) {
    event.preventDefault();
    openPalette();
  }
  if (event.key === 'Escape') {
    closePalette();
    closeSidebar();
  }
});

showView(window.location.hash.slice(1) || 'world', false);
