# Kindle PDF — conversão local de livros para PDF

O aplicativo identifica o formato de um arquivo local, extrai EPUB, KF8/AZW3 e MOBI compatíveis sem DRM, valida o PDF pesquisável e publica somente resultados aprovados. Para um livro protegido do aplicativo Kindle para Windows, o candidato local completo inclui as ferramentas necessárias e escolhe essa rota automaticamente. O fluxo básico não exige Kindle conectado, conta Amazon ou conexão de rede.

## Uso no Windows

Em um ambiente Python 3.12 local ao projeto:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e .
.venv\Scripts\kindle-pdf.exe diagnosticar "C:\caminho\livro.azw"
```

A saída é um único objeto JSON com `status`, `format`, `drm_state`, `size_bytes`, `sha256` e `reason`. O hash SHA-256 é calculado em fluxo; o arquivo de entrada não é alterado. Arquivos acima de 1 GiB são recusados antes do hash.

| `status` | Significado | Código de saída |
| --- | --- | ---: |
| `supported` | Cabeçalho ou estrutura preliminar compatível com EPUB, MOBI ou AZW3 sem proteção detectada. A extração deve ser verificada separadamente. | 0 |
| `unsupported_format` | Formato desconhecido ou KFX-ZIP reconhecido sem adaptador no núcleo. | 2 |
| `invalid_file` | Entrada ausente, vazia, truncada, excessiva ou ilegível. | 3 |
| `protected_or_unreadable` | Proteção identificada pelo cabeçalho ou manifesto. O diagnóstico não tenta descriptografar. | 4 |

O detector reconhece `EA DRMION` do aplicativo Kindle Windows atual, além de `DRMION` direto; não confia na extensão para decidir o formato. `drm_state=not_detected` significa somente que os indicadores inspecionados não apontaram proteção. A validação editorial ou criptográfica completa ainda não existe nesta fase.

## Interface gráfica atual

Abra **KindlePDF** pelo menu Iniciar ou execute `KindlePDF.exe`. Com o Kindle para Windows instalado e o livro baixado, clique em **Selecionar livro**, escolha o título e clique em **Converter**. Para EPUB, MOBI ou AZW3 de outra pasta, use **Outro arquivo**. O aplicativo decide pelo conteúdo do arquivo se basta a extração comum ou se deve usar a rota Kindle. Ao concluir, clique em **Abrir PDF**. Os PDFs vão por padrão para `%LOCALAPPDATA%\KindlePDF\PDFs`; **Configurações** permite escolher outro destino local. A interface não pede caminhos de arquivador, Calibre ou KFX Input.

O app não acessa a conta Amazon e não baixa livros: esses passos são feitos no aplicativo Kindle. Se **Selecionar livro** não encontrar nada, confirme no Kindle que o livro foi baixado neste computador; **Outro arquivo** aceita uma cópia local. O seletor lê títulos do cache local do Kindle quando disponíveis e mostra o identificador do arquivo nos demais casos. Livros protegidos exigem a versão de Kindle para Windows compatível com o adaptador testado. A [validação da nova interface](docs/validation/2026-09-26-one-click.md) distingue o que foi testado do que ainda depende de outro computador.

## Candidato portátil Windows (Fase 8)

O build local produz um instalador Windows por usuário em `artifacts/KindlePDF-Setup-win-x64-candidate.exe`, compilado com Inno Setup 7; ele cria entrada no menu Iniciar e desinstalador sem solicitar privilégios de administrador. Também produz um ZIP portátil em `artifacts/KindlePDF-win-x64-candidate.zip`. Esses binários **não são enviados a este repositório público**. O candidato local inclui o arquivador validado, Calibre Portable e KFX Input dentro do app, sem instalação global separada. **Ainda não está liberado para distribuição a terceiros**: a licença de redistribuição do arquivador específico e o inventário completo das demais dependências permanecem pendentes.

O bundle contém `KindlePDF.exe` para a interface gráfica, `KindlePDF-CLI.exe` para o terminal, PySide6, PyMuPDF, KindleUnpack e o WeasyPrint Windows v70. No uso portátil, extraia a pasta inteira, sem instalar Python. Abra `KindlePDF.exe` diretamente pelo Explorador ou menu Iniciar; ele é um aplicativo Windows sem janela de PowerShell associada. Para comandos, use o executável de console:

```powershell
.\KindlePDF-CLI.exe diagnosticar "C:\livros\livro.epub"
.\KindlePDF-CLI.exe converter "C:\livros\livro.epub" --saida "C:\pdfs"
```

Na GUI, a rota protegida é automática quando o pacote completo está presente. A CLI conserva suas opções explícitas para diagnóstico técnico. O pacote não se conecta à conta Amazon e a compatibilidade continua restrita à versão validada do Kindle para Windows.

O script [`build_windows.ps1`](scripts/build_windows.ps1) verifica o SHA-256 do WeasyPrint oficial, instala as dependências fixadas em [`requirements.txt`](requirements.txt) no ambiente local de build, vincula o código fonte atual e cria o ZIP. Exige os caminhos locais `-Archiver`, `-CalibreDir` e `-KfxInputZip` e valida os hashes das quatro peças executáveis ou instaláveis antes de preparar `tools/`. [`build_installer_windows.ps1`](scripts/build_installer_windows.ps1) recusa um bundle sem essas ferramentas ou com hash divergente e compila o [projeto Inno](installer/KindlePDF.iss). [`build_macos.sh`](scripts/build_macos.sh) e [`build_linux.sh`](scripts/build_linux.sh) continuam sem execução validada.

No Windows 11 desta estação, o bundle corrigido converteu um MOBI de teste e o livro Kindle autorizado, com 230 páginas de texto extraível. O hash do livro original permaneceu igual; não restou pasta temporária do fluxo protegido e o manifesto não contém marcadores de segredos. O novo ZIP foi extraído em outro diretório: seus executáveis passaram pela verificação de subsistema PE, diagnosticaram o MOBI e mantiveram a GUI ativa depois que o PowerShell lançador terminou. A conversão protegida foi feita pelo mesmo bundle antes da extração do ZIP. Ainda faltam máquina limpa, validação visual interativa do executável, macOS/Linux e revisão de licenças antes de distribuição externa. Consulte a [matriz de aceitação](docs/validation/release-matrix.md) e o [relatório da Fase 8](docs/validation/2026-09-25-phase8-release.md).

## API de extração (Fase 3)

```python
from pathlib import Path
from kindle_pdf.unpack import unpack_book
from kindle_pdf.prepare import prepare_book

unpacked = unpack_book(Path("livro.epub"), Path("area-temporaria"))
book = prepare_book(unpacked)
print(book.title, book.language, len(book.chapters), book.warnings)
```

`unpack_book` preserva o original e cria `area-temporaria/book`; a área deve ser nova para cada livro. `prepare_book` lê a ordem do spine, normaliza HTML antigo, mantém notas e caminhos de recursos locais, recusa referências externas em recursos ativos e informa arquivos ausentes. O HTML devolvido pelos capítulos ainda não foi preparado para impressão. A API rejeita arquivos cuja proteção seja identificada pelo diagnóstico; não usa chaves nem altera livros protegidos.

O KindleUnpack v0.83 está incluído como ferramenta local em `src/kindle_pdf/_vendor/KindleUnpack`, com código fonte, origem e licença GPLv3. No ambiente Python, pode-se substituir o script com `KINDLEUNPACK_SCRIPT`; o executável portátil usa seu modo interno e recusa essa variável. A revisão das licenças para distribuição do aplicativo e dos pacotes permanece pendente após a Fase 8. Somente o Windows foi validado até agora.

## Renderização e validação (Fase 4)

No Windows validado nesta fase, aponte `WEASYPRINT_EXE` para o executável local do WeasyPrint v70 já preparado na Fase 1. O pacote Python chama esse executável sem shell e permite apenas recursos com protocolo `file`; recursos e CSS também passam por validação de caminhos. O executável ainda não é distribuído dentro do wheel Python.

```powershell
$env:WEASYPRINT_EXE = "C:\caminho\weasyprint.exe"
```

```python
from pathlib import Path
from kindle_pdf.render import PrintStyle, render_pdf
from kindle_pdf.validate import validate_pdf

pdf = render_pdf(book, Path("area-temporaria/livro.tmp.pdf"), PrintStyle())
report = validate_pdf(pdf, book)
print(report.status, report.pages, report.chapters_found, report.warnings)
```

O renderizador recusa sobrescrever o destino e remove um PDF parcial em falhas. `validate_pdf` exige texto extraível e marcadores de capítulo em ordem no sumário do PDF; notas e imagens ausentes resultam em `review_required`, e falta de texto/capítulos resulta em `invalid`. O PDF gerado por essa API isolada permanece temporário. A API e a CLI da Fase 5 fazem a publicação controlada.

## Conversão e retomada (Fase 5)

Após configurar `WEASYPRINT_EXE`, execute:

```powershell
.venv\Scripts\kindle-pdf.exe converter "C:\livros\livro.epub" --saida "C:\pdfs" --json
.venv\Scripts\kindle-pdf.exe converter-pasta "C:\livros" --saida "C:\pdfs"
```

`--json` também funciona em `converter-pasta`; sem essa opção, o lote mostra o andamento de cada arquivo. O lote percorre subpastas e grava `.kindle-pdf-batch.json` no destino após cada item. Na retomada, verifica hash da entrada, opções, versão do pipeline e hash do PDF produzido. Saídas válidas já existentes nunca são sobrescritas. Um PDF com ressalvas fica em `review/` e recebe `review_required`; não aparece na pasta principal como `converted`. Arquivos protegidos sem adaptador recebem `protected_or_unreadable`.

Os códigos de saída da conversão são 0 para todos convertidos (inclusive lote vazio), 1 se houver falha ou formato incompatível, 4 para protegido e 5 se houver apenas itens que exigem revisão. O diagnóstico conserva seus códigos próprios acima.

## Kindle para Windows com proteção (Fase 6)

O adaptador opcional `kindle_pdf.drm_windows.WindowsKindleAdapter` usa o arquivador externo compatível com o aplicativo Kindle Windows `1.0.25218.0` x64, o Calibre Portable 9.15 e o plugin KFX Input 2.34.2. Os três caminhos são informados explicitamente. O arquivador, o Calibre e o plugin **não** integram o pacote Python; o programa não os instala globalmente. O adaptador lê a pasta de um livro já baixado pelo aplicativo Kindle e produz, dentro da área temporária da conversão, KFX-ZIP e EPUB. O núcleo aceita somente o EPUB validado e então gera e valida o PDF.

Com as ferramentas já preparadas localmente, configure o renderizador e execute, por exemplo:

```powershell
$env:WEASYPRINT_EXE = "C:\caminho\weasyprint.exe"
.venv\Scripts\kindle-pdf.exe converter-pasta "C:\caminho\Kindle\Content\ID_DO_LIVRO_EBOK" `
  --saida "C:\caminho\pdfs" --kindle-windows `
  --archiver-exe "C:\caminho\MSIXKFXArchiver_x64_1_25218.exe" `
  --calibre-dir "C:\caminho\Calibre Portable\Calibre" `
  --kfx-input-zip "C:\caminho\KFX Input.zip" --json
```

`converter` também aceita as mesmas opções para um único `.azw`. A pasta `_EBOK` precisa conter os demais arquivos do livro; selecionar apenas uma cópia isolada do `.azw` não basta. A GUI valida os hashes do arquivador, dos executáveis do Calibre e do plugin incluídos; a CLI aceita caminhos externos explicitamente informados e valida o arquivador. Uma mudança na versão do Kindle exige nova validação antes de se afirmar compatibilidade. A opção usa o material local já existente do aplicativo Kindle; a `SecretInput` interna é apenas um marcador exigido pelo contrato da porta e não contém chave, senha ou token.

O núcleo cria uma pasta `.kindle-pdf-*` no destino, copia para ela os arquivos do livro e mapeia essa pasta a uma letra de unidade temporária para conter a pasta `Data` usada pelo arquivador. O adaptador direciona arquivos de chave, KFX-ZIP, EPUB, cache e configuração do Calibre para essa área; stdout e stderr das ferramentas externas são descartados porque podem conter tokens. O manifesto registra somente hashes, opções não secretas, status e caminho do PDF. A pasta e a unidade são removidas ao final da operação normal. Se a pasta de cache de chaves que essa versão da ferramenta copiaria para fora da área temporária existir na verificação inicial, o adaptador recusa a execução.

Use um destino local fora de pastas sincronizadas ou submetidas a backup durante a execução: um serviço desses pode copiar os temporários antes de serem removidos. A limpeza normal não é apagamento seguro. Se o próprio Kindle criar o cache externo enquanto o arquivador estiver rodando, esta verificação inicial não impede uma cópia externa; não foi observado no ensaio. A retomada confere os hashes do livro e do PDF, mas não as versões do Calibre e do plugin: trocar essas ferramentas não força uma nova conversão de um PDF já validado.

O ensaio real desta fase converteu o livro autorizado “Código Penal Militar e Código de Processo Penal Militar” até um PDF de 230 páginas, todas com texto extraível. Confirmamos a remoção da pasta temporária e da unidade mapeada, a ausência de `C:\Data`, e a preservação do hash do original. Isso demonstra a combinação testada; não demonstra compatibilidade com outros livros, outras versões do Kindle, Kindle físico, macOS ou Linux. A rota depende de ferramentas externas mantidas pelo usuário. A distribuição futura dessas ferramentas exige análise de licença separada. O PDF anterior da Fase 1, produzido por outra rota no Calibre, tem 319 páginas; a diferença de paginação não foi examinada editorialmente. Consulte o [relatório da Fase 6](docs/validation/2026-09-25-phase6-protected.md).

`SecretInput` oculta seu valor em `repr`/`str` e recusa serialização; o manifesto exclui credenciais. Quando há adaptador, o lote pode retomar um PDF previamente validado por hashes e identidade do adaptador sem armazenar ou verificar novamente a credencial. Sem adaptador, arquivos protegidos continuam com `protected_or_unreadable`.

Os resultados e limites estão nos relatórios de [Fase 2](docs/validation/2026-09-25-phase2-diagnostic.md), [Fase 3](docs/validation/2026-09-25-phase3-extraction.md), [Fase 4](docs/validation/2026-09-25-phase4-pdf.md), [Fase 5](docs/validation/2026-09-25-phase5-pipeline.md), [Fase 6](docs/validation/2026-09-25-phase6-protected.md) e [Fase 7](docs/validation/2026-09-25-phase7-gui.md). O [plano](docs/superpowers/plans/2026-09-25-kindle-portatil.md) acompanha as etapas restantes.
