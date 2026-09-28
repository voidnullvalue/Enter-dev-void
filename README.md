# Enter /dev/void/

This repo is the index for the blog. Individual posts live in their own GitHub Pages repositories.

The index does **not** contain a hand-maintained post list. A scheduled GitHub Action scans public repositories owned by `voidnullvalue`, reads the metadata from each root `index.html`, sorts matching posts by publication time, builds the index, and deploys it to GitHub Pages.

## Add a post

Put this in the `<head>` of the post's root `index.html`:

```html
<meta name="devvoid:post" content="1">
<meta name="devvoid:title" content="Post title">
<meta name="devvoid:summary" content="One short description of the post.">
<meta name="devvoid:published" content="2026-09-28T19:00:00Z">
<meta name="devvoid:tags" content="linux, reverse-engineering, hardware">
```

Required fields are `post`, `title`, `summary`, and `published`.

`published` should be ISO 8601. A full timestamp is preferred so multiple posts on the same day sort deterministically.

`tags` is optional and comma-separated.

By default the index derives the post URL as:

```text
https://voidnullvalue.github.io/<repository-name>/
```

If a page uses a custom domain or some other URL, add:

```html
<meta name="devvoid:url" content="https://example.com/post/">
```

The index rebuilds on pushes to this repo, on manual dispatch, and every 15 minutes, so adding the metadata to another public Pages repo is enough to make it show up here without editing this repo.
