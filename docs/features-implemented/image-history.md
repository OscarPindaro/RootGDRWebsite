# Image history

Worlds, characters, NPCs and places keep an immutable history of uploaded images. Their existing `image_file_id` remains the current-image pointer, so existing image URLs and responses continue to work.

Each upload creates a `FileModel` and an `ImageRevisionModel` in the same database transaction, then moves the owner's current pointer. Older objects remain available intentionally. Upload validation still limits actual streamed bytes to 10 MiB, accepts only PNG, JPEG, GIF and WebP magic, and sanitizes filenames.

## API

History uses a shared typed route:

`/api/worlds/{world_id}/images/{owner_kind}/{owner_id}/revisions`

Owner kinds are `world`, `character`, `npc` and `place`.

- `GET /` lists newest first and marks the current revision.
- `GET /{revision_id}/content` reads historical content with `X-Content-Type-Options: nosniff`.
- `POST /{revision_id}/restore` makes a revision current.
- `DELETE /{revision_id}` deletes a non-current revision. A current revision requires `replacement_id=<revision>` or `clear=true`.
- `DELETE /current` clears the pointer without deleting history.

Reads use each feature's normal world/content visibility rules. Restore, deletion and clear use that feature's normal image-management rule: world owner/admin, character owner/world master, or world master for NPCs and places. Revision and replacement IDs must belong to the same typed owner and world.

Deleting an entity removes its revisions and stored objects. Deleting a world removes all revision objects in that world. Database cascades are a final guard for revision rows. Filesystem and database transactions cannot be fully atomic on local storage; failed uploads remove the newly written object, and cleanup tolerates already-missing objects.

The migration backfills every existing current image as its owner's first revision. Downgrade removes history metadata but leaves current pointers and files intact.
