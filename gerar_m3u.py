import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.olhosnatv.com.br/"
CATEGORY_PAGE = urljoin(BASE_URL, "p/blog-page.html")
OUTPUT = Path("olhosnatv.m3u")
MAX_PAGES = 800
TIMEOUT = 25
SLEEP = 0.08

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; OlhosNaTV-M3U-Generator/2.0)"
})

# As categorias são obtidas da própria página CATEGORIAS do site.
# O script não usa uma lista fixa de canais: ele acompanha os posts e rótulos
# publicados pelo site.
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

def extract_streams(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    found = []

    # URLs explícitas no HTML/JavaScript.
    for pattern in STREAM_PATTERNS:
        found.extend(re.findall(pattern, html, flags=re.I))

    # Players/iframes/source tags.
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

def get_title(soup):
    # Em posts do Blogger, o título costuma estar em h1/h2/h3.
    for tag in soup.find_all(["h1", "h2", "h3"], limit=10):
        text = clean(tag.get_text(" ", strip=True))
        if text and text.lower() not in {"postagens", "categorias"}:
            if len(text) <= 150:
                return text
    if soup.title:
        return clean(re.sub(r"\s*-\s*Olhos na TV.*$", "", soup.title.get_text(" ", strip=True), flags=re.I))
    return "Canal"

def get_labels(soup):
    labels = []

    # Links /search/label/<categoria>
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/search/label/" in href:
            text = clean(a.get_text(" ", strip=True))
            if text and text not in labels and text in KNOWN_LABELS:
                labels.append(text)

    # Também aceita labels conhecidas em texto de posts.
    text = clean(soup.get_text(" ", strip=True))
    for label in KNOWN_LABELS:
        if label.lower() in text.lower() and label not in labels:
            # Só adiciona quando há evidência de que é um rótulo.
            if re.search(rf"\b{re.escape(label)}\b", text, flags=re.I):
                labels.append(label)

    return labels

def discover_category_urls(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    urls = {}
    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" ", strip=True))
        href = canonical(urljoin(page_url, a["href"]))
        if text in KNOWN_LABELS and "/search/label/" in href:
            urls[text] = href
    return urls

def looks_like_post(url):
    # URLs típicas de posts do Blogger: /YYYY/MM/nome.html
    return bool(re.search(r"/\d{4}/\d{2}/[^/]+\.html$", urlparse(url).path, re.I))

def main():
    # 1) Descobre as categorias diretamente da página do site.
    cat_html, cat_final = fetch(CATEGORY_PAGE)
    category_urls = discover_category_urls(cat_html, cat_final)

    # Garante as categorias conhecidas mesmo que alguma não esteja no HTML
    # naquele momento.
    for label in KNOWN_LABELS:
        category_urls.setdefault(
            label,
            urljoin(BASE_URL, "search/label/" + label.replace(" ", "%20"))
        )

    # 2) Varre todas as páginas de cada categoria, seguindo "Mais postagens".
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

        # Todos os links de posts encontrados nessa categoria.
        for link in extract_page_links(html, final_url):
            if looks_like_post(link):
                post_urls.add(link)

        # Segue paginação da categoria.
        for a in soup.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).lower()
            href = canonical(urljoin(final_url, a["href"]))
            if is_internal(href) and (
                "mais postagens" in label
                or "older posts" in label
                or "próxima" in label
                or "next" == label
            ):
                if href not in visited:
                    queue.append(href)

        time.sleep(SLEEP)

    print(f"[INFO] Categorias encontradas: {len(category_urls)}")
    print(f"[INFO] Páginas de canais encontradas: {len(post_urls)}")

    # 3) Abre cada post e coleta título, categorias e streams.
    channels = {}
    for i, post_url in enumerate(sorted(post_urls), 1):
        html, final_url = fetch(post_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        title = get_title(soup)
        labels = get_labels(soup)
        streams = extract_streams(html, final_url)

        if not streams:
            continue

        # Se não identificou rótulo, coloca em uma categoria técnica para
        # não perder o canal. Em condições normais, os posts do site têm labels.
        if not labels:
            labels = ["Sem categoria"]

        for stream in streams:
            stream_key = stream.strip()
            if not stream_key:
                continue

            if stream_key not in channels:
                channels[stream_key] = {
                    "name": title,
                    "labels": labels[:],
                    "source": final_url,
                }
            else:
                # Um mesmo canal pode aparecer em várias categorias.
                channels[stream_key]["labels"] = list(
                    dict.fromkeys(channels[stream_key]["labels"] + labels)
                )

        if i % 25 == 0:
            print(f"[INFO] Processados {i}/{len(post_urls)} posts")
        time.sleep(SLEEP)

    # 4) Gera M3U agrupando exatamente pelas categorias/labels do site.
    groups = defaultdict(list)
    for item in channels.values():
        for label in item["labels"]:
            groups[label].append(item)

    # Ordem das categorias igual à página CATEGORIAS do site.
    ordered_labels = [x for x in KNOWN_LABELS if x in groups]
    ordered_labels += sorted(x for x in groups if x not in ordered_labels)

    lines = ["#EXTM3U"]

    for label in ordered_labels:
        for item in sorted(groups[label], key=lambda x: x["name"].lower()):
            name = item["name"].replace('"', "'")
            lines.append(
                f'#EXTINF:-1 group-title="{label}" '
                f'tvg-country="BR" tvg-language="Portuguese",{name}'
            )
            lines.append(item["source"] if False else next(
                s for s, v in channels.items() if v is item
            ))

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[OK] {len(channels)} streams únicos.")
    print(f"[OK] {len(ordered_labels)} categorias com canais.")
    print(f"[OK] Arquivo: {OUTPUT}")

if __name__ == "__main__":
    main()
