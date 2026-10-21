# Team interactions

Project rules win. Keep the toast library the project already uses (`sonner` or
`react-hot-toast`); never install both. All projects follow the copy and write
flow below.

## Copy

<!-- TODO(circeus): if the product localizes, replace these English defaults
with the product language once, here. -->

- `Confirm`: reversible, non-destructive action when the title asks a complete question.
- `Cancel`: cancel beside primary.
- `Save`: form-dialog primary.
- `Delete`: destructive; ask with the object, for example `Delete campaign "X"?`.
- Display-only dialog: close icon, no button.
- Loading: gerund, for example `Deleting ...`; success agrees with noun/number.
- Error fallback: `Something went wrong`; validation: `Required field`, `Invalid value`.

For DataGrid/forms, abbreviate only while readable. Universal terms such as ISO
codes and units are fine. Put column-wide units in the header. Use `Created at`
and `Last updated`. Rename cryptic labels instead of adding hover-only
descriptions.

## Writes: close, then resolve one toast

Close the modal, create one loading toast, and resolve the same `id`:

```tsx
import toast from "react-hot-toast"; // or the project's sonner import
```

Then use the same flow:

```tsx
async function handleConfirm() {
  onClose();
  const id = toast.loading("Deleting campaigns");
  try {
    const res = await deleteCampaigns(ids);
    if (res.status !== 200) {
      toast.error("Delete failed", { id });
      return;
    }
    toast.success("Campaigns deleted", { id });
  } catch (error) {
    toast.error("Delete failed", { id });
    posthog.captureException(error);
  }
}
```

HTTP failures are user-visible, not exceptions. Send only thrown exceptions to
PostHog when configured. Touched modal writes must not retain
`isSaving`/`isDeleting`/`isLoading`; a non-modal inline action may use
`data-loading`.

Toast writes only. Initial reads, polling, and optimistic updates use their own
patterns; initial reads use skeletons or `loading.tsx`.

## Duration and placement

- Loading: indefinite until replaced by `id`.
- Quick success: ~2s; meaningful information: ~10s; error: ~20s.
- Polling notices use a stable `id` to replace rather than stack.
- Mount one `<Toaster position="top-center" />` per [shell](shell.md).

Modal control rules live in [shadcn conventions](../../../shared/conventions/typescript/frontend/shadcn.md).
