---
name: ghost-posts
description: Previews and updates Ghost posts through the Admin API, including text, links, images, and iframe destinations. Use for content edits rather than theme or server changes.
---

# Ghost posts

Use the Admin API for edits. Keep credentials and saved post snapshots outside
this public repository. Use the official [JavaScript client](https://docs.ghost.org/admin-api/javascript)
or HTTP with Ghost's configured admin URL and a compatible `Accept-Version`.

## Establish access

Use existing authorized access: an Admin API integration key, a staff access
token, or an authenticated staff session. A custom integration is not mandatory.
Check the live installation rather than inferring available access from a backup
or an integration's display name.

Read `GHOST_ADMIN_API_URL` and `GHOST_ADMIN_API_KEY` from the environment, or
`.secrets/ghost-admin.json` with `url` and `key` fields. An empty key is not
configured access. Keep this file gitignored and mode `0600`.

- With authorized SSH/database access, inspect live `api_keys` metadata for
  `type='admin'` and its associated integration/user. Reuse a key whose purpose
  and permissions cover the requested edit, such as content migration. Read its
  `id` and `secret` within the private request process, not tool output; the key
  format is `id:secret`. Do not alter database records to edit a post or create access.
- Otherwise use an existing private key supplied by the user or the signed-in
  Ghost Admin session. For new API access, open Settings → Integrations → Add
  custom integration, name its purpose, and save its Admin API key privately.
  Obtain any required authorization before creating new persistent access.
- For token requests, let the client sign the key, or sign an HS256 JWT with
  header `kid=id`, hexadecimal-decoded secret, `aud='/admin/'`, and an expiry
  within five minutes. Send `Authorization: Ghost <token>`.
  Staff sessions use their existing cookie and Origin requirements instead.
- Test access with a read of the target post. A 403 means that key lacks the
  needed permissions; do not change its role to make the edit. If usable access
  is unavailable, ask the user to supply an Admin API key through a private file
  or environment variable; do not ask them to paste it into chat.

See Ghost's [authentication methods](https://docs.ghost.org/admin-api#authentication).

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

## Preview and approval

Provide Ghost's own shareable preview URL before applying a live change:

- For an unpublished draft, save the proposed content with `status: "draft"`.
- For a published or scheduled post, create a temporary draft with the proposed
  content. Copy the writable fields that affect rendering: title, editor content,
  feature image/alt/caption, authors, tags, excerpt, template, visibility, post
  code injection, and publication date where present. Omit the original ID,
  UUID and slug; set `status: "draft"` and do not send email options. Leave the
  original post untouched; never unpublish it to obtain a preview.
- Read the saved draft's UUID and provide `<site-url>/p/<uuid>/`. Open it once
  to check that it renders the proposed change. A published post's `/p/` URL
  redirects to its live page and is not a preview of pending changes.
- Return that link and a short description of the change, then wait for explicit
  approval. Keep draft content and preview URLs out of this public repository.

## Apply the approved change

After approval, re-fetch the original and check for concurrent edits against the
saved snapshot. If the proposed change needs revision, refresh the preview and
obtain approval again. Update the original post, not the temporary preview copy,
with `PUT /ghost/api/admin/posts/{id}/?save_revision=true`. Send only the fields
being changed plus its latest checked `updated_at`. For a body edit:

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
an HTTP 200 alone does not verify an interactive embed. After a successful
update, remove only the temporary preview draft created for this edit. Report
what changed.
To undo an authorized edit, restore the affected fields from the saved snapshot
using the latest `updated_at`, preserving any subsequent unrelated edits.

See Ghost's [post format](https://docs.ghost.org/admin-api/posts/overview) and
[update contract](https://docs.ghost.org/admin-api/posts/updating-a-post).
