#!/usr/bin/env python3

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path

OWNER = os.environ.get("DEVVOID_OWNER", "voidnullvalue")
TEMPLATE = Path("index.template.html")
OUTPUT_DIR = Path("_site")
POSTS_JSON = OUTPUT_DIR / "posts.json"
FEED_XML = OUTPUT_DIR / "feed.xml"
MARKER = "<!-- DEVVOID_POSTS -->"
USER_AGENT = "Enter-dev-void-indexer/2"
SITE_URL = "https://devslashvoid.dev/"
FEED_URL = SITE_URL + "feed.xml"
ATOM_NS = "http://www.w3.org/2005/Atom"
OLD_INDEX_URLS = (
    "https://voidnullvalue.github.io/Enter-dev-void/",
    "https://voidnullvalue.github.io/Enter-dev-void",
)


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


def rss_datetime(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return format_datetime(value)


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

        source_url = (
            meta.get("url")
            or f"https://{owner}.github.io/{urllib.parse.quote(name)}/"
        )
        local_url = SITE_URL + "posts/" + urllib.parse.quote(name) + "/"
        tags = [tag.strip() for tag in meta.get("tags", "").split(",") if tag.strip()]

        posts.append(
            {
                "repo": name,
                "branch": branch,
                "title": meta["title"],
                "summary": meta["summary"],
                "published": meta["published"],
                "published_dt": published,
                "url": local_url,
                "source_url": source_url,
                "tags": tags,
                "source_html": source,
            }
        )

    posts.sort(key=lambda post: post["published_dt"], reverse=True)
    return posts


def rewrite_mirrored_index(path, post):
    source = path.read_text(encoding="utf-8", errors="replace")
    local_url = post["url"]

    # Keep old post repos independently publishable, but make the mirrored copy
    # identify itself as the devslashvoid.dev version.
    source = re.sub(
        r'(<meta\s+name=["\']devvoid:url["\']\s+content=["\'])[^"\']*(["\'])',
        lambda match: match.group(1) + local_url + match.group(2),
        source,
        flags=re.IGNORECASE,
    )

    # Rewrite explicit self-links and old blog-index links in mirrored copies.
    source_url = post.get("source_url")
    if source_url:
        source = source.replace(source_url, local_url)

    for old_url in OLD_INDEX_URLS:
        source = source.replace(old_url, SITE_URL)

    # Give search engines a stable canonical URL on the custom domain.
    if re.search(r'<link\b[^>]*\brel=["\']canonical["\']', source, flags=re.IGNORECASE):
        source = re.sub(
            r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>',
            f'<link rel="canonical" href="{html.escape(local_url, quote=True)}">',
            source,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        canonical = f'  <link rel="canonical" href="{html.escape(local_url, quote=True)}">\n'
        source = re.sub(r"</head>", canonical + "</head>", source, count=1, flags=re.IGNORECASE)

    path.write_text(source, encoding="utf-8")


def mirror_post(post):
    destination = OUTPUT_DIR / "posts" / post["repo"]
    destination.parent.mkdir(parents=True, exist_ok=True)

    repo_url = f"https://github.com/{OWNER}/{post['repo']}.git"

    try:
        with tempfile.TemporaryDirectory(prefix="devvoid-post-") as tmpdir:
            checkout = Path(tmpdir) / "repo"
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--depth",
                    "1",
                    "--branch",
                    post["branch"],
                    repo_url,
                    str(checkout),
                ],
                check=True,
                timeout=60,
            )

            shutil.copytree(
                checkout,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", ".github"),
            )
    except Exception as exc:
        print(
            f"WARN: {post['repo']}: full mirror failed ({exc}); copying index.html only",
            file=sys.stderr,
        )
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "index.html").write_text(post["source_html"], encoding="utf-8")

    index = destination / "index.html"
    if not index.exists():
        raise RuntimeError(f"{post['repo']}: mirrored repository has no index.html")

    rewrite_mirrored_index(index, post)


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


def build_rss(posts):
    ET.register_namespace("atom", ATOM_NS)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Enter /dev/void/"
    ET.SubElement(channel, "link").text = SITE_URL
    ET.SubElement(channel, "description").text = (
        "Old hardware, embedded Linux, reverse engineering, local services, "
        "and other things I decided to screw with."
    )
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "generator").text = "Enter /dev/void/ metadata indexer"
    ET.SubElement(channel, "ttl").text = "60"
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {
            "href": FEED_URL,
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    if posts:
        ET.SubElement(channel, "lastBuildDate").text = rss_datetime(posts[0]["published_dt"])

    for post in posts:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = post["title"]
        ET.SubElement(item, "link").text = post["url"]
        guid = ET.SubElement(item, "guid", {"isPermaLink": "true"})
        guid.text = post["url"]
        ET.SubElement(item, "pubDate").text = rss_datetime(post["published_dt"])
        ET.SubElement(item, "description").text = post["summary"]
        for tag in post["tags"]:
            ET.SubElement(item, "category").text = tag

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    posts = discover_posts(OWNER, token=token)

    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        raise SystemExit(f"template is missing {MARKER}")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for post in posts:
        try:
            mirror_post(post)
        except Exception as exc:
            print(f"WARN: {post['repo']}: mirror failed: {exc}", file=sys.stderr)

    output = template.replace(MARKER, render_posts(posts))
    (OUTPUT_DIR / "index.html").write_text(output, encoding="utf-8")
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    FEED_XML.write_bytes(build_rss(posts))

    serializable = [
        {
            key: value
            for key, value in post.items()
            if key not in {"published_dt", "source_html"}
        }
        for post in posts
    ]
    POSTS_JSON.write_text(json.dumps(serializable, indent=2) + "\n", encoding="utf-8")

    print(f"Indexed {len(posts)} post(s):")
    for post in posts:
        print(f"  {post['published']}  {post['repo']}  {post['title']}")
        print(f"    local:  {post['url']}")
        print(f"    source: {post['source_url']}")
    print(f"RSS: {FEED_URL}")


if __name__ == "__main__":
    main()
