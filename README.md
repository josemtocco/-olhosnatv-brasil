# Olhos na TV — M3U com nomes e categorias

Esta versão corrige a identificação dos canais e grava explicitamente o nome em `tvg-name` e também no nome final do `#EXTINF`.

Exemplo:

#EXTINF:-1 group-title="TVs Abertas" tvg-name="SBT" tvg-country="BR" tvg-language="Portuguese",SBT
https://...

O nome é obtido prioritariamente do título real da postagem do canal no Olhos na TV, evitando usar o título geral do site.

## Implantação

Substitua no seu repositório atual:

- `gerar_m3u.py`
- `.github/workflows/atualizar.yml`

Mantenha `requirements.txt`.

Depois vá em:

**Actions → Atualizar M3U - Olhos na TV → Run workflow**

## URL do SS IPTV

Se o repositório continuar sendo:

`josemtocco/olhosnatv-categorias`

a URL continua:

https://raw.githubusercontent.com/josemtocco/olhosnatv-categorias/main/olhosnatv.m3u
