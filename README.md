# Enter /dev/void/

This repo is the index and deployment root for the blog.

Individual posts still live in their own public GitHub repositories, but the deployed blog no longer sends readers to the separate `github.io/<repo>/` sites. The scheduled indexer discovers posts from their metadata, mirrors each post repository into the Pages artifact under:

```text
https://devslashvoid.dev/posts/<repository-name>/
```

and builds the index, RSS feed, and `posts.json` using those local URLs.

The source repositories remain independently usable GitHub Pages sites; the blog copy is generated at deploy time and is **not** committed back into this repository.

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

A source post may also publish:

```html
<meta name="devvoid:url" content="https://voidnullvalue.github.io/example-post/">
```

That value is retained as the source URL in `posts.json`, but public blog links are generated locally as:

```text
https://devslashvoid.dev/posts/<repository-name>/
```

The index rebuilds on pushes to this repo, on manual dispatch, and every 15 minutes. On each build it:

1. scans public repositories owned by `voidnullvalue`;
2. finds root `index.html` files containing `devvoid:post`;
3. sorts posts by `devvoid:published`;
4. mirrors each matching repository into `_site/posts/<repository-name>/`;
5. rewrites the mirrored page's self/canonical URL to `devslashvoid.dev`;
6. builds the index, RSS feed, and `posts.json`;
7. deploys `_site` to GitHub Pages.

The mirror excludes `.git` and `.github`. If cloning a post repository fails, the indexer falls back to mirroring that post's root `index.html` so the build can still complete.
