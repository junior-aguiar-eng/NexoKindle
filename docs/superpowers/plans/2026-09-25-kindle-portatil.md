# Conversor Kindle Portátil Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Este documento não autoriza implementação, instalação ou publicação.

**Goal:** converter, localmente, livros jurídicos predominantemente de texto corrido em PDF pesquisável, a partir de arquivos selecionados pelo usuário, com uma aplicação agnóstica à origem do arquivo e distribuída em pacotes portáteis por sistema operacional.

**Architecture:** núcleo Python recebe arquivos locais e produz um modelo intermediário de livro; adaptadores detectam e extraem formatos; um renderizador transforma o modelo em HTML de impressão e PDF. CLI e interface gráfica chamam o mesmo núcleo. Acesso ao Kindle por USB é somente uma forma de selecionar arquivos, não uma dependência do conversor.

**Tech Stack:** Python 3.12; `pytest`; KindleUnpack para arquivos Kindle sem DRM compatíveis; `html5lib` para HTML legado; WeasyPrint para PDF; PyMuPDF para validação; PySide6 para interface; PyInstaller para investigar distribuição portátil. Versões finais devem ser fixadas após a prova de empacotamento e compatibilidade das amostras. Nenhuma dessas bibliotecas substitui o diagnóstico do arquivo real.

**Spec:** [`PROMPT_KINDLE.txt`](../../../PROMPT_KINDLE.txt), complementado pelas decisões do usuário nesta conversa: livros jurídicos comuns, texto corrido, aplicativo agnóstico e portátil. Este plano é a especificação executável consolidada dessas decisões.

## Global Constraints

- Não modificar os arquivos originais; ler ou copiar para uma área temporária local.
- O fluxo básico não exige conta Amazon, Calibre, nuvem, conexão com a internet, Kindle conectado ou instalação global de Python.
- Distribuir artefatos separados para Windows, macOS e Linux, nas arquiteturas efetivamente testadas. Portabilidade não significa um binário universal nem garantia de acesso USB idêntico entre dispositivos.
- Seleção manual de arquivo ou pasta é obrigatória; descoberta automática de Kindle é conveniência posterior.
- O núcleo não importa código, acervo, navegador, sessões ou dependências do NexoJuris Scraper. Reaproveitar apenas padrões: estados explícitos, checkpoint, hash, escrita segura e relatório por item.
- Suportar inicialmente apenas formatos comprovados pelas amostras. Reconhecer outros formatos e responder `unsupported_format`; nunca tratá-los como conversão bem-sucedida.
- Descriptografia é um adaptador opcional, isolado, condicionado a compatibilidade técnica e uso autorizado. Chaves não são persistidas nem registradas. O processo nunca promete que a posse de um número de série basta para ler todo livro.
- Não gravar o PDF definitivo antes de validar estrutura, páginas e texto extraível. Resultado parcial ou duvidoso exige status próprio.
- Não criar instalador, ativação no sistema ou atualização automática como condição de uso.

## Review Focus

1. Arquivo com extensão `.azw3` mas conteúdo de outro formato: detectar por assinatura/estrutura e rejeitar com diagnóstico.
2. Livro protegido, arquivo truncado ou formato Kindle não coberto: manter o original e não criar PDF definitivo.
3. Capítulo com referências relativas a imagens, CSS ou notas: resolver dentro do pacote extraído sem acesso à rede.
4. Interrupção durante renderização ou validação: remover saída temporária e preservar eventual PDF definitivo anterior.
5. Dois livros com mesmo título ou nomes inválidos no sistema de destino: produzir destinos distintos e nomes seguros.

## Mapa de arquivos proposto

O projeto está vazio, além do prompt. A estrutura abaixo é nova e pode ser ajustada somente se a prova de portabilidade revelar uma limitação concreta.

```text
pyproject.toml                 dependências, comandos e configurações de teste
requirements.txt              dependências de execução fixadas para reprodução
README.md                     uso, formatos, limites e distribuição
src/kindle_pdf/__init__.py
src/kindle_pdf/model.py        tipos e estados do livro e do resultado
src/kindle_pdf/detect.py       detecção por conteúdo
src/kindle_pdf/unpack.py       adaptador para KindleUnpack sem DRM
src/kindle_pdf/prepare.py      ordem de leitura e recursos locais
src/kindle_pdf/render.py       HTML de impressão e WeasyPrint
src/kindle_pdf/validate.py     inspeção estrutural e textual do PDF
src/kindle_pdf/pipeline.py     orquestração, transições, temporários e publicação
src/kindle_pdf/batch.py        lote e checkpoint, sem interface
src/kindle_pdf/cli.py          interface de terminal
src/kindle_pdf/gui.py          interface PySide6
src/kindle_pdf/drm.py          porta opcional para etapa de descriptografia
tests/                        fixtures sintéticas e testes por responsabilidade
scripts/                      builds e smoke tests por plataforma
```

`input_books/` e `output_pdfs/` serão pastas opcionais de exemplo, não diretórios obrigatórios nem depósitos de livros reais no repositório. Arquivos protegidos, chaves, PDFs gerados e temporários entram no `.gitignore`.

## Fase 1 — Viabilidade com amostras e portabilidade

**Entrega independente:** diagnóstico de 3 a 5 livros representativos e um PDF mínimo gerado por pacote portátil em cada plataforma escolhida. Esta fase precede a arquitetura final porque WeasyPrint e a GUI possuem componentes nativos.

**Conclusão atualizada em 25/09/2026:** quatro arquivos `.azw` com assinatura `DRMION` foram diagnosticados. Após autorização específica do usuário, três amostras foram processadas em cópias com o utilitário compatível com Kindle Windows 1.0.25218 e convertidas em EPUB pelo KFX Input. Duas também geraram PDF: “Sou péssimo em português” e “Código Penal Militar e Código de Processo Penal Militar”. O PDF jurídico tem 319 páginas, 318 com texto extraível; duas páginas de conteúdo foram inspecionadas visualmente. O PDF é uma prova local com Calibre, **não** uma conversão executada pelo núcleo do aplicativo planejado. O smoke portátil Windows gerou PDF pesquisável; execução em Windows limpo e empacotamento/teste macOS e Linux continuam pendentes. A Fase 1 permanece **parcial**, com viabilidade técnica demonstrada para o exemplar jurídico e portabilidade multiplataforma ainda não comprovada. Evidências em [`docs/validation/2026-09-25-phase1-portability.md`](../../validation/2026-09-25-phase1-portability.md).

**Privacidade do ensaio:** o ambiente bloqueou a limpeza automática da pasta temporária que continha chaves e cópias. O usuário a removeu manualmente; sua ausência foi confirmada em verificação posterior. A unidade mapeada foi removida, os originais do Kindle permaneceram intactos e o PDF final em `outputs/` foi preservado.

- [ ] Selecionar amostras próprias: texto corrido, notas, tabela simples e imagem, quando disponíveis. Registrar somente hash, tamanho, assinatura, formato detectado e características estruturais; não incorporar conteúdo ou chave ao repositório.
- [x] Criar um `scripts/portable_smoke.py` que renderize HTML local, abra o PDF com PyMuPDF e confirme uma página com texto `Teste portátil`.
- [ ] Empacotar esse smoke test para Windows, macOS e Linux em ambientes separados; executar em máquinas/VMs sem Python e sem WeasyPrint previamente instalados. Registrar sistema, arquitetura, tamanho, comandos e dependências externas verificadas em `docs/validation/portable-smoke.md`.
- [ ] Decidir, pela evidência, quais plataformas/arquiteturas são suportadas na primeira versão. Se o pacote exigir instalação global ou acesso de rede para renderizar, a fase não está concluída.

Teste essencial:

```python
def test_smoke_pdf_contains_text(tmp_path):
    from scripts.portable_smoke import make_smoke_pdf
    import fitz
    output = make_smoke_pdf(tmp_path / "smoke.pdf")
    with fitz.open(output) as pdf:
        assert len(pdf) == 1
        assert "Teste portátil" in pdf[0].get_text()
```

## Fase 2 — Contrato do núcleo e diagnóstico

**Entrega independente:** CLI `diagnosticar CAMINHO` que não converte nem altera a entrada e retorna JSON legível por outras interfaces.

**Execução em 25/09/2026:** concluída no Windows para o contrato de diagnóstico. O comando instalável em `.venv` retornou JSON e código 4 para os quatro contêineres Kindle reais, reconhecidos como `kindle_drmion`; hashes e tamanhos coincidiram com a Fase 1. A suíte completa teve 16 testes aprovados com o renderizador local da Fase 1 configurado. Uma revisão independente identificou e levou à correção de uma corrida entre hash e leitura do formato. EPUB, MOBI e AZW3 sem DRM foram testados apenas com estruturas sintéticas; `supported` indica candidato estrutural, sem garantia de extração até a Fase 3. Evidência em [`docs/validation/2026-09-25-phase2-diagnostic.md`](../../validation/2026-09-25-phase2-diagnostic.md).

**Arquivos:** `model.py`, `detect.py`, `cli.py`, `tests/test_detect.py`, `tests/test_cli.py`.

**Interfaces:** `detect_book(path: Path) -> Detection`; `Detection(format, drm_state, size_bytes, sha256, reason)`; `main(argv: list[str] | None = None) -> int`. Estados mínimos: `supported`, `unsupported_format`, `protected_or_unreadable`, `invalid_file`.

- [x] Escrever testes com arquivos sintéticos válidos e inválidos; incluir extensão enganosa e arquivo vazio. Verificar que o hash corresponde aos bytes de entrada.
- [x] Executar `python -m pytest tests/test_detect.py tests/test_cli.py -q` e confirmar a falha esperada antes da implementação.
- [x] Implementar leitura somente de cabeçalhos para identificação preliminar; aplicar limite de tamanho e hash em streaming. O detector não invoca descriptografia e não supõe suporte só pela extensão.
- [x] Implementar `diagnosticar` com saída JSON e códigos de retorno distintos para entrada válida, não suportada e erro de leitura; executar os testes até passarem.
- [x] Comparar o diagnóstico das amostras reais com a estrutura observada; registrar formatos que serão implementados na Fase 3.

Exemplo de contrato testável:

```python
def test_extension_does_not_override_signature(tmp_path):
    from kindle_pdf.detect import detect_book
    sample = tmp_path / "livro.azw3"
    sample.write_bytes(b"not a kindle file")
    result = detect_book(sample)
    assert result.format == "unknown"
    assert result.drm_state == "unknown"
```

## Fase 3 — Extração e modelo intermediário

**Entrega independente:** um livro compatível sem DRM transforma-se em `BookModel`, sem produzir PDF.

**Arquivos:** `model.py`, `unpack.py`, `prepare.py`, `tests/test_unpack.py`, `tests/test_prepare.py`.

**Interfaces:** `unpack_book(input_path: Path, work_dir: Path) -> UnpackedBook`; `prepare_book(unpacked: UnpackedBook) -> BookModel`. `BookModel` contém título, idioma, capítulos ordenados, recursos locais e avisos. Cada capítulo tem identificador, título opcional e XHTML/HTML normalizado. `UnpackedBook` guarda `root`, caminho do manifesto, diretório de recursos e formato efetivamente extraído.

- [x] Criar fixture livre e pequena com capítulos fora da ordem alfabética, nota interna e imagem relativa. Testar que a ordem do manifesto, e não a ordem dos nomes de arquivo, determina a leitura.
- [x] Executar os testes focados e confirmar falha inicial.
- [x] Integrar KindleUnpack como ferramenta local empacotada ou dependência vendorizada conforme sua licença; invocar processo com lista literal de argumentos, sem shell. Capturar saída e erros sem registrar conteúdo integral ou segredos.
- [x] Resolver caminhos relativos dentro do diretório temporário; rejeitar referências que escapem dele ou tentem buscar URLs remotas. Preservar avisos de recursos ausentes no `BookModel`.
- [x] Confirmar em amostras reais título, ordem, contagem de capítulos, notas e recursos; documentar perdas observadas antes de passar ao PDF.

Execução e limites da Fase 3: [relatório de extração](../../validation/2026-09-25-phase3-extraction.md). As três variantes reais de *Dom Casmurro* não possuem marcadores `noteref`; a preservação de nota interna foi comprovada pela fixture, não por essa amostra. O MOBI antigo fornece um único item no spine, e o KF8 aponta para uma imagem de capa ausente. O componente KindleUnpack v0.83 foi incluído com sua licença GPLv3; a decisão de licenciamento/distribuição do produto final permanece na Fase 8.

Teste de ordem e confinamento:

```python
def test_prepare_uses_spine_and_rejects_escape(unpacked_fixture):
    from kindle_pdf.prepare import prepare_book
    book = prepare_book(unpacked_fixture)
    assert [chapter.id for chapter in book.chapters] == ["intro", "capitulo-1"]
    assert all(resource.is_relative_to(unpacked_fixture.root) for resource in book.resources)
```

## Fase 4 — HTML, PDF e validação

**Entrega independente:** PDF pesquisável de um `BookModel`, com saída temporária validada.

**Arquivos:** `render.py`, `validate.py`, `tests/test_render.py`, `tests/test_validate.py`.

**Interfaces:** `render_pdf(book: BookModel, target_tmp: Path, style: PrintStyle) -> Path`; `validate_pdf(pdf_path: Path, expected: BookModel) -> ValidationReport`. `ValidationReport` traz páginas, texto extraível, capítulos identificados, avisos e status `valid`/`review_required`/`invalid`.

- [x] Criar testes de livro sintético com títulos, notas, citação longa, tabela e imagem; verificar extração de texto e marcadores de capítulo com PyMuPDF.
- [x] Confirmar falha inicial dos testes.
- [x] Produzir HTML de impressão com `base_url` local e CSS para hierarquia, margens, quebras de capítulo, notas e tabelas. Bloquear carregamento remoto de recursos durante a renderização.
- [x] Implementar `validate_pdf`: abrir com PyMuPDF, exigir ao menos uma página, texto extraível não vazio para livro textual e presença dos títulos dos capítulos esperados. Classificar perdas de imagem/nota como `review_required` quando o restante estiver legível; PDF ilegível é `invalid`.
- [x] Inspecionar visualmente páginas representativas das amostras reais: capa/início, capítulo intermediário, nota, tabela e final. Anotar discrepâncias em relatório de validação; ajustar CSS antes de considerar a fase concluída.

Execução: [relatório de PDF e revisão visual](../../validation/2026-09-25-phase4-pdf.md). O `base_url` efetivo é o URL de arquivo do HTML temporário; as referências locais dos capítulos são reescritas para URIs `file:` de recursos previamente validados, pois um livro reúne capítulos de diretórios diferentes. Os testes reais não contêm nota identificada, por isso a inspeção de nota e tabela usou o livro sintético. O KF8 permanece `review_required` por referência a imagem ausente no pacote de origem.

Teste de PDF substantivo:

```python
def test_pdf_has_all_chapter_markers(sample_book, tmp_path):
    from kindle_pdf.render import PrintStyle, render_pdf
    from kindle_pdf.validate import validate_pdf
    pdf = render_pdf(sample_book, tmp_path / "book.tmp.pdf", PrintStyle())
    report = validate_pdf(pdf, sample_book)
    assert report.status == "valid"
    assert report.pages >= 1
    assert report.chapters_found == len(sample_book.chapters)
```

## Fase 5 — Pipeline, lote, retomada e CLI

**Entrega independente:** conversão de pasta com resultados individuais, sem sobrescrever saídas válidas nem publicar resultados incompletos.

**Arquivos:** `pipeline.py`, `batch.py`, `cli.py`, `tests/test_pipeline.py`, `tests/test_batch.py`.

**Interfaces:** `convert_one(input_path: Path, output_dir: Path, options: ConvertOptions) -> ConversionResult`; `convert_batch(paths: list[Path], output_dir: Path, options: ConvertOptions) -> BatchReport`. `ConvertOptions` contém estilo de impressão e renderizador injetável para testes de falha. `ConversionResult` inclui caminho de entrada, hash, status, PDF publicado opcional e diagnóstico. Estados: `converted`, `review_required`, `unsupported`, `protected_or_unreadable`, `failed`.

- [x] Escrever testes de colisão de títulos, arquivo já convertido, interrupção simulada durante renderização e lote com um item inválido entre dois válidos.
- [x] Confirmar falha inicial.
- [x] Orquestrar as fases anteriores em diretório temporário; gerar PDF ao lado do destino e publicar o nome definitivo somente depois de `ValidationReport.valid`. Resultado `review_required` fica em área de revisão identificada, nunca como sucesso pleno.
- [x] Criar manifesto local de lote com hash do arquivo, opções relevantes, versão do pipeline e resultado, gravado por substituição segura. Retomar somente quando identidade e opções coincidirem; não armazenar conteúdo do livro ou chaves.
- [x] Expor CLI `diagnosticar`, `converter ARQUIVO` e `converter-pasta PASTA --saida DESTINO`; fornecer progresso simples e resumo JSON opcional. Testar os três comandos em diretórios temporários.

Teste de publicação segura:

```python
def test_failed_conversion_preserves_existing_pdf(valid_input, output_dir, broken_renderer):
    from kindle_pdf.pipeline import ConvertOptions, convert_one
    existing = output_dir / "Livro.pdf"
    existing.write_bytes(b"existing valid output")
    result = convert_one(valid_input, output_dir, ConvertOptions(renderer=broken_renderer))
    assert result.status == "failed"
    assert existing.read_bytes() == b"existing valid output"
    assert not list(output_dir.glob("*.tmp.pdf"))
```

## Fase 6 — Etapa opcional para arquivos protegidos

**Entrega independente:** contrato isolado e diagnóstico honesto; integração concreta somente para combinação de formato, ferramenta e amostras comprovadamente compatível.

**Arquivos:** `drm.py`, `drm_windows.py`, `pipeline.py`, `cli.py`, `tests/test_drm.py`, `tests/test_windows_kindle.py`, documentação de compatibilidade.

**Interfaces:** `DecryptAdapter.decrypt(input_path: Path, output_dir: Path, credential: SecretInput) -> DecryptResult`; `DecryptResult` distingue `decrypted`, `unsupported`, `invalid_credential` e `failed`. `SecretInput` não possui serialização para manifesto/log.

- [x] Testar primeiro que `protected_or_unreadable` não publica PDF e que `SecretInput` não aparece em exceções, logs ou manifesto.
- [x] Confirmar falha inicial dos testes.
- [x] Implementar a porta para adaptador opcional sem acoplar o núcleo a uma ferramenta específica; avaliar compatibilidade técnica e licença da ferramenta selecionada antes de integrar seus arquivos ou distribuir binários.
- [x] Integrar em um adaptador Windows a cadeia já validada na Fase 1: arquivador externo → KFX-ZIP → Calibre Portable/KFX Input → EPUB → núcleo → PDF. Ferramentas são indicadas por caminho e não entram no pacote Python.
- [x] Testar com um livro autorizado: “Código Penal Militar e Código de Processo Penal Militar” produziu PDF `converted` com 230 páginas e texto extraível em todas. O original conservou o SHA-256; a pasta temporária e a unidade mapeada foram removidas; não restaram chaves ou intermediários no destino nem seus nomes no manifesto.

**Conclusão atualizada em 25/09/2026:** a conversão protegida funciona na CLI do projeto para a combinação específica Kindle Windows `1.0.25218.0` x64 + arquivador v10.0.32 com hash fixado + Calibre Portable 9.15 + KFX Input 2.34.2. A ferramenta externa não foi instalada globalmente nem incluída no pacote Python. O adaptador recusa executar se detectar, antes do processo, a pasta que o arquivador copiaria para fora da área temporária. O teste real cobre um livro jurídico; não comprova os demais livros da biblioteca, novas versões do aplicativo, Kindle físico, macOS, Linux, instalação em Windows limpo nem equivalência editorial com o PDF de 319 páginas da Fase 1. O destino deve ficar fora de sincronização/backup durante a execução, pois contém temporários sensíveis; exclusão normal não é apagamento seguro. A licença para redistribuir o executável externo segue sem decisão; a rota atual depende de ferramenta local fornecida pelo usuário. Evidências no [relatório da Fase 6](../../validation/2026-09-25-phase6-protected.md).

Teste de privacidade:

```python
def test_secret_is_absent_from_result_and_log(protected_sample, tmp_path, caplog):
    from kindle_pdf.drm import SecretInput, diagnose_protected
    secret = SecretInput("SERIAL-DE-TESTE-NAO-REAL")
    result = diagnose_protected(protected_sample, secret, tmp_path)
    assert "SERIAL-DE-TESTE-NAO-REAL" not in repr(result)
    assert "SERIAL-DE-TESTE-NAO-REAL" not in caplog.text
```

## Fase 7 — Interface gráfica e acesso agnóstico aos arquivos

**Entrega independente:** janela que seleciona arquivos/pastas e usa o mesmo `convert_batch` da CLI.

**Arquivos:** `gui.py`, `batch.py`, `tests/test_gui.py`, `tests/test_batch.py`, `pyproject.toml`, `README.md` e relatório de validação.

**Interfaces:** `launch_gui() -> int`; seleção fornece `list[Path]` ao núcleo. A interface exibe diagnóstico, progresso por livro, resultado e caminho do PDF. O trabalho pesado roda fora da thread da interface.

- [x] Testar a passagem dos caminhos selecionados ao núcleo, a apresentação de cada status e o cancelamento entre livros. A GUI foi testada com núcleo falso; o lote real ganhou `should_cancel` e teste próprio.
- [x] Confirmar falha inicial dos testes antes de implementar.
- [x] Implementar seleção manual e arrastar/soltar; permitir escolher uma pasta visível do Kindle quando o sistema a expuser. Não depender de letra de unidade, API da Amazon ou detecção automática. Varredura de pastas e conversão usam threads Qt distintas; a porta protegida da Fase 6 recebe caminhos explícitos das ferramentas locais.
- [ ] Completar o teste manual nos três sistemas: selecionar pasta local e unidade/dispositivo acessível, cancelar lote e abrir PDF final. No Windows, uma pasta local foi convertida pela GUI em PDF pesquisável; a pasta local do livro do aplicativo Kindle foi reconhecida; cancelamento durante o primeiro livro impediu a conversão do segundo. A abertura do PDF foi testada por chamada controlada, sem iniciar um visualizador externo. Não havia Kindle físico nem ambientes macOS/Linux acessíveis.

**Conclusão em 25/09/2026:** a implementação da GUI e seus testes de código estão concluídos para o ambiente Windows disponível. A validação manual multiplataforma e em dispositivo físico permanece aberta. O wheel Python contém a interface, mas não constitui aplicativo autônomo; empacotamento e máquina limpa pertencem à Fase 8. Evidências no [relatório da Fase 7](../../validation/2026-09-25-phase7-gui.md).

## Fase 8 — Distribuição e aceitação

**Entrega independente:** pacotes portáteis reproduzíveis por plataforma suportada, documentação e evidências de execução em ambiente limpo.

**Arquivos:** `scripts/build_windows.ps1`, `scripts/build_installer_windows.ps1`, `installer/KindlePDF.iss`, `scripts/build_macos.sh`, `scripts/build_linux.sh`, `README.md`, `docs/validation/release-matrix.md`, `requirements.txt`.

- [x] Gerar candidato Windows x64 em ZIP com `KindlePDF.exe` gráfico e `KindlePDF-CLI.exe` para comandos e processo filho KindleUnpack, além do renderizador local. `scripts/build_windows.ps1` usa versões fixadas, verifica o ZIP oficial do WeasyPrint e rejeita o build caso o subsistema do executável gráfico seja de console.
- [x] Adicionar instalador Windows por usuário a partir do mesmo bundle, com menu Iniciar e desinstalador. Inno Setup 7 compila um `.exe` local; a atualização da cópia instalada foi ensaiada com autorização do usuário, e os executáveis instalados coincidiram com o bundle. A desinstalação ainda precisa de ensaio separado.
- [ ] Gerar e testar pacotes nativos macOS/Linux. Os scripts foram preparados, mas estes sistemas e renderizadores nativos não estavam disponíveis; não houve cross-build.
- [ ] Executar CLI e GUI em máquinas/VMs limpas, sem Python instalado; verificar tráfego de rede e gravações. O ZIP anterior funcionou recolocado em outra pasta com `PATH` reduzido e sem variáveis de Python/renderizador, mas tinha a GUI compilada como console. O novo ZIP foi extraído em outra pasta: diagnóstico MOBI e permanência da GUI após o lançador PowerShell terminar passaram. No bundle corrigido, o livro autorizado foi reconvertido com 230 páginas de texto; um teste visual interativo e VM limpa faltam. O hash da origem Kindle permaneceu igual e os temporários foram removidos.
- [ ] Repetir toda a matriz da Fase 1, com tempo, inspeção visual e formatos reais adicionais. Um livro jurídico autorizado foi reconvertido pelo ZIP; EPUB/MOBI sintéticos verificaram as rotas comuns. Kindle físico e os outros exemplares reais não foram ensaiados nesta fase.
- [x] Rodar suíte completa, mypy e Ruff do código próprio, e inspecionar o ZIP para ausência de livros, chaves e ferramentas externas. A revisão de licenças para distribuição permanece aberta; build local, publicação e instalação em terceiros são gates separados.

**Conclusão em 25/09/2026:** existe um candidato portátil Windows validado nesta estação, inclusive no caminho protegido com o livro autorizado, e um instalador local compilado do mesmo bundle. Após o usuário identificar que a GUI se encerrava ao fechar o PowerShell, o bundle foi reconstruído com executável gráfico separado da CLI; o build verifica os subsistemas PE. A cópia instalada no perfil foi atualizada com autorização do usuário e passou no ensaio de permanência após o PowerShell lançador encerrar. A Fase 8 permanece **parcial** por falta de ensaio de desinstalação, máquina limpa, macOS/Linux, teste visual interativo do executável, matriz completa e decisão de licenças. Evidências em [relatório da Fase 8](../../validation/2026-09-25-phase8-release.md) e [matriz](../../validation/release-matrix.md).

## Condições de conclusão

O projeto atende à primeira versão quando arquivos compatíveis de texto corrido podem ser diagnosticados e convertidos localmente pela CLI e pela GUI; o PDF é pesquisável e passa pela inspeção estrutural e visual; falhas não danificam origem ou saída anterior; e os pacotes executam sem instalação de Python nas plataformas declaradas. Compatibilidade com cada formato/proteção é afirmada somente após teste com amostra real correspondente.

## Referências técnicas verificadas na análise

- KindleUnpack: <https://github.com/kevinhendricks/KindleUnpack> — extração de Kindle/MobiPocket sem DRM, com saída distinta conforme a geração do formato.
- WeasyPrint: <https://doc.courtbouillon.org/weasyprint/stable/api_reference.html> — `base_url`, recursos relativos e `write_pdf()`.
- Instalação do WeasyPrint: <https://doc.courtbouillon.org/weasyprint/latest/first_steps.html> — componentes nativos e particularidades por plataforma.
- Ajuda da Amazon para acesso USB: <https://digprjsurvey.amazon.com/csad/help/node/TCUBEdEkbIhK07ysFu> — o acesso aos arquivos do dispositivo varia entre sistemas e modelos; por isso, seleção de arquivo local é o contrato principal.
