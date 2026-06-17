from flask import Flask, request, render_template_string, jsonify
import requests, re

app = Flask(__name__)

API = "https://danbooru.donmai.us/posts.json"
HEADERS = {"User-Agent": "PinterestBooru/1.0"}

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Danbooru Pinterest Browser</title>
<link rel="icon" href="https://danbooru.donmai.us/favicon.ico">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
*, *::before, *::after { box-sizing: border-box; }

body {
    background: #0e0e0e;
    color: #ddd;
    font-family: system-ui, sans-serif;
    margin: 0;
}

header {
    position: sticky;
    top: 0;
    z-index: 10;
    background: #161616;
    border-bottom: 1px solid #2a2a2a;
    padding: 10px 14px;
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
}

input {
    background: #222;
    border: 1px solid #333;
    color: #eee;
    padding: 7px 10px;
    border-radius: 4px;
    font-size: 13px;
    outline: none;
    width: 280px;
}

input:focus { border-color: #555; }

button {
    background: #2a2a2a;
    border: 1px solid #444;
    color: #eee;
    padding: 7px 16px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
}

button:hover { background: #333; }

#restricted-note {
    font-size: 12px;
    color: #666;
    margin-left: 4px;
}

.masonry {
    columns: 200px;
    column-gap: 8px;
    padding: 10px;
}

.item {
    break-inside: avoid;
    margin-bottom: 8px;
    background: #1a1a1a;
    border-radius: 5px;
    overflow: hidden;
    display: block;
    cursor: pointer;
}

.item img, .item video {
    width: 100%;
    display: block;
}

#suggestions {
    position: fixed;
    background: #1e1e1e;
    border: 1px solid #383838;
    border-radius: 4px;
    display: none;
    z-index: 9999;
    box-shadow: 0 4px 12px rgba(0,0,0,.5);
    overflow: hidden;
}

.sugg-item {
    padding: 7px 10px;
    cursor: pointer;
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.sugg-item:hover { background: #2a2a2a; }

#sentinel { height: 1px; }
</style>
</head>
<body>

<header>
    <input id="tags"      placeholder="tags (comma or space separated)">
    <input id="blacklist" placeholder="blacklist tags"
           value="rating:explicit,rating:questionable,rating:sensitive">
    <button onclick="startSearch()">Search</button>
    <span id="restricted-note"></span>
</header>

<div id="suggestions"></div>
<div class="masonry" id="grid"></div>
<div id="sentinel"></div>

<script>
let page = null, loading = false, done = false;
let activeInput  = null;
let suggestTimer = null;
let totalRestricted = 0;

const tagsEl  = document.getElementById("tags");
const blackEl = document.getElementById("blacklist");
const box     = document.getElementById("suggestions");
const note    = document.getElementById("restricted-note");

tagsEl.addEventListener("focus",  () => activeInput = tagsEl);
blackEl.addEventListener("focus", () => activeInput = blackEl);

tagsEl.addEventListener("keydown",  e => { if (e.key === "Enter") startSearch(); });
blackEl.addEventListener("keydown", e => { if (e.key === "Enter") startSearch(); });

tagsEl.addEventListener("input",  e => debouncedSuggest(e.target));
blackEl.addEventListener("input", e => debouncedSuggest(e.target));

function debouncedSuggest(input) {
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(() => suggest(input), 180);
}

function startSearch() {
    page = null; done = false;
    totalRestricted = 0;
    note.textContent = "";
    document.getElementById("grid").innerHTML = "";
    box.style.display = "none";
    loadMore();
}

async function loadMore() {
    const tags = tagsEl.value.trim();
    if (loading || done || !tags) return;
    loading = true;

    let url = `/api?tags=${encodeURIComponent(tags)}&blacklist=${encodeURIComponent(blackEl.value)}`;
    if (page) url += `&page=${page}`;

    const res  = await fetch(url);
    const { results, restricted } = await res.json();

    if (!results.length) { done = true; loading = false; return; }

    totalRestricted += restricted;
    if (totalRestricted > 0)
        note.textContent = `${totalRestricted} hidden (login required)`;

    page = results[results.length - 1].id;
    const grid = document.getElementById("grid");

    for (const p of results) {
        if (!p.preview) continue;

        const a = document.createElement("a");
        a.className         = "item";
        a.href              = p.url;
        a.target            = "_blank";
        a.style.aspectRatio = p.w / p.h;

        const isVideo = p.preview.endsWith(".mp4") || p.preview.endsWith(".webm");

        if (isVideo) {
            const vid       = document.createElement("video");
            vid.src         = p.preview;
            vid.muted       = true;
            vid.loop        = true;
            vid.playsInline = true;
            vid.addEventListener("mouseenter", () => vid.play());
            vid.addEventListener("mouseleave", () => { vid.pause(); vid.currentTime = 0; });
            a.appendChild(vid);
        } else {
            const img   = document.createElement("img");
            img.src     = p.preview;
            img.loading = "lazy";
            a.appendChild(img);
        }

        grid.appendChild(a);
    }

    loading = false;

    if (document.body.scrollHeight <= window.innerHeight) loadMore();
}

new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) loadMore();
}, { rootMargin: "600px" }).observe(document.getElementById("sentinel"));

async function suggest(input) {
    const raw  = input.value;
    const last = raw.split(/[\s,]+/).pop().trim();

    if (!last || last.startsWith("rating:")) {
        box.style.display = "none";
        return;
    }

    const res  = await fetch(`/tags?q=${encodeURIComponent(last)}`);
    const data = await res.json();

    if (!data.length) { box.style.display = "none"; return; }

    const rect = input.getBoundingClientRect();
    box.style.top   = (rect.bottom + 4) + "px";
    box.style.left  = rect.left + "px";
    box.style.width = rect.width + "px";
    box.style.display = "block";
    box.innerHTML = "";

    for (const t of data) {
        const div = document.createElement("div");
        div.className   = "sugg-item";
        div.textContent = t;
        div.addEventListener("mousedown", e => {
            e.preventDefault();
            const parts = raw.split(/(\s+|,\s*)/).filter(Boolean);
            if (parts.length) parts[parts.length - 1] = t;
            else parts.push(t);
            input.value = parts.join(" ") + " ";
            box.style.display = "none";
            input.focus();
        });
        box.appendChild(div);
    }
}

document.addEventListener("click", e => {
    if (!box.contains(e.target)) box.style.display = "none";
});
</script>

</body>
</html>
"""

def parse_tags(text):
    return [t for t in re.split(r"[\s,]+", text.strip()) if t]


RATING_MAP = {"explicit": "e", "questionable": "q", "sensitive": "s", "general": "g"}


def fetch(raw_tags, raw_blacklist, page=None):
    tags      = parse_tags(raw_tags)
    blacklist = set(parse_tags(raw_blacklist))

    if not tags:
        return {"results": [], "restricted": 0}

    rating_tags = [t for t in tags if t.startswith("rating:")]
    normal_tags = [t for t in tags if not t.startswith("rating:")]

    api_tags = normal_tags[:2] + rating_tags
    extra    = set(normal_tags[2:])

    blacklist_ratings = {RATING_MAP[t[7:]] for t in blacklist
                         if t.startswith("rating:") and t[7:] in RATING_MAP}
    blacklist_tags    = {t for t in blacklist if not t.startswith("rating:")}

    params = {"tags": " ".join(api_tags), "limit": 100}
    if page:
        params["page"] = f"b{page}"

    r = requests.get(
        API,
        params=params,
        headers=HEADERS,
        timeout=15
    )

    if r.status_code != 200:
        return {"results": [], "restricted": 0}

    results    = []
    restricted = 0

    for post in r.json():
        if not post.get("file_url"):
            restricted += 1
            continue

        if post.get("rating") in blacklist_ratings:
            continue

        post_tags = set(post.get("tag_string", "").split())
        if blacklist_tags and post_tags & blacklist_tags:
            continue
        if extra and not extra.issubset(post_tags):
            continue

        file_url = post.get("file_url")
        ext      = file_url.rsplit(".", 1)[-1].lower()
        if ext in ("mp4", "webm", "zip"):
            preview = post.get("preview_file_url") or file_url
        else:
            preview = post.get("large_file_url") or file_url

        if not preview:
            continue

        results.append({
            "id":      post["id"],
            "url":     file_url,
            "preview": preview,
            "w":       post.get("image_width")  or 1,
            "h":       post.get("image_height") or 1,
        })

    return {"results": results, "restricted": restricted}


@app.route("/tags")
def tags_route():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    r = requests.get(
        "https://danbooru.donmai.us/tags.json",
        params={
            "search[name_matches]": f"{q}*",
            "search[order]":        "count",
            "limit":                8,
        },
        headers=HEADERS,
        timeout=10,
    )
    if r.status_code != 200:
        return jsonify([])

    return jsonify([t["name"] for t in r.json()])


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/api")
def api():
    return jsonify(fetch(
        request.args.get("tags", ""),
        request.args.get("blacklist", ""),
        request.args.get("page"),
    ))


if __name__ == "__main__":
    app.run(debug=True, port=5000)