import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.olhosnatv.com.br/"
OUTPUT = Path("olhosnatv-brasil.m3u")
MAX_PAGES = 250
TIMEOUT = 25

# O filtro começa pela categoria de TVs abertas e usa termos de exclusão
# para evitar filmes, séries, desenhos etc.
CATEGORY_URLS = [
    "https://www.olhosnatv.com.br/p/blog-page.html",
]

EXCLUDE = re.compile(
    r"(filme|films|cinema|série|series|seriado|desenho|cartoon|anime|"
    r"kids|music|música|videoclipe|faroeste|gospel|cat[oó]lico|esp[ií]rita|"
    r"document[aá]rio|not[ií]cia do mundo|pegadinha|autom[oó]veis|culin[aá]ria|"
    r"televenda|agron[oô]gocio|animal|variedades|novela|esporte)",
    re.I,
)

BRAZIL_HINTS = re.compile(
    r"(sbt|band|record|rede brasil|tv brasil|cultura|gazeta|globo|"
    r"amazonas|acre|alagoas|amapa|bahia|cear[aá]|esp[ií]rito santo|"
    r"goi[aá]s|maranh[aã]o|mato grosso|minas gerais|par[aá]|para[ií]ba|"
    r"paran[aá]|pernambuco|piau[ií]|rio grande|rond[oô]nia|roraima|"
    r"santa catarina|s[aã]o paulo|sergipe|tocantins|aracati|juara|"
    r"meio norte|tela brasil|istv|sonata|awtv|amplitude)",
    re.I,
)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; OlhosNaTV-M3U-Generator/1.0)"
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

def internal(url):
    return urlparse(url).netloc == urlparse(BASE_URL).netloc

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def page_title(soup):
    for tag in soup.find_all(["h1", "h2", "h3"], limit=5):
        name = clean(tag.get_text(" ", strip=True))
        if name and len(name) <= 100:
            return name
    if soup.title:
        return clean(re.sub(r"\s*-\s*Olhos na TV.*$", "", soup.title.get_text(" ", strip=True), flags=re.I))
    return "Canal Brasil"

def extract_candidates(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    values = []

    # URLs diretas normalmente encontradas no HTML/JS.
    patterns = [
        r'https?://[^\'"\s<>\\]+\.m3u8(?:\?[^\'"\s<>\\]*)?',
        r'https?://[^\'"\s<>\\]+\.mpd(?:\?[^\'"\s<>\\]*)?',
        r'https?://[^\'"\s<>\\]+\.mp4(?:\?[^\'"\s<>\\]*)?',
        r'https?://[^\'"\s<>\\]+\.ts(?:\?[^\'"\s<>\\]*)?',
    ]
    for pattern in patterns:
        values.extend(re.findall(pattern, html, flags=re.I))

    # Iframes e elementos de vídeo.
    for tag in soup.find_all(["iframe", "video", "source"]):
        for attr in ("src", "data-src", "data-url", "data-video", "data-stream"):
            src = tag.get(attr)
            if src:
                values.append(urljoin(page_url, src))

    return list(dict.fromkeys(v.replace("\\/", "/") for v in values))

def links_from_page(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = canonical(urljoin(page_url, a["href"]))
        if internal(href) and href.startswith(BASE_URL.rstrip("/")):
            links.append(href)
    return list(dict.fromkeys(links))

def looks_like_channel(name, source_url):
    text = f"{name} {source_url}"
    return not EXCLUDE.search(text) and bool(BRAZIL_HINTS.search(text))

def main():
    queue = [canonical(u) for u in CATEGORY_URLS] + [canonical(BASE_URL)]
    visited = set()
    results = {}

    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html, final_url = fetch(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        name = page_title(soup)

        # Só considera páginas claramente relacionadas a canais brasileiros.
        if looks_like_channel(name, final_url):
            for stream in extract_candidates(html, final_url):
                # O stream pode estar hospedado fora do site; isso é esperado.
                key = stream.split("?")[0]
                results.setdefault(key, {
                    "name": name,
                    "url": stream,
                    "source": final_url,
                })

        for link in links_from_page(html, final_url):
            if link not in visited and link not in queue:
                # Prioriza páginas que parecem ser posts de canais.
                if looks_like_channel(link, link):
                    queue.insert(0, link)
                else:
                    queue.append(link)

        time.sleep(0.10)

    lines = ["#EXTM3U"]
    for item in sorted(results.values(), key=lambda x: x["name"].lower()):
        name = item["name"].replace('"', "'")
        lines.append(f'#EXTINF:-1 group-title="Brasil" tvg-country="BR" tvg-language="Portuguese",{name}')
        lines.append(item["url"])

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Gerados {len(results)} streams em {OUTPUT}")

if __name__ == "__main__":
    main()
