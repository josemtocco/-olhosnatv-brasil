# Olhos na TV — M3U por categorias, somente canais ativos

Esta versão mantém os nomes e categorias dos canais e adiciona um teste de disponibilidade antes de gravar cada stream na M3U.

## Como funciona

1. Lê as categorias do Olhos na TV.
2. Encontra as páginas dos canais.
3. Extrai o nome do canal.
4. Extrai os streams públicos encontrados na página.
5. Faz uma requisição de teste para cada stream.
6. Para HLS (`.m3u8`), exige resposta HTTP 200/206 e a assinatura `#EXTM3U`.
7. Para DASH (`.mpd`), exige uma resposta que contenha `<MPD`/XML.
8. Para streams de mídia, exige resposta de dados.
9. Só os streams aprovados entram em `olhosnatv.m3u`.

## Importante

O teste é uma verificação de disponibilidade no momento da execução. Um canal pode estar ativo durante o teste e cair depois, ou pode bloquear determinados locais/agentes de usuário.

Também é possível que um stream responda HTTP 200 mas não seja reproduzível em todos os players. O teste reduz bastante os falsos positivos, mas não substitui a reprodução real.

## Implantação

No repositório atual `josemtocco/olhosnatv-categorias`, substitua:

- `gerar_m3u.py`
- `.github/workflows/atualizar.yml`

Mantenha `requirements.txt`.

Depois execute:

**Actions → Atualizar M3U - Olhos na TV (somente ativos) → Run workflow**

A rotina automática continua 4 vezes por dia.

## URL para SS IPTV

https://raw.githubusercontent.com/josemtocco/olhosnatv-categorias/main/olhosnatv.m3u
