import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, unquote

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.olhosnatv.com.br/"
CATEGORY_PAGE = urljoin(BASE_URL, "p/blog-page.html")
OUTPUT = Path("olhosnatv.m3u")
MAX_PAGES = 1000
TIMEOUT = 25
STREAM_TIMEOUT = 12
SLEEP = 0.06
MAX_STREAM_TESTS = 500

KNOWN_LABELS = [
    "TVs Abertas", "Filmes", "Seriados", "Clássicos", "Desenhos",
    "Variedades", "Notícias", "Animes", "Novelas", "Esportes", "Músicas",
    "Faroestes", "Evangélicos", "Documentários", "Católicos",
    "Videoclipes Musical", "Kids", "Filmes Gospel", "Notícias do Mundo",
    "Pegadinhas", "Educativos", "Agronégocios", "Animais", "Governamentais",
    "Espíritas", "Culinárias", "Automóveis", "Televendas"
]

STREAM_PATTERNS = [
    r'https?://[^\'"\s<>\\]+\.m3u8(?:\?[^\'"\s<>\\]*)?',
    r'https?://[^\'"\s<>\\]+\.mpd(?:\?[^\'"\s<>\\]*)?',
    r'https?://[^\'"\s<>\\]+\.mp4(?:\?[^\'"\s<>\\]*)?',
    r'https?://[^\'"\s<>\\]+\.ts(?:\?[^\'"\s<>\\]*)?',
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept": "*/*",
})

def fetch(url, timeout=TIMEOUT):
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text, r.url
    except requests.RequestException as exc:
        print(f"[WARN] {url}: {exc}")
        return "", url

def canonical(url):
    return urldefrag(url)[0].rstrip("/")

def is_internal(url):
    return urlparse(url).netloc.lower() == urlparse(BASE_URL).netloc.lower()

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def normalize_name(text):
    text = clean(unquote(text))
    text = re.sub(r"\s*[-|]\s*Olhos na TV.*$", "", text, flags=re.I)
    return text.strip(" -|")

def get_channel_name(soup):
    selectors = [
        "h3.post-title.entry-title", "h2.post-title.entry-title",
        "h1.post-title.entry-title", ".post-title.entry-title",
        ".post-title", "article h1", "article h2", "article h3"
    ]
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            name = normalize_name(tag.get_text(" ", strip=True))
            if name and name.lower() not in {"postagens", "categorias", "olhos na tv"}:
                return name

    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        name = normalize_name(meta["content"])
        if name and "olhos na tv" not in name.lower():
            return name

    if soup.title:
        name = normalize_name(soup.title.get_text(" ", strip=True))
        if name and "olhos na tv" not in name.lower():
            return name

    return "Canal sem nome"

def extract_streams(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for pattern in STREAM_PATTERNS:
        found.extend(re.findall(pattern, html, flags=re.I))
    for tag in soup.find_all(["iframe", "video", "source"]):
        for attr in ("src", "data-src", "data-url", "data-video", "data-stream"):
            value = tag.get(attr)
            if value:
                found.append(urljoin(page_url, value))
    return list(dict.fromkeys(x.replace("\\/", "/") for x in found))

def extract_page_links(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for a in soup.find_all("a", href=True):
        href = canonical(urljoin(page_url, a["href"]))
        if is_internal(href):
            result.append(href)
    return list(dict.fromkeys(result))

def discover_category_urls(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    urls = {}
    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" ", strip=True))
        href = canonical(urljoin(page_url, a["href"]))
        if text in KNOWN_LABELS and "/search/label/" in href:
            urls[text] = href
    return urls

def get_labels(soup):
    labels = []
    for a in soup.find_all("a", href=True):
        if "/search/label/" in a["href"]:
            text = clean(a.get_text(" ", strip=True))
            if text in KNOWN_LABELS and text not in labels:
                labels.append(text)
    return labels

def looks_like_post(url):
    return bool(re.search(r"/\d{4}/\d{2}/[^/]+\.html$", urlparse(url).path, re.I))

def probe_stream(url):
    """Returns True only when the URL responds like a playable public stream."""
    try:
        r = session.get(
            url,
            timeout=STREAM_TIMEOUT,
            stream=True,
            allow_redirects=True,
            headers={
                "User-Agent": session.headers["User-Agent"],
                "Accept": "*/*",
                "Range": "bytes=0-4095",
            },
        )
        status = r.status_code
        ctype = (r.headers.get("content-type") or "").lower()
        first = b""
        try:
            first = next(r.iter_content(chunk_size=4096), b"")
        finally:
            r.close()

        if status not in (200, 206):
            return False

        path = urlparse(r.url).path.lower()

        # HLS: require an actual playlist signature, not merely HTTP 200.
        if ".m3u8" in path or "mpegurl" in ctype or "vnd.apple.mpegurl" in ctype:
            sample = first.decode("utf-8", errors="ignore")
            return "#EXTM3U" in sample

        # DASH: require an MPD/XML signature.
        if ".mpd" in path or "dash" in ctype:
            sample = first.decode("utf-8", errors="ignore").lower()
            return "<mpd" in sample or "<?xml" in sample

        # MPEG-TS / media files: a successful byte response is enough for this
        # lightweight check; a player still decides final compatibility.
        if any(x in ctype for x in ("video/", "audio/", "octet-stream", "mpeg")):
            return len(first) > 0

        # Some CDNs omit Content-Type. For known stream extensions, accept data.
        if any(path.endswith(ext) for ext in (".ts", ".mp4", ".m4v", ".aac")):
            return len(first) > 0

        return False
    except requests.RequestException:
        return False

def main():
    cat_html, cat_final = fetch(CATEGORY_PAGE)
    category_urls = discover_category_urls(cat_html, cat_final)

    for label in KNOWN_LABELS:
        category_urls.setdefault(
            label, urljoin(BASE_URL, "search/label/" + label.replace(" ", "%20"))
        )

    post_urls = set()
    queue = [canonical(u) for u in category_urls.values()]
    visited = set()

    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html, final_url = fetch(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        for link in extract_page_links(html, final_url):
            if looks_like_post(link):
                post_urls.add(link)

        for a in soup.find_all("a", href=True):
            text = clean(a.get_text(" ", strip=True)).lower()
            href = canonical(urljoin(final_url, a["href"]))
            if is_internal(href) and (
                "mais postagens" in text or
                "older posts" in text or
                "próxima" in text or text == "next"
            ) and href not in visited:
                queue.append(href)

        time.sleep(SLEEP)

    print(f"[INFO] Categorias: {len(category_urls)}")
    print(f"[INFO] Páginas de canais: {len(post_urls)}")

    channels = {}
    for i, post_url in enumerate(sorted(post_urls), 1):
        html, final_url = fetch(post_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        name = get_channel_name(soup)
        labels = get_labels(soup) or ["Sem categoria"]

        for stream in extract_streams(html, final_url):
            stream = stream.strip()
            if not stream:
                continue
            if stream not in channels:
                channels[stream] = {"name": name, "labels": labels[:]}
            else:
                channels[stream]["labels"] = list(
                    dict.fromkeys(channels[stream]["labels"] + labels)
                )
                if channels[stream]["name"] == "Canal sem nome" and name != "Canal sem nome":
                    channels[stream]["name"] = name

        if i % 25 == 0:
            print(f"[INFO] Posts processados: {i}/{len(post_urls)}")
        time.sleep(SLEEP)

    print(f"[INFO] Streams encontrados antes do teste: {len(channels)}")

    # Testa cada stream uma vez. Canais inativos são descartados.
    active = {}
    tested = 0
    for stream, item in channels.items():
        if tested >= MAX_STREAM_TESTS:
            print("[WARN] Limite de testes atingido; streams restantes não serão incluídos.")
            break

        tested += 1
        ok = probe_stream(stream)
        print(f"[TESTE] {'ATIVO' if ok else 'INATIVO'} - {item['name']} - {stream}")
        if ok:
            active[stream] = item

    print(f"[RESULTADO] Ativos: {len(active)} / Testados: {tested}")

    groups = defaultdict(list)
    for stream, item in active.items():
        for label in item["labels"]:
            groups[label].append((item["name"], stream))

    ordered_labels = [x for x in KNOWN_LABELS if x in groups]
    ordered_labels += sorted(x for x in groups if x not in ordered_labels)

    lines = ["#EXTM3U"]
    for label in ordered_labels:
        # Evita duplicar o mesmo stream dentro da mesma categoria.
        seen_group = set()
        for name, stream in sorted(groups[label], key=lambda x: x[0].lower()):
            if stream in seen_group:
                continue
            seen_group.add(stream)
            safe_name = name.replace('"', "'")
            lines.append(
                f'#EXTINF:-1 group-title="{label}" tvg-name="{safe_name}" '
                f'tvg-country="BR" tvg-language="Portuguese",{safe_name}'
            )
            lines.append(stream)

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Lista gerada: {OUTPUT}")
    print(f"[OK] Categorias com canais ativos: {len(ordered_labels)}")

if __name__ == "__main__":
    main()
