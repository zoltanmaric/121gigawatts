---
name: ghost-posts
description: Updates Ghost posts programmatically through the Admin API, including text, links, images, and iframe destinations. Use for content edits rather than theme or server changes.
---

# Ghost posts

Use the Admin API with an authorized custom integration. Keep credentials and
saved post snapshots outside this public repository. Use the official
[JavaScript client](https://docs.ghost.org/admin-api/javascript) or HTTP
requests authenticated as documented in the [Admin API](https://docs.ghost.org/admin-api).
Use Ghost's configured admin URL and a compatible `Accept-Version` header.

## Read and prepare

- Fetch the target by slug with
  `GET /ghost/api/admin/posts/slug/{slug}/?formats=lexical,html`.
  Check its identity and publication status; save the original response privately.
- Parse the `lexical` JSON string and edit only the intended nodes or fields.
  For an iframe in an HTML card (`type: "html"`), replace only its intended
  `src` in that card's `html`, preserving the surrounding markup and attributes.
  Make URL replacements exact; stop if the expected target is absent or ambiguous.
- Compare the before/after payload. If it is already correct, do not save.
  Preserve the editor structure instead of regenerating the post from rendered
  HTML with `source=html`, which can lose card structure.

## Save

When the requested edit is authorized, use
`PUT /ghost/api/admin/posts/{id}/?save_revision=true`. Send only the fields being
changed plus the fetched `updated_at`. For a body edit:

```javascript
const body = {
  posts: [{
    lexical: JSON.stringify(editedDocument),
    updated_at: post.updated_at
  }]
};
```

Omit unrelated metadata, tags, authors, publication status, and email options.
If changing tags or authors, send the complete intended array: Ghost replaces
these relations rather than merging them. Keep drafts as drafts unless publishing
is requested; an edit to an already published post takes effect immediately.

On a collision, re-fetch and recompute the intended change; stop if concurrent
edits make the requested result unclear. After a timeout or uncertain response,
read the post before retrying so a successful edit is not repeated.

## Verify or undo

Re-fetch the post and confirm the intended editor-content change and preserved
metadata. Check the public page and affected link, image, or embed in a browser;
an HTTP 200 alone does not verify an interactive embed. Report what changed.
To undo an authorized edit, restore the affected fields from the saved snapshot
using the latest `updated_at`, preserving any subsequent unrelated edits.

See Ghost's [post format](https://docs.ghost.org/admin-api/posts/overview) and
[update contract](https://docs.ghost.org/admin-api/posts/updating-a-post).
