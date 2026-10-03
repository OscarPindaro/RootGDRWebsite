const main = document.querySelector('#main');
const detailsDialog = document.querySelector('#details-dialog');
const params = new URLSearchParams(location.search);
const viewNames = { character: 'Personaggi', place: 'Luoghi', session: 'Sessioni', story: 'Storie', page: 'Pagine', fields: 'Campi', mentions: 'Menzioni' };
let view = Object.hasOwn(viewNames, params.get('view')) ? params.get('view') : 'character';
let layout = ['a', 'b', 'c'].includes(params.get('layout')) ? params.get('layout') : 'c';
let toolbar = 'icons';
let editing = false;
let saveTimer;
let toastTimer;
let mentionIndex = 0;
let mentionMatches = [];
let mentionStart = 0;
let calendarMonth = new Date();
const localDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const escape = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const icon = (name) => `<svg class="study-icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const palette = ['Vermiglio', 'Arancio', 'Ocra', 'Oliva', 'Bosco', 'Turchese', 'Cielo', 'Cobalto', 'Indaco', 'Prugna', 'Rosa', 'Argilla'];
const sessions = [
  { title: 'La prima notte', date: '19 settembre 2026' },
  { title: 'Il pedaggio del Guado', date: '26 settembre 2026' },
  { title: 'Le voci del mercato', date: '3 ottobre 2026' },
];
const entities = [
  { name: 'Paolo', kind: 'Personaggio', tint: 2, icon: 'cat' },
  { name: 'Il Guado Spezzato', kind: 'Luogo', tint: 6, icon: 'place' },
  { name: 'La prima notte', kind: 'Sessione', tint: 8, icon: 'calendar' },
  { name: 'La strada per il Guado', kind: 'Storia', tint: 5, icon: 'book' },
];
const documents = {
  character: { title: 'Paolo', subtitle: 'Il mariuolo', summary: 'Conosce ogni sentiero del Bosco. E qualche scorciatoia di troppo.', body: '', tint: 2, draft: false, locked: false, bodyLabel: 'Descrizione', invitation: 'Aggiungi una descrizione', owner: 'Giocato da e2e-admin@example.com' },
  place: { title: 'Il Guado Spezzato', subtitle: 'Una radura sul fiume', summary: 'Il passaggio tra le due rive, dove ogni viaggio ha il suo prezzo.', body: '', tint: 6, draft: true, locked: false, bodyLabel: 'Descrizione', invitation: 'Aggiungi una descrizione' },
  session: { title: 'La mia nuova sessione', summary: 'Una sera al tavolo con Fabio, Hakim ed Enka.', body: '', tint: 1, draft: true, locked: false, bodyLabel: 'Resoconto', invitation: 'Scrivi il resoconto', worldDate: 'Autunno, terzo anno', realDate: localDate(new Date()) },
  story: { title: 'La strada per il Guado', summary: 'Un pedaggio conteso, un patto fragile e due rive da riconciliare.', body: '', tint: 1, draft: true, locked: false, bodyLabel: 'Testo', invitation: 'Inizia a scrivere', period: 'Autunno, terzo anno', status: 'In corso', sessionIds: [0, 1] },
  page: { title: 'Usanze del Bosco', summary: 'Le promesse, i piccoli riti e le cose che si imparano vivendo tra le radure.', body: '', tint: 5, draft: true, locked: false, bodyLabel: 'Testo', invitation: 'Inizia a scrivere', slug: 'customs-of-the-woodland', position: 3 },
};

function tintPicker(doc) {
  return `<div class="metadata-item"><span class="control-label">Colore</span>
    <button class="tint-trigger" data-palette-toggle aria-label="Scegli colore" aria-expanded="false"><span class="tint-swatch" aria-hidden="true"></span><span data-tint-name>${palette[doc.tint - 1]}</span>${icon('chevron')}</button>
    <div class="tint-palette" data-palette hidden><span class="control-label">Tinta del documento</span><div class="tint-options" role="group" aria-label="Palette di dodici colori">
      ${palette.map((name, index) => `<button class="tint-option" data-tint="${index + 1}" aria-label="${name}" title="${name}" aria-pressed="${doc.tint === index + 1}" style="--swatch: var(--p${index + 1})">${doc.tint === index + 1 ? icon('check') : ''}</button>`).join('')}
    </div><p>Una tinta per riconoscere la tua scheda.</p></div></div>`;
}

function metadata(doc) {
  let fields = '';
  if (view === 'session') fields = `<label class="metadata-item"><span class="control-label">Data nel mondo</span><input aria-label="Data nel mondo" data-property="worldDate" value="${escape(doc.worldDate)}" ${doc.locked ? 'disabled' : ''}></label>
    <div class="metadata-item"><label class="control-label" for="real-date">Data reale</label><div class="date-control"><input id="real-date" data-real-date data-property="realDate" type="date" value="${doc.realDate}" ${doc.locked ? 'disabled' : ''}><button class="calendar-trigger" data-calendar-toggle aria-label="Apri calendario" aria-expanded="false" ${doc.locked ? 'disabled' : ''}>${icon('calendar')}</button></div><div class="calendar-popup" data-calendar hidden role="dialog" aria-label="Calendario"></div></div>`;
  if (view === 'story') fields = `<label class="metadata-item"><span class="control-label">Periodo</span><input aria-label="Periodo" data-property="period" value="${escape(doc.period)}" ${doc.locked ? 'disabled' : ''}></label>
    <label class="metadata-item"><span class="control-label">Stato della storia</span><select aria-label="Stato della storia" data-property="status" ${doc.locked ? 'disabled' : ''}>${['In corso', 'Conclusa', 'Sospesa'].map((status) => `<option ${doc.status === status ? 'selected' : ''}>${status}</option>`).join('')}</select></label>`;
  if (view === 'page') fields = `<label class="metadata-item"><span class="control-label">Indirizzo</span><input aria-label="Indirizzo della pagina" data-property="slug" value="${escape(doc.slug)}" ${doc.locked ? 'disabled' : ''}></label>
    <label class="metadata-item"><span class="control-label">Posizione nel menu</span><input aria-label="Posizione nel menu" data-property="position" type="number" min="0" value="${doc.position}" ${doc.locked ? 'disabled' : ''}></label>`;
  const relationship = view === 'story' ? `<div class="relationship-row"><div><span class="control-label">Sessioni collegate</span><p>${doc.sessionIds.length ? doc.sessionIds.map((id) => escape(sessions[id].title)).join(' · ') : 'Nessuna sessione collegata'}</p></div><button class="command" data-sessions ${doc.locked ? 'disabled' : ''}>Gestisci ${icon('chevron')}</button></div>` : '';
  return `<section class="metadata-region" aria-label="Dettagli del documento"><div class="metadata-grid">${fields}${tintPicker(doc)}</div>${relationship}</section>`;
}

function detailsSummary(doc) {
  return `${view === 'story' ? `${doc.status} · ${doc.sessionIds.length} sessioni` : `Posizione ${doc.position}`} · ${palette[doc.tint - 1]}`;
}

function renderDetails() {
  const doc = documents[view];
  detailsDialog.style.setProperty('--document-tint', `var(--p${doc.tint})`);
  detailsDialog.querySelector('[data-details-context]').textContent = doc.title;
  detailsDialog.querySelector('[data-details-body]').innerHTML = metadata(doc);
  if (doc.locked) detailsDialog.querySelectorAll('[data-palette-toggle]').forEach((button) => { button.disabled = true; });
}

function writing(doc) {
  return `<section class="writing-section"><div class="writing-heading"><span class="identity-label">${doc.bodyLabel}</span><span>Scrivi direttamente nel documento</span></div>
    <div class="writing-host">
      <button class="writing-empty" data-write ${doc.body || editing ? 'hidden' : ''} ${doc.locked ? 'disabled' : ''}>${icon('pencil')}<span>${doc.invitation}<small>Markdown e menzioni, come nella sintesi.</small></span></button>
      <div class="writing-preview" ${!doc.body || editing ? 'hidden' : ''}><span data-body-preview>${escape(doc.body)}</span><br><button class="command" data-write ${doc.locked ? 'hidden' : ''}>${icon('pencil')} Modifica il testo</button></div>
      <div class="writing-editor" ${editing ? '' : 'hidden'}><div class="writing-tools"><span>Markdown · @ per citare</span><button class="command" data-preview>Mostra il risultato ${icon('check')}</button></div><textarea aria-label="Testo Markdown" spellcheck="false">${escape(doc.body)}</textarea><div class="mention-menu" data-mention-menu role="listbox" aria-label="Menzioni" hidden></div></div>
    </div><div class="writing-footer">${editing ? 'Ctrl / ⌘ + Invio per il risultato · Esc per uscire' : 'F2 per iniziare a scrivere'}</div></section>`;
}

function actionBar(doc) {
  return `<div class="document-toolbar" data-style="${toolbar}"><div class="document-facts"><span class="eyebrow">${{ character: 'Personaggio', place: 'Luogo', session: 'Sessione', story: 'Storia', page: 'Pagina' }[view]}</span><span class="state-badge ${doc.draft ? 'draft' : ''}" data-publication-state>${doc.draft ? 'Bozza' : 'Pubblicato'}</span>${doc.owner ? `<span class="owner-label">${escape(doc.owner)}</span>` : ''}</div>
    <div class="document-commands"><button class="command primary" data-edit aria-label="Modifica" title="Modifica · F2" ${doc.locked ? 'disabled' : ''}>${icon('pencil')}<span class="command-text">Modifica</span></button>
      <button class="command" data-lock aria-label="${doc.locked ? 'Bloccato' : 'Sbloccato'}" title="${doc.locked ? 'Sblocca il documento' : 'Blocca il documento'}" aria-pressed="${doc.locked}">${icon(doc.locked ? 'lock' : 'unlock')}<span class="command-text">${doc.locked ? 'Bloccato' : 'Sbloccato'}</span></button>
      <button class="command" data-publish aria-label="${doc.draft ? 'Pubblica' : 'Riporta a bozza'}" title="${doc.draft ? 'Pubblica' : 'Riporta a bozza'} · Ctrl/⌘+Shift+Invio" ${doc.locked ? 'disabled' : ''}>${icon(doc.draft ? 'publish' : 'undo')}<span class="command-text">${doc.draft ? 'Pubblica' : 'Riporta a bozza'}</span></button>
      <details class="action-disclosure"><summary class="command icon-command" aria-label="Altre azioni" title="Altre azioni">${icon('more')}</summary><div class="action-menu"><button data-shortcuts>Scorciatoie</button><button class="danger" data-demo-danger>${doc.draft ? 'Annulla bozza' : 'Elimina'}</button></div></details></div></div>
    <div class="document-save-line"><span class="save-state" role="status" data-save-status>Salvato · demo</span></div>`;
}

function renderDocument(doc) {
  const previousEditor = main.querySelector('.writing-editor textarea');
  const caret = editing && previousEditor ? { start: previousEditor.selectionStart, end: previousEditor.selectionEnd, scroll: previousEditor.scrollTop } : null;
  const hasFace = view === 'character' || view === 'place';
  const identity = `<div class="document-identity ${hasFace ? 'character-head' : ''}">${hasFace ? `<div><div class="character-portrait">${icon(view === 'character' ? 'cat' : 'place')}</div><p class="portrait-note">${view === 'character' ? 'Gatto' : 'Radura'} · ${palette[doc.tint - 1]}</p><div class="character-tint">${tintPicker(doc)}</div></div>` : ''}
    <div><label class="identity-label" for="document-title">${hasFace ? 'Nome' : 'Titolo'}</label><h1><input id="document-title" class="identity-input" aria-label="Titolo" data-property="title" value="${escape(doc.title)}" ${doc.locked ? 'disabled' : ''}></h1>
      ${doc.subtitle ? `<label class="identity-label" for="document-subtitle">Titolo</label><input id="document-subtitle" class="identity-input subtitle-input" aria-label="Titolo del personaggio" data-property="subtitle" value="${escape(doc.subtitle)}" ${doc.locked ? 'disabled' : ''}>` : '<div class="identity-breath"></div>'}
      <label class="identity-label" for="document-summary">Sintesi</label><textarea id="document-summary" rows="2" class="identity-input summary-input" aria-label="Sintesi" data-property="summary" ${doc.locked ? 'disabled' : ''}>${escape(doc.summary)}</textarea></div></div>`;
  let sheet = writing(doc);
  if (!hasFace) {
    const details = metadata(doc);
    if (layout === 'b' && (view === 'story' || view === 'page')) sheet = `<div class="layout-margin"><div>${sheet}</div>${details}</div>`;
    else if (layout === 'c' && (view === 'story' || view === 'page')) sheet = `<button class="details-trigger" data-details-open aria-label="Dettagli del documento" aria-haspopup="dialog" aria-expanded="${detailsDialog.open}"><span><span class="control-label">Dettagli</span><span data-details-summary>${escape(detailsSummary(doc))}</span></span>${icon('chevron')}</button>${sheet}`;
    else sheet = details + sheet;
  }
  main.style.setProperty('--document-tint', `var(--p${doc.tint})`);
  main.innerHTML = `<nav class="document-crumbs" aria-label="Percorso"><a href="../index.html">Mondi</a><span>/</span><a href="../mondo.html">Boscochiaro</a><span>/</span><span>${viewNames[view]}</span><span>/</span><span data-crumb-title>${escape(doc.title)}</span></nav>${actionBar(doc)}
    <div class="document-spread"><article class="document-sheet">${identity}${sheet}</article><aside class="backlinks"><span class="identity-label">Collegamenti</span>${view === 'story' ? '<a href="?view=session">La prima notte</a><a href="?view=place">Il Guado Spezzato</a><a href="?view=character">Paolo</a>' : '<p>I riferimenti al documento compariranno qui.</p>'}<div class="margin-note"><strong>La proposta</strong><p>${view === 'story' || view === 'page' ? { a: 'Dettagli compatti, tutti visibili. Il testo rimane il centro della pagina.', b: 'I dettagli passano a margine; i collegamenti conservano il loro spazio.', c: 'Il riepilogo rimane nel documento. I dettagli si aprono in un pannello separato.' }[layout] : 'Stati separati dai comandi. Un invito chiaro per iniziare a scrivere, anche quando il testo è vuoto.'}</p></div></aside></div>`;
  if (doc.locked) main.querySelectorAll('[data-palette-toggle]').forEach((button) => { button.disabled = true; });
  if (caret) {
    const editor = main.querySelector('.writing-editor textarea');
    editor.setSelectionRange(caret.start, caret.end);
    editor.scrollTop = caret.scroll;
  }
  if (detailsDialog.open) renderDetails();
}

function mentionChoices(items, rich = true, interactive = false) {
  return items.map((entity, index) => `<button class="mention-choice" ${interactive ? `role="option" aria-selected="${index === mentionIndex}" data-mention="${index}"` : `data-demo-mention="${escape(entity.name)}"`} tabindex="${interactive ? '-1' : '0'}"><span class="mention-mark" style="--swatch: var(--p${entity.tint})">${rich ? icon(entity.icon) : ''}</span><span class="mention-name">${escape(entity.name)}</span><span class="mention-kind">${entity.kind}</span></button>`).join('');
}

function renderSpecimen() {
  if (view === 'fields') main.innerHTML = `<nav class="document-crumbs">Studio / Campi e label</nav><div class="document-save-line"><span class="save-state">Salvato · demo</span></div><h1 class="specimen-title">Una label sulla riga.</h1><p class="specimen-note">Clicca nei campi: la label si ferma sul bordo, senza cambiare lo spazio occupato dal form.</p><div class="field-specimens"><div><div class="outlined-field"><input id="world-name" placeholder=" " value="Le Cronache di Boscochiaro"><label for="world-name">Nome</label></div><p class="field-support">Il nome con cui riconoscere il mondo.</p></div><div><div class="outlined-field"><textarea id="world-description" placeholder=" "></textarea><label for="world-description">Descrizione</label></div><p class="field-support">Markdown. Puoi modificarla in seguito.</p></div><div><span class="control-label">Allineamento del salvataggio</span><div class="field-state-comparison"><span class="save-state">Salvato</span><span class="save-state dirty">Salvataggio…</span></div></div></div>`;
  else main.innerHTML = `<nav class="document-crumbs">Studio / Menzioni</nav><div class="document-save-line"></div><h1 class="specimen-title">Riconoscere chi stai citando.</h1><p class="specimen-note">Lo stesso menu con due trattamenti: il colore da solo, oppure l’identità del contenuto. Prova anche a scrivere @ nella descrizione di un documento.</p><div class="mentions-specimen"><section><span class="identity-label">A / Tinta rettangolare</span><div class="mention-menu">${mentionChoices(entities, false)}</div></section><section><span class="identity-label">B / Identità e tinta</span><div class="mention-menu">${mentionChoices(entities)}</div></section></div>`;
}

function render() {
  document.querySelectorAll('[data-view]').forEach((link) => {
    if (link.dataset.view === view) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  document.querySelector('[data-layout-controls]').hidden = !['story', 'page'].includes(view);
  document.querySelectorAll('[data-layout]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.layout === layout)));
  document.querySelectorAll('[data-toolbar]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.toolbar === toolbar)));
  if (documents[view]) renderDocument(documents[view]);
  else renderSpecimen();
  const url = new URL(location.href);
  url.searchParams.set('view', view);
  url.searchParams.set('layout', layout);
  history.replaceState(null, '', url);
}

function markDirty() {
  const status = main.querySelector('[data-save-status]');
  if (!status) return;
  status.textContent = 'Salvataggio… · demo';
  status.classList.add('dirty');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const current = main.querySelector('[data-save-status]');
    if (current) { current.textContent = 'Salvato · demo'; current.classList.remove('dirty'); }
  }, 900);
}

function openWriting() {
  const doc = documents[view];
  if (!doc || doc.locked) return;
  editing = true;
  renderDocument(doc);
  const textarea = main.querySelector('.writing-editor textarea');
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);
}

function closeWriting() {
  if (!editing) return;
  editing = false;
  renderDocument(documents[view]);
  main.querySelector('[data-write]')?.focus({ preventScroll: true });
}

function toast(message) {
  const surface = document.querySelector('.study-toast');
  surface.textContent = message;
  surface.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { surface.hidden = true; }, 3500);
}

function updateMentions(textarea) {
  const match = textarea.value.slice(0, textarea.selectionStart).match(/@([^\s@\[\]]*)$/);
  const menu = main.querySelector('[data-mention-menu]');
  mentionMatches = match ? entities.filter((entity) => entity.name.toLocaleLowerCase('it').includes(match[1].toLocaleLowerCase('it'))) : [];
  menu.hidden = !mentionMatches.length;
  if (menu.hidden) return;
  mentionStart = textarea.selectionStart - match[0].length;
  mentionIndex = 0;
  menu.innerHTML = `<span class="control-label">Cita un contenuto</span>${mentionChoices(mentionMatches, true, true)}`;
}

function chooseMention(index) {
  const textarea = main.querySelector('.writing-editor textarea');
  const entity = mentionMatches[index];
  if (!entity || !textarea) return;
  const insertion = `@[${entity.name}] `;
  textarea.setRangeText(insertion, mentionStart, textarea.selectionStart, 'end');
  documents[view].body = textarea.value;
  main.querySelector('[data-mention-menu]').hidden = true;
  textarea.focus();
  markDirty();
}

function calendar() {
  const doc = documents.session;
  const year = calendarMonth.getFullYear();
  const month = calendarMonth.getMonth();
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7;
  const dates = Array.from({ length: 42 }, (_, index) => new Date(year, month, 1 - offset + index));
  main.querySelector('[data-calendar]').innerHTML = `<div class="calendar-header"><button data-calendar-month="-1" aria-label="Mese precedente">${icon('arrow')}</button><span>${first.toLocaleDateString('it', { month: 'long', year: 'numeric' })}</span><button class="calendar-next" data-calendar-month="1" aria-label="Mese successivo">${icon('arrow')}</button></div><div class="calendar-grid">${['L', 'M', 'M', 'G', 'V', 'S', 'D'].map((day) => `<span>${day}</span>`).join('')}${dates.map((date) => `<button data-calendar-date="${localDate(date)}" aria-label="${date.toLocaleDateString('it', { dateStyle: 'full' })}" class="${date.getMonth() !== month ? 'outside' : ''} ${localDate(date) === doc.realDate ? 'selected' : ''} ${localDate(date) === localDate(new Date()) ? 'today' : ''}">${date.getDate()}</button>`).join('')}</div><div class="calendar-footer"><button data-calendar-date="">Cancella</button><button data-calendar-date="${localDate(new Date())}">Oggi</button></div>`;
}

function closeRail() {
  document.querySelector('#rail').classList.remove('is-open');
  document.querySelector('[data-close-rail]').hidden = true;
  document.querySelector('[data-open-rail]').setAttribute('aria-expanded', 'false');
}

document.addEventListener('input', (event) => {
  const target = event.target;
  const doc = documents[view];
  if (!doc || doc.locked) return;
  if (target.dataset.property) {
    doc[target.dataset.property] = target.value;
    if (target.dataset.property === 'title') main.querySelector('[data-crumb-title]').textContent = target.value;
    const summary = main.querySelector('[data-details-summary]');
    if (summary) summary.textContent = detailsSummary(doc);
    markDirty();
  }
  if (target.matches('.writing-editor textarea')) { doc.body = target.value; markDirty(); updateMentions(target); }
});

main.addEventListener('dblclick', (event) => {
  if (event.target.matches('.identity-input')) event.target.select();
  if (event.target.closest('.writing-preview')) openWriting();
});

main.addEventListener('pointerdown', (event) => {
  if (event.target.closest('[data-mention]')) event.preventDefault();
});

document.addEventListener('click', (event) => {
  const target = event.target.closest('button, a, summary');
  if (!target) return;
  const doc = documents[view];
  if (target.dataset.view) { event.preventDefault(); view = target.dataset.view; editing = false; closeRail(); render(); }
  else if (target.dataset.layout) { layout = target.dataset.layout; render(); }
  else if (target.dataset.toolbar) { toolbar = target.dataset.toolbar; render(); }
  else if (target.matches('[data-edit], [data-write]')) openWriting();
  else if (target.matches('[data-preview]')) closeWriting();
  else if (target.matches('[data-details-open]')) { renderDetails(); detailsDialog.showModal(); target.setAttribute('aria-expanded', 'true'); }
  else if (target.matches('[data-lock]')) { doc.locked = !doc.locked; editing = false; render(); }
  else if (target.matches('[data-publish]') && !doc.locked) { doc.draft = !doc.draft; render(); toast(doc.draft ? 'Riportato a bozza · solo dimostrazione' : 'Pubblicato · solo dimostrazione'); }
  else if (target.matches('[data-demo-danger]')) toast('Dimostrazione: nessun contenuto viene eliminato. Nell’app questa azione richiede conferma.');
  else if (target.matches('[data-shortcuts]')) document.querySelector('#shortcuts-dialog').showModal();
  else if (target.matches('[data-palette-toggle]')) {
    const popup = target.parentElement.querySelector('[data-palette]');
    popup.hidden = !popup.hidden;
    target.setAttribute('aria-expanded', String(!popup.hidden));
    if (!popup.hidden) popup.querySelector('[aria-pressed="true"]').focus();
  }
  else if (target.dataset.tint) { doc.tint = Number(target.dataset.tint); render(); markDirty(); (detailsDialog.open ? detailsDialog : main).querySelector('[data-palette-toggle]').focus(); }
  else if (target.matches('[data-calendar-toggle]')) {
    const popup = main.querySelector('[data-calendar]');
    popup.hidden = !popup.hidden;
    target.setAttribute('aria-expanded', String(!popup.hidden));
    if (!popup.hidden) { calendarMonth = new Date(doc.realDate ? `${doc.realDate}T12:00:00` : Date.now()); calendar(); }
  }
  else if (target.dataset.calendarMonth) { calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + Number(target.dataset.calendarMonth), 1); calendar(); }
  else if (target.hasAttribute('data-calendar-date')) { doc.realDate = target.dataset.calendarDate; render(); markDirty(); main.querySelector('[data-calendar-toggle]').focus(); }
  else if (target.hasAttribute('data-mention')) chooseMention(Number(target.dataset.mention));
  else if (target.dataset.demoMention) toast(`Menzione selezionata: ${target.dataset.demoMention} · demo`);
  else if (target.matches('[data-open-rail]')) { document.querySelector('#rail').classList.add('is-open'); document.querySelector('[data-close-rail]').hidden = false; target.setAttribute('aria-expanded', 'true'); }
  else if (target.matches('[data-close-rail]')) { closeRail(); document.querySelector('[data-open-rail]').focus(); }
  else if (target.matches('[data-sessions]')) {
    document.querySelector('[data-session-search]').value = '';
    document.querySelector('[data-session-options]').innerHTML = sessions.map((session, index) => `<label><input type="checkbox" value="${index}" ${doc.sessionIds.includes(index) ? 'checked' : ''}><span>${session.title}<small>${session.date}</small></span></label>`).join('');
    document.querySelector('#sessions-dialog').showModal();
  }
  else if (target.matches('[data-close-sessions]')) document.querySelector('#sessions-dialog').close();
  else if (target.matches('[data-apply-sessions]')) { doc.sessionIds = [...document.querySelectorAll('[data-session-options] input:checked')].map((input) => Number(input.value)); document.querySelector('#sessions-dialog').close(); render(); markDirty(); (detailsDialog.open ? detailsDialog : main).querySelector('[data-sessions]')?.focus(); }
});

document.querySelector('[data-session-search]').addEventListener('input', (event) => {
  const query = event.target.value.toLocaleLowerCase('it');
  document.querySelectorAll('[data-session-options] label').forEach((label) => { label.hidden = !label.textContent.toLocaleLowerCase('it').includes(query); });
});

detailsDialog.addEventListener('close', () => {
  detailsDialog.querySelector('[data-details-body]').replaceChildren();
  const trigger = main.querySelector('[data-details-open]');
  trigger?.setAttribute('aria-expanded', 'false');
  trigger?.focus({ preventScroll: true });
});

detailsDialog.addEventListener('cancel', (event) => {
  const popup = detailsDialog.querySelector('[data-palette]:not([hidden])');
  if (!popup) return;
  event.preventDefault();
  popup.hidden = true;
  const trigger = popup.parentElement.querySelector('[data-palette-toggle]');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.focus();
});

document.addEventListener('keydown', (event) => {
  if (document.querySelector('dialog[open]')) return;
  const target = event.target;
  const menu = main.querySelector('[data-mention-menu]');
  if (editing && menu && !menu.hidden && ['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(event.key)) {
    event.preventDefault();
    if (event.key === 'Enter') chooseMention(mentionIndex);
    else if (event.key === 'Escape') menu.hidden = true;
    else {
      mentionIndex = (mentionIndex + (event.key === 'ArrowDown' ? 1 : -1) + mentionMatches.length) % mentionMatches.length;
      menu.querySelectorAll('[role="option"]').forEach((option, index) => option.setAttribute('aria-selected', String(index === mentionIndex)));
    }
    return;
  }
  if (event.key === 'Escape') {
    const popup = main.querySelector('[data-palette]:not([hidden]), [data-calendar]:not([hidden])');
    if (popup) { popup.hidden = true; const trigger = popup.parentElement.querySelector('[data-palette-toggle], [data-calendar-toggle]'); trigger.setAttribute('aria-expanded', 'false'); trigger.focus(); }
    else if (editing) closeWriting();
    else closeRail();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    if (event.shiftKey && documents[view] && !documents[view].locked) { event.preventDefault(); main.querySelector('[data-publish]').click(); }
    else if (!event.shiftKey && editing) { event.preventDefault(); closeWriting(); }
    return;
  }
  if (event.key === 'F2' && !target.closest('input, textarea, select, [contenteditable]')) { event.preventDefault(); openWriting(); }
});

render();
