# dorker

Agregador de busca multi-engine com anti-detecção, para automatizar "dorks" (queries com operadores como `site:`, `filetype:`, `inurl:`) através de várias fontes ao mesmo tempo.

## Instalação

```bash
uv sync
```

## Uso

```bash
uv run dorker "site:gov.br senha"
uv run dorker "intitle:index.of mp3" --engine duckduckgo --pages 3
uv run dorker "filetype:pdf confidential" --engine all --output results.json --format json
uv run dorker "inurl:admin login" --engine searx --delay 5 12 --timeout 20
```

Engines disponíveis: `duckduckgo`, `mojeek`, `google`, `searx`, ou `all` (roda todos).

Veja `uv run dorker --help` para a lista completa de opções (delay entre requisições, timeout, retries, rotação de identidade, formato de saída).
