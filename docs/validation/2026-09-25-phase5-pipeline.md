# Validação da Fase 5 — pipeline, lote, retomada e CLI

Data: 2026-09-25. Ambiente executado: Windows, Python 3.12, WeasyPrint v70 local. O diretório de trabalho não é um repositório Git; esta validação cobre arquivos locais, sem commit ou publicação.

## Implementação

- `convert_one` detecta proteção/formato, extrai em diretório temporário no volume de saída, prepara capítulos, renderiza e valida. Publica sem sobrescrever por link de arquivo somente após validação `valid`. O diretório temporário é removido ao final ou em falha.
- `review_required` fica em `review/`, fora da raiz de PDFs aprovados. Um arquivo já existente no nome calculado impede a publicação.
- Nomes incluem título sanitizado, prefixo do SHA-256 de entrada e impressão digital das opções. Dois livros com o mesmo título e conteúdo diferente geram arquivos separados.
- `convert_batch` grava manifesto JSON após cada arquivo com substituição atômica, hash de entrada, opções, versão, status, caminho relativo e hash de saída. Registros anteriores são preservados ao alternar estilo ou conteúdo; a retomada exige coincidência de todos esses elementos. Saída alterada não é reutilizada nem sobrescrita.
- CLI: `diagnosticar`, `converter`, `converter-pasta`, com `--saida`; os comandos de conversão aceitam `--json` ou texto. O lote continua após item inválido.

## Evidência executada

Os testes foram escritos antes da implementação e inicialmente falharam por ausência de pipeline/lote/comandos. A revisão acrescentou quatro regressões para alternância de opções, lote vazio, progresso por item e link simbólico em `review/`. A suíte completa passou ao final com **63 testes aprovados** (`python -m pytest -q`, `--basetemp=.tmp/pytest-phase5-final2`); os **15 testes da Fase 5** também passaram isoladamente (`--basetemp=.tmp/pytest-phase5-regression`).

Lote real local em `.tmp/phase3-samples` com *Dom Casmurro* de domínio público, sem proteção:

| Entrada | Resultado | PDF | Páginas |
| --- | --- | --- | ---: |
| EPUB | `converted` | raiz da saída | 163 |
| MOBI antigo | `converted` | raiz da saída | 157 |
| KF8/MOBI | `review_required` | `review/` | 162 |

O KF8 apresenta aviso de capa referenciada e ausente, já observado na extração da Fase 3. A segunda execução retomou **3 de 3** itens sem renderizar novamente. A saída de ensaio fica em `.tmp/phase5-e2e`.

## Limites

Arquivos comerciais do aplicativo Kindle observados na Fase 1 usam contêiner protegido `kindle_drmion`; permanecem bloqueados. A Fase 5 não implementa descriptografia. O manifesto registra metadados técnicos e hashes, não o texto do livro nem chaves. A execução foi validada apenas no Windows; distribuição e provas em macOS/Linux permanecem nas fases posteriores. A inspeção visual/editorial de `review_required` não foi substituída por teste automatizado.
