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
SLEEP = 0.08

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
    "User-Agent": "Mozilla/5.0 (compatible; OlhosNaTV-M3U-Generator/3.0)"
})

def fetch(url):
    try:
        r = session.get(url, timeout=TIMEOUT)
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
    text = re.sub(r"\s*\|\s*.*$", "", text) if text.lower().startswith("olhos na tv") else text
    return text.strip(" -|")

def get_channel_name(soup):
    # 1. Estrutura padrão de post do Blogger.
    selectors = [
        "h3.post-title.entry-title",
        "h2.post-title.entry-title",
        "h1.post-title.entry-title",
        ".post-title.entry-title",
        ".post-title",
        "article h1",
        "article h2",
        "article h3",
    ]
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            name = normalize_name(tag.get_text(" ", strip=True))
            if name and name.lower() not in {"postagens", "categorias", "olhos na tv"}:
                return name

    # 2. Meta og:title costuma conter exatamente o título da postagem.
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        name = normalize_name(meta["content"])
        if name and name.lower() not in {"olhos na tv", "assistir tv online grátis - olhos na tv"}:
            return name

    # 3. Título HTML, removendo o nome do site.
    if soup.title:
        name = normalize_name(soup.title.get_text(" ", strip=True))
        if name and name.lower() not in {"olhos na tv", "assistir tv online grátis"}:
            return name

    # 4. Último recurso: procurar headings, mas ignorar elementos do layout.
    for tag in soup.find_all(["h1", "h2", "h3"]):
        classes = " ".join(tag.get("class", []))
        name = normalize_name(tag.get_text(" ", strip=True))
        if "post-title" in classes and name:
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
        href = a["href"]
        if "/search/label/" in href:
            text = clean(a.get_text(" ", strip=True))
            if text and text in KNOWN_LABELS and text not in labels:
                labels.append(text)
    return labels

def looks_like_post(url):
    return bool(re.search(r"/\d{4}/\d{2}/[^/]+\.html$", urlparse(url).path, re.I))

def main():
    cat_html, cat_final = fetch(CATEGORY_PAGE)
    category_urls = discover_category_urls(cat_html, cat_final)

    for label in KNOWN_LABELS:
        category_urls.setdefault(
            label,
            urljoin(BASE_URL, "search/label/" + label.replace(" ", "%20"))
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
                "próxima" in text or
                text == "next"
            ):
                if href not in visited:
                    queue.append(href)

        time.sleep(SLEEP)

    print(f"[INFO] {len(category_urls)} categorias.")
    print(f"[INFO] {len(post_urls)} páginas de canais.")

    channels = {}

    for i, post_url in enumerate(sorted(post_urls), 1):
        html, final_url = fetch(post_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        name = get_channel_name(soup)
        labels = get_labels(soup)
        streams = extract_streams(html, final_url)

        if not streams:
            continue

        if not labels:
            labels = ["Sem categoria"]

        for stream in streams:
            key = stream.strip()
            if not key:
                continue

            if key not in channels:
                channels[key] = {
                    "name": name,
                    "labels": list(labels),
                }
            else:
                channels[key]["labels"] = list(
                    dict.fromkeys(channels[key]["labels"] + labels)
                )
                # Se o primeiro título for genérico, aproveita o título atual.
                if channels[key]["name"] == "Canal sem nome" and name != "Canal sem nome":
                    channels[key]["name"] = name

        if i % 25 == 0:
            print(f"[INFO] Processados {i}/{len(post_urls)} posts")
        time.sleep(SLEEP)

    groups = defaultdict(list)
    for stream, item in channels.items():
        for label in item["labels"]:
            groups[label].append((item["name"], stream))

    ordered_labels = [x for x in KNOWN_LABELS if x in groups]
    ordered_labels += sorted(x for x in groups if x not in ordered_labels)

    lines = ["#EXTM3U"]

    for label in ordered_labels:
        for name, stream in sorted(groups[label], key=lambda x: x[0].lower()):
            safe_name = name.replace('"', "'")
            lines.append(
                f'#EXTINF:-1 group-title="{label}" '
                f'tvg-name="{safe_name}" '
                f'tvg-country="BR" tvg-language="Portuguese",{safe_name}'
            )
            lines.append(stream)

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] {len(channels)} streams únicos.")
    print(f"[OK] {len(ordered_labels)} categorias.")
    print(f"[OK] {OUTPUT}")

if __name__ == "__main__":
    main()
