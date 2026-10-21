# MUI patterns

Use for MUI work. Project rules override placeholder values. Team palette, locale, DataGrid classes, and motion live in `team-conventions`; hybrid rules live in [MUI and shadcn coexistence](../../../shared/ui/hybrid-coexistence.md).

## Theme and defaults

- Keep the theme to branding, locale, breakpoints, and true app-wide defaults. Prefer call-site styling over `components.styleOverrides`.
- Set `cssVariables: true`; use the project font variable and explicit locale.
- Align `sm`/`md`/`lg` with Tailwind; declare TypeScript breakpoint augmentation for custom `2xl`.
- Dense controls use `size="small"`.
- Set `MuiButton.defaultProps` to `variant="contained"` and `disableElevation`; secondary/cancel buttons override to text, and destructive buttons use `color="error"`.
- Default-import MUI icons to avoid the package barrel.
- Use Tailwind flex/grid unless a MUI component requires MUI Grid.

## Data Grid Pro

- Every flexible column needs both `flex: 1` and `minWidth`.
- Memoize column arrays. Keep render handlers stable with `useCallback`; when they need frequently changing state, store the current implementation in a ref and expose a stable callback.
- Apply the row generic to `GridColDef`, `GridRowParams`, `GridRenderCellParams`, `GridValueGetter`, and `GridValidRowModel`.
- Pin read-only/preview actions, selection, and reorder left. Pin write/destructive actions right and last; never pin actions in the middle.
- One row action uses one button; two use two icon buttons in an 80 px cell; three or more use one overflow menu.
- In-cell actions call `stopPropagation()` when the row is clickable, including links.
- Prefer separate grids for separate data sets and explicit toolbar/actions over cell-click modals.

With `autoHeight`, initially empty rows can collapse the loading overlay. Prefer server fetch plus client hydration; otherwise use a fixed height. Reserve client `loading=true` for later fetches.

Server operations are all-or-nothing: set `paginationMode`, `filterMode`, and `sortingMode` to `server`, with `rowCount` and handlers, or omit all three for client mode.

## Date and time

- Use Dayjs `LocalizationProvider` at app root, explicit format such as `DD/MM/YYYY`, and data bounds via `minDate`/`maxDate`.
- Prefer `DateRangePicker` over two DatePickers.
- Use `TimePicker ampm={false}` or keyboard-only `TimeField`, never native `TextField type="time"`. Serialize with `format("HH:mm:ss")`.

## Dialogs and drawers

- Dialog: confirmation, preview/confirm, destructive action, or compact form up to three fields.
- Right drawer: sectioned, scrolling, or more than five or six inputs. If a dialog needs scrolling, use a drawer.
- Add `DialogContent sx={{ pt: 1 }}` only when its first child is a floating-label input.
- Separate mixed input rows with `pt-4`; separate drawer sections with `<Divider sx={{ my: 1.5 }} />`.
- Drawer width: `{ xs: "100%", sm: 620 }`. Keep header/footer fixed and body `flex-1 overflow-y-auto`; use full-width 42px footer buttons.

## Sources

- [MUI](https://mui.com/material-ui/getting-started/)
- [Data Grid Pro](https://mui.com/x/react-data-grid/)
- [Date Pickers Pro](https://mui.com/x/react-date-pickers/)
