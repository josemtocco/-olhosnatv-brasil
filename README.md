# Olhos na TV — Brasil Português

Gerador automático de uma lista M3U baseada nas páginas públicas do site Olhos na TV.

Fonte:
https://www.olhosnatv.com.br/

## Arquivos

- `gerar_m3u.py` — coleta páginas e procura URLs públicas de streams.
- `olhosnatv-brasil.m3u` — lista final.
- `requirements.txt` — dependências.
- `.github/workflows/atualizar.yml` — atualização automática.

## Como colocar no GitHub

Crie um repositório chamado, por exemplo:

`olhosnatv-brasil`

No usuário:

`josemtocco`

Envie estes arquivos mantendo exatamente a estrutura de pastas.

Depois abra:

**Actions → Atualizar M3U - Olhos na TV Brasil → Run workflow**

O workflow também executará automaticamente quatro vezes por dia.

## URL para o SS IPTV

Depois que o arquivo existir na branch `main`, a URL será:

https://raw.githubusercontent.com/josemtocco/olhosnatv-brasil/main/olhosnatv-brasil.m3u

Se você escolher outro nome para o repositório, altere somente essa parte da URL.

## Importante

O site pode mudar a estrutura HTML, o player ou os endereços dos streams. O gerador procura URLs públicas diretamente presentes nas páginas, incluindo formatos como M3U8 e MPEG-DASH. Players que escondem o endereço atrás de JavaScript, tokens temporários ou outros mecanismos podem não produzir uma URL M3U direta.

A lista não tenta contornar autenticação, DRM ou restrições de acesso. Use apenas streams públicos e cuja redistribuição seja autorizada.
