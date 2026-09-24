# Olhos na TV — M3U por categorias

Projeto para gerar automaticamente uma playlist M3U a partir das páginas públicas do Olhos na TV.

Fonte:
https://www.olhosnatv.com.br/

## O que esta versão faz

A lista não fica limitada a "TVs Abertas".

O gerador lê as categorias do próprio site e associa cada canal às categorias publicadas em sua página.

Categorias atualmente apresentadas pelo site incluem:

- TVs Abertas
- Filmes
- Seriados
- Clássicos
- Desenhos
- Variedades
- Notícias
- Animes
- Novelas
- Esportes
- Músicas
- Faroestes
- Evangélicos
- Documentários
- Católicos
- Videoclipes Musical
- Kids
- Filmes Gospel
- Notícias do Mundo
- Pegadinhas
- Educativos
- Agronégocios
- Animais
- Governamentais
- Espíritas
- Culinárias
- Automóveis
- Televendas

Se o site adicionar ou remover categorias, o gerador tenta acompanhar os rótulos publicados.

## Organização da M3U

Cada entrada recebe `group-title` conforme a categoria do site:

```text
#EXTM3U

#EXTINF:-1 group-title="TVs Abertas" tvg-country="BR" tvg-language="Portuguese",SBT
https://...

#EXTINF:-1 group-title="TVs Abertas" tvg-country="BR" tvg-language="Portuguese",BAND
https://...

#EXTINF:-1 group-title="Filmes" tvg-country="BR" tvg-language="Portuguese",...
https://...
```

Um mesmo canal pode aparecer em mais de uma categoria quando o próprio site publica mais de um rótulo para ele.

## GitHub

Repositório sugerido:

`josemtocco/olhosnatv-categorias`

Depois de enviar os arquivos, execute:

**Actions → Atualizar M3U - Olhos na TV → Run workflow**

O workflow também roda automaticamente quatro vezes por dia.

## URL para o SS IPTV

Se o repositório for `josemtocco/olhosnatv-categorias` e a branch for `main`:

https://raw.githubusercontent.com/josemtocco/olhosnatv-categorias/main/olhosnatv.m3u

Essa é a URL para cadastrar como playlist no SS IPTV.

## Observações

- O gerador trabalha com páginas e streams públicos encontrados no site.
- Não tenta contornar login, DRM ou proteção de acesso.
- Um player que esconda o stream atrás de JavaScript, token temporário ou DRM pode não fornecer uma URL M3U direta.
- O conteúdo da playlist depende do que estiver publicado e acessível no Olhos na TV no momento da execução.
