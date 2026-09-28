#!/usr/bin/env python3

import base64
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

OWNER = os.environ.get("DEVVOID_OWNER", "voidnullvalue")
TEMPLATE = Path("index.template.html")
OUTPUT_DIR = Path("_site")
POSTS_JSON = OUTPUT_DIR / "posts.json"
MARKER = "<!-- DEVVOID_POSTS -->"
USER_AGENT = "Enter-dev-void-indexer/1"


class DevVoidMetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        data = {k.lower(): v for k, v in attrs if k and v is not None}
        name = data.get("name", "")
        if not name.startswith("devvoid:"):
            return
        self.meta[name.split(":", 1)[1]] = data.get("content", "").strip()


def request_text(url, token=None, timeout=15):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def list_public_repos(owner, token=None):
    repos = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{urllib.parse.quote(owner)}/repos"
            f"?type=owner&per_page=100&page={page}&sort=full_name"
        )
        payload = json.loads(request_text(url, token=token))
        if not payload:
            break
        repos.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return repos


def fetch_root_index(owner, repo_name, default_branch):
    repo = urllib.parse.quote(repo_name, safe="")
    branch = urllib.parse.quote(default_branch, safe="")
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/index.html"
    try:
        return request_text(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def parse_published(value):
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def discover_posts(owner, token=None):
    posts = []
    for repo in list_public_repos(owner, token=token):
        if repo.get("fork") or repo.get("archived"):
            continue
        name = repo["name"]
        branch = repo.get("default_branch") or "main"
        try:
            source = fetch_root_index(owner, name, branch)
        except Exception as exc:
            print(f"WARN: {name}: could not fetch index.html: {exc}", file=sys.stderr)
            continue
        if not source:
            continue

        parser = DevVoidMetaParser()
        try:
            parser.feed(source)
        except Exception as exc:
            print(f"WARN: {name}: could not parse HTML: {exc}", file=sys.stderr)
            continue

        meta = parser.meta
        if meta.get("post", "").lower() not in {"1", "true", "yes"}:
            continue

        missing = [key for key in ("title", "summary", "published") if not meta.get(key)]
        if missing:
            print(f"WARN: {name}: devvoid post missing {', '.join(missing)}", file=sys.stderr)
            continue

        try:
            published = parse_published(meta["published"])
        except ValueError:
            print(f"WARN: {name}: invalid devvoid:published={meta['published']!r}", file=sys.stderr)
            continue

        default_url = f"https://{owner}.github.io/{urllib.parse.quote(name)}/"
        tags = [tag.strip() for tag in meta.get("tags", "").split(",") if tag.strip()]
        posts.append(
            {
                "repo": name,
                "title": meta["title"],
                "summary": meta["summary"],
                "published": meta["published"],
                "published_dt": published,
                "url": meta.get("url") or default_url,
                "tags": tags,
            }
        )

    posts.sort(key=lambda post: post["published_dt"], reverse=True)
    return posts


def render_posts(posts):
    if not posts:
        return "      <p>No indexed posts yet.</p>"

    rendered = []
    for post in posts:
        date = post["published_dt"].date().isoformat()
        tags = "".join(
            f'<span class="tag">{html.escape(tag)}</span>' for tag in post["tags"]
        )
        tags_html = f'\n      <div class="post-tags">{tags}</div>' if tags else ""
        rendered.append(
            "    <article>\n"
            f'      <div class="post-date">{date}</div>\n'
            f'      <h3 class="post-title"><a href="{html.escape(post["url"], quote=True)}">'
            f'{html.escape(post["title"])}</a></h3>\n'
            f'      <p class="post-summary">{html.escape(post["summary"])}</p>'
            f"{tags_html}\n"
            "    </article>"
        )
    return "\n".join(rendered)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    posts = discover_posts(OWNER, token=token)

    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        raise SystemExit(f"template is missing {MARKER}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = template.replace(MARKER, render_posts(posts))
    (OUTPUT_DIR / "index.html").write_text(output, encoding="utf-8")
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    serializable = [
        {key: value for key, value in post.items() if key != "published_dt"}
        for post in posts
    ]
    POSTS_JSON.write_text(json.dumps(serializable, indent=2) + "\n", encoding="utf-8")

    print(f"Indexed {len(posts)} post(s):")
    for post in posts:
        print(f"  {post['published']}  {post['repo']}  {post['title']}")


if __name__ == "__main__":
    main()
