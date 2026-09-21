# Image history

Worlds, characters, NPCs and places keep immutable uploaded-image revisions while preserving their existing current-image URL.

## What it does

- Every upload becomes a history revision and moves the owner's `image_file_id` current pointer. Previous revisions remain readable and can be restored.
- The history dialog lists thumbnails, original filenames, timestamps, uploader names and current state. Authorized users can restore or delete a revision, or clear the current pointer.
- Deleting a non-current revision removes its database file row and stored object. Deleting the current revision requires a same-owner replacement or `clear=true`; clearing `/current` retains all history.
- Deleting an entity purges all its revision objects. Deleting a world purges all revision objects in that world.

## How it is built

- Upload creates `FileModel` and `ImageRevisionModel` in the same database transaction, then updates the owner pointer. The shared API is `/api/worlds/{world_id}/images/{owner_kind}/{owner_id}/revisions` for `world`, `character`, `npc` and `place`.
- `GET /` lists newest first, `GET /{revision_id}/content` serves historical bytes with `nosniff`, `POST /{revision_id}/restore` restores, and DELETE routes remove or clear.
- `editorial.ImageEditor` supplies the picker, drag-and-drop surface and accessible native history dialog. Character, NPC and place symbol/shape and tint controls PATCH the typed document API with `expected_version`.
- The migration backfills each existing current image as its owner's first revision. Its downgrade removes history metadata while retaining current pointers and files.

## Notes and limits

- Uploads accept PNG, JPEG, GIF and WebP magic and at most 10 MiB of streamed bytes; filenames are sanitized.
- Reads follow normal content visibility. Mutations follow each feature's normal image-management permissions and reject revisions from another owner or world.
- Read-only and locked documents show only the image or generated fallback.
- Filesystem and database transactions cannot be fully atomic on local storage. Failed uploads discard the new object when possible, and cleanup tolerates an already-missing object.
