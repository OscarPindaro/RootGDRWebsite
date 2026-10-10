# Drawing workspace

The drawing editor's workspace: an admin-only area for geometric artwork, opened
by `REQ-0015/T01`. This milestone ships the shell and its visual reference; the
drawing tools themselves arrive in later tickets.

## What it does

- One component, `editorial.DrawingEditor`, composes the whole workspace: a tool
  rail on the left, the artboard in the middle, layers and properties on the
  right.
- The tool rail names every tool the editor will offer (select, triangle,
  rectangle, circle, polygon, line, cut) and shows the active one with a pressed
  state, not only a colour.
- The artboard is a real SVG: a faint grid, the scene's shapes and the vertex
  handles of the selected object. Shapes render from typed scene data, not from
  raw SVG strings.
- The layer list and the property panel report the selected object and its fill,
  stroke, width and opacity.
- Below the phone breakpoint the workspace stacks, the tools scroll
  horizontally, and the canvas becomes a preview with a note that drawing needs
  a computer.

## How it is built

- `editorial/DrawingEditor.jinja` renders the workspace from a `scene` value
  whose shape is `{artboard, selected, selected_fill, handles, objects}`. The
  component is read-only in this milestone: its commands are present but
  disabled until persistence exists.
- `editorial/DrawingEditor.css` owns the three-column composition. The two fixed
  rails and the artboard proportion are role tokens in `main.css`
  (`--drawing-tool-rail`, `--drawing-side-rail`, `--drawing-artboard-ratio`,
  `--drawing-swatch`, `--drawing-layer-check`), so the component reads tokens and
  never literals.
- `prototypes/devin-prototype/drawings.html` and `drawing-editor.html` are the
  static visual reference, with `drawing.css` mirroring the component's classes.
- The tool icons are server-rendered from the registry; the new names
  (`mouse-pointer-2`, `triangle`, `square`, `circle`, `spline`, `pen-tool`,
  `scissors`, `redo-2`) were added to `tools/build_icons.mjs` and generated with
  `npm run icons`.

## Used by

- `pages.showcase.Showcase` — a read-only specimen.

## Limits

- No drawing interaction yet: the component renders a scene, it does not edit
  one. The tool buttons and commands are inert until the next tickets.
- The scene value is passed in; nothing is loaded, saved or validated here.
- The prototype's tool glyphs are text characters; the application renders the
  Lucide registry icons instead.
- Phone is a preview, not a drawing surface.
