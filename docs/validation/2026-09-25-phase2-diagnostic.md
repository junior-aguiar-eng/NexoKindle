# Fase 2 — contrato do núcleo e diagnóstico

Data: 25/09/2026. Ambiente: Windows 11 x64, Python 3.12.14. Escopo: CLI local somente de leitura. Os arquivos originais do Kindle não foram convertidos, copiados ou modificados nesta fase.

## Contrato entregue

- `detect_book(path: Path) -> Detection` em `src/kindle_pdf/detect.py`.
- `Detection(status, format, drm_state, size_bytes, sha256, reason)` em `src/kindle_pdf/model.py`.
- `kindle-pdf diagnosticar CAMINHO` em `src/kindle_pdf/cli.py`, com um objeto JSON na saída padrão e códigos 0/2/3/4. O comando foi instalado apenas em `.venv`, sem instalação global.
- A detecção usa assinatura ou estrutura, hash SHA-256 em blocos de 1 MiB e limite padrão de 1 GiB. EPUB, Palm/MOBI, KFX-ZIP e DRMION têm caminhos distintos; KFX-ZIP é reconhecido como `unsupported_format` porque o núcleo ainda não possui seu adaptador.

## Testes e comparação real

A primeira execução dos testes falhou por módulo ausente; depois de criar interfaces mínimas, 11 testes falharam com `NotImplementedError`, como esperado. Após a implementação, 12 testes focados passaram. A comparação com os arquivos Kindle revelou que a assinatura real começa com `EA DRMION`, e não com `DRMION` no primeiro byte. Um teste de regressão falhou para esse prefixo e passou após a correção.

Com `WEASYPRINT_EXE` apontando para o renderizador local da Fase 1, a suíte completa terminou com **16 testes aprovados**. A primeira execução da suíte sem essa variável falhou apenas no smoke anterior, porque o renderizador não estava no caminho padrão. O executável de entrada `.venv/Scripts/kindle-pdf.exe` também foi invocado nos quatro arquivos reais e devolveu JSON, código 4 e hash idêntico ao calculado diretamente.

| ID do livro | Formato | Estado | Bytes | Prefixo SHA-256 |
| --- | --- | --- | ---: | --- |
| `B07FCS663K_EBOK` | `kindle_drmion` | `protected_or_unreadable` | 836.327 | `71503b0076ae` |
| `B0D2LTZZSP_EBOK` | `kindle_drmion` | `protected_or_unreadable` | 618.916 | `0bcd84071c6b` |
| `B0DLBS3HMV_EBOK` | `kindle_drmion` | `protected_or_unreadable` | 630.260 | `b0db62894ece` |
| `B0F6TBJPY1_EBOK` | `kindle_drmion` | `protected_or_unreadable` | 267.297 | `5b9804c68a4e` |

Os hashes completos conferem com o [diagnóstico da Fase 1](2026-09-25-phase1-portability.md). Os testes EPUB/MOBI/AZW3 são sintéticos; ainda não há amostras reais sem DRM para afirmar suporte de extração. O estado `supported` nesta fase descreve compatibilidade preliminar do cabeçalho, não conversão comprovada.

## Decisões e limites

- Sem repositório Git neste diretório: não foram criados branch, worktree ou commit. A evidência fica neste relatório e nos testes.
- Foi criado `.gitignore` para excluir livros, PDFs, chaves, `.tmp/` e artefatos quando o diretório vier a ser versionado.
- O ensaio da Fase 1 com chaves continua separado do comando `diagnosticar`; nenhuma chave é exigida, lida, serializada ou exibida por este núcleo.
- A pasta temporária sensível da Fase 1 foi removida pelo usuário; a ausência foi confirmada em verificação posterior. O diagnóstico não a utilizou.

## Revisão independente

A revisão apontou risco de divergência entre SHA-256 e formato porque o detector reabria o arquivo após o hash. Um teste de troca de arquivo falhou antes da correção e passou depois: o hash e a leitura do cabeçalho agora usam o mesmo descritor, com verificação de tamanho e hora de modificação ao final. A suíte completa permaneceu verde (16/16) e a comparação dos quatro arquivos reais foi repetida.

A revisão também sugeriu que compressão ZIP desconhecida causaria exceção não tratada. O caso sintético executado retornou JSON `invalid_file` e código 3 sem alteração do código: em Python, `NotImplementedError` herda de `RuntimeError`, já capturada pelo detector. O teste exploratório, que passou desde o início, não foi mantido como teste de regressão de um defeito inexistente.
