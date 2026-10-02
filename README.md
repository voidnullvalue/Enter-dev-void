# Enter /dev/void/

This repo is the index and deployment root for the blog.

Posts can live either:

- in their own public GitHub repository, with the post at the repository root as `index.html`; or
- together in any public repository under `posts/<slug>/index.html`.

That includes this repository itself, so new posts can be added directly under:

```text
Enter-dev-void/
  posts/
    my-new-post/
      index.html
      ...
```

The scheduled indexer discovers posts from their metadata, mirrors each post into the Pages artifact, and publishes it at:

```text
https://devslashvoid.dev/posts/<slug>/
```

For the legacy one-repository-per-post layout, `<slug>` is the repository name, so existing URLs do not change.

For the multi-post layout, `<slug>` is the path beneath `posts/`. For example:

```text
posts/hr54/index.html
```

publishes as:

```text
https://devslashvoid.dev/posts/hr54/
```

The source repositories remain independently usable GitHub Pages sites. The blog copy is generated at deploy time and is **not** committed back into this repository.

## Add a post

Put this in the `<head>` of the post's `index.html`:

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
<meta name="devvoid:url" content="https://example.com/original-post/">
```

That value is retained as the source URL in `posts.json`, but public blog links are generated locally under `https://devslashvoid.dev/posts/`.

## Supported layouts

### One repository per post

```text
some-post-repo/
  index.html
  image.png
  ...
```

This publishes as:

```text
https://devslashvoid.dev/posts/some-post-repo/
```

The entire repository is mirrored, excluding `.git` and `.github`.

### Multiple posts in one repository

```text
some-repo/
  posts/
    first-post/
      index.html
      image.png
    second-post/
      index.html
      diagram.svg
```

These publish as:

```text
https://devslashvoid.dev/posts/first-post/
https://devslashvoid.dev/posts/second-post/
```

Only each post's own directory is mirrored for a multi-post repository, so its local assets remain with the post without copying the rest of the repository into the site.

Nested paths are also supported. For example, `posts/hardware/hr54/index.html` publishes as `/posts/hardware/hr54/`.

Post slugs must be unique across all discovered repositories. If two posts would publish to the same URL, the indexer warns and skips the later collision rather than overwriting an existing post.

## Build behavior

The index rebuilds on pushes to this repo, on manual dispatch, and every 15 minutes. On each build it:

1. scans public repositories owned by `voidnullvalue`;
2. finds root `index.html` files and `posts/**/index.html` files containing `devvoid:post`;
3. validates the required metadata;
4. sorts posts by `devvoid:published`;
5. mirrors each matching post into `_site/posts/<slug>/`;
6. rewrites the mirrored page's self/canonical URL to `devslashvoid.dev`;
7. builds the index, RSS feed, and `posts.json`;
8. deploys `_site` to GitHub Pages.

The mirror excludes `.git` and `.github`. If cloning a source repository fails, the indexer falls back to publishing that post's `index.html` so the build can still complete.

Private repositories are not currently discovered or mirrored.


## Per-page visitor counter

The generated site includes GoatCounter pageview tracking and a per-page visible counter.

By default the GoatCounter site code is `devslashvoid`, so the generated endpoint is:

```text
https://devslashvoid.goatcounter.com/count
```

Override it at build time with `DEVVOID_GOATCOUNTER_CODE` if the GoatCounter site uses a different code.

The visible footer uses the blog's pseudo-path rather than the public URL:

```text
1,847 poor bastards have wandered into /dev/void/
1,847 poor bastards have wandered into /dev/void/some-post
```

Counts remain keyed to the actual published page path, such as `/` or `/posts/some-post/`, so each page has its own count.

In GoatCounter, enable **Allow adding visitor counts on your website** or the visible counter endpoint will not return the count.
