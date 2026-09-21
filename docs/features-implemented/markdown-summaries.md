# Markdown summaries

Every character, NPC, place, session, story and page has a short description
written in CommonMark. The server renders it with raw HTML disabled and resolves
`@[Name]` references with the same links, type metadata and tint used in document
bodies. Missing or ambiguous names remain visible placeholders.

Editors open the rendered summary in place with a double click. A compact
CodeMirror field provides the active-line preview, visible caret and the `@`
suggestion menu. Suggestions show the content type; names shared by more than one
type insert qualified labels such as `@[luogo:Roccianera]`. `Ctrl/⌘+Enter` returns
to the server-rendered result. The field uses the document autosave queue,
optimistic version, offline draft and conflict recovery shared by names, titles
and bodies. Names and titles remain single-line fields.

Reference indexing scans the summary and body together on every create, update,
import or rebuild. Labels are deduplicated before rows are written, so a mention
in either field creates one backlink. Readers receive rendered HTML and do not
download the editor bundle; CodeMirror is loaded only on editable pages and
forms.
