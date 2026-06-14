---
name: wechat-draft
description: 微信公众号内容排版助手。Prepare, beautify, create, or update WeChat Official Account drafts from a packaged article directory. Use when the user provides a package containing article_config.json, wechat_article_template.html, article.md, layout_style_spec.md, and assets, and asks to put the article into the WeChat draft box without publishing.
---

# 微信公众号内容排版助手

Use this skill when the user asks Codex to create or update a WeChat Official Account draft from a local article package.

## Non-negotiable safety rule

Only create or update drafts. Do not publish, do not mass-send, and do not call any WeChat publish or send API.

## Expected package

A package usually contains:

- `article_config.json`
- `wechat_article_template.html`
- optional `wechat_article_template_enhanced.html`
- `article.md`
- `layout_style_spec.md`
- `assets/` with cover and body images

If the user provides a zip file, extract it to a working directory first, then run the plugin script against the extracted package directory.

## Beautification rule

For every future article, prefer a beautified template.

1. If `wechat_article_template_enhanced.html` exists, use it.
2. If it does not exist and the user asks for a polished article, create `wechat_article_template_enhanced.html` first.
3. Keep the original title, digest, author, body images, and image placeholders unless the user explicitly asks for content changes.
4. Avoid empty list items and blank bullets. Prefer paragraphs and card sections over raw lists when formatting for WeChat.
5. Keep inline styles only. Do not use external CSS, JavaScript, or uncontrolled external image links.

The bundled script automatically chooses `wechat_article_template_enhanced.html` when present and falls back to `wechat_article_template.html`.

## Script

Resolve the plugin directory, then use:

```powershell
python scripts/wechat_draft_package.py check --package-dir <package-dir>
python scripts/wechat_draft_package.py create --package-dir <package-dir> --env-file <env-file>
python scripts/wechat_draft_package.py update --package-dir <package-dir> --media-id <draft-media-id> --env-file <env-file>
```

If `python` is unavailable on Windows, use the bundled Codex Python runtime when available.

## Workflow

1. Inspect the package and user instructions.
2. Confirm all required images exist.
3. If needed, create or improve `wechat_article_template_enhanced.html`.
4. Run the script's `check` command.
5. Use `create` for a new draft, or `update` for an existing draft.
6. Report the draft `media_id`, returned WeChat JSON, template used, image replacement status, and manual checks the user should perform in the WeChat backend.

## Error handling

If WeChat returns an error, explain the likely fix. Common cases:

- `40164`: add the current public IP to the WeChat Official Account IP whitelist.
- `40001`: check AppID/AppSecret or access token validity.
- `48001`: the account lacks permission for the API.
- `40007`: invalid draft or material media_id.
- image upload errors: check image type, file size, and whether the upload endpoint is correct.

Never print AppSecret, access tokens, or other credentials.
