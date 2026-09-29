# Fase 1 — diagnóstico de amostra e prova de portabilidade

Data: 25/09/2026. Escopo executado no Windows 11 x64, Python 3.12.14. Este relatório registra uma prova técnica, não uma versão distribuível do conversor.

## Resultado por requisito

| Requisito da Fase 1 | Resultado observado |
| --- | --- |
| 3 a 5 livros Kindle representativos | Parcial. Quatro contêineres foram diagnosticados; três geraram EPUB, e dois geraram PDF, incluindo o volume jurídico. Notas e tabelas não foram avaliadas porque não ocorreram no EPUB jurídico testado. |
| Diagnóstico sem alterar os livros | Executado para quatro arquivos: extensão, tamanho, SHA-256 e 32 bytes iniciais. |
| PDF mínimo com texto pesquisável | Aprovado no Windows. O teste automatizado passou e o PDF extraído do pacote tinha 1 página e o texto esperado. |
| Pacote Windows executado sem instalação global de Python | Aprovado como simulação local: o ZIP foi extraído em outra pasta e o executável rodou com `PATH` contendo apenas diretórios do Windows. Não houve teste em máquina limpa. |
| Pacotes e execução em macOS e Linux | Não executados. O usuário informou dispor apenas de Windows; WSL continha somente `docker-desktop` e o daemon Docker não estava ativo. |

## Amostra do aplicativo Kindle

- Aplicativo em execução: `AMZNKindle.AmazonKindleReadingApp`, versão do pacote observada `1.0.25218.0`, Windows x64.
- Local técnico: `LocalState/Classic/Content/` do pacote do aplicativo. Quatro arquivos principais com extensão `.azw` foram encontrados. A captura da biblioteca enviada pelo usuário mostra “Código Penal Militar e Código de Processo Penal Militar”, “Vigiar e punir”, “Sou péssimo em português” e “Crime e castigo”. A correspondência entre cada título e identificador interno não foi confirmada pela leitura técnica dos arquivos.
- Assinatura inicial observada em ASCII nos quatro: `DRMION`; o prefixo também contém `ProtectedData`. **Inferência:** são contêineres protegidos, e a extensão `.azw` não demonstra compatibilidade com o caminho AZW3/MOBI sem DRM previsto no prompt original.

| Identificador interno | Tamanho (bytes) | SHA-256 |
| --- | ---: | --- |
| `B0DLBS3HMV_EBOK` | 630.260 | `B0DB62894ECE2F91CE015E0874CA5046185AE746DE798415F4714E327BF2E2F0` |
| `B0D2LTZZSP_EBOK` | 618.916 | `0BCD84071C6B483E76BF26F2136A482329B9E642E8759749C3074C44328CDBC8` |
| `B07FCS663K_EBOK` | 836.327 | `71503B0076AE3A60F69197822FB525EB52027A353634DCEEEF8DC166BEB7588F` |
| `B0F6TBJPY1_EBOK` | 267.297 | `5B9804C68A4EA1D98761AB0B1B6DA124AE252D832231C668CC5C2D21FB978E35` |
- Na inspeção inicial, não foram lidos capítulos, texto, credenciais ou chaves. No ensaio posterior abaixo, três pastas de livros foram copiadas para teste; os originais do aplicativo não foram modificados.

**Decisão arquitetural:** o detector da Fase 2 deve reconhecer `DRMION` antes de escolher adaptador por extensão e devolver estado explícito de conteúdo protegido ou não legível. A Fase 3 não deve presumir que livros baixados pelo aplicativo atual sejam AZW3/MOBI aceitos por KindleUnpack.

### Caminho candidato para os arquivos protegidos

Em 25/09/2026, a versão preliminar [DeDRM_tools v10.0.32](https://github.com/Satsuoni/DeDRM_tools/releases/tag/v10.0.32) declara suporte **específico a MSKindle 1.0.25218**, a mesma versão principal observada neste computador. O mantenedor também informa que ela é 64 bits e que os executáveis anteriores não servem para essa versão. A publicação fornece um pacote `DeDRM_tools.zip` e ferramentas auxiliares; sua descrição menciona a criação de `books.keyfile`. Isto constitui uma rota técnica concreta para um ensaio isolado, mas **não comprova** que algum dos quatro livros possa ser extraído, convertido ou renderizado com fidelidade. Nenhum desses utilitários foi instalado ou executado nesta fase; nenhuma chave foi lida.

O usuário informou possuir um Kindle físico na mesma conta, porém sem acesso ao aparelho neste momento. Esse dispositivo representa uma segunda origem de arquivos para diagnóstico posterior, sem garantia de formato ou extração. O núcleo portátil do projeto deve receber um arquivo intermediário legível de qualquer adaptador; o adaptador específico para o aplicativo MSKindle 64 bits seria dependente de Windows e versão.

### Ensaio local autorizado: KFX → EPUB → PDF

O usuário autorizou o ensaio com o utilitário que acessa chaves da instalação Kindle. Foi baixado o pacote oficial da publicação v10.0.32, SHA-256 `AF63128BC089757BC399DEFB42E20D3E105198B5128DB1CB466922719223850D`, e extraído `MSIXKFXArchiver_x64_1_25218.exe`, SHA-256 `A06D8946901CF962A8024E8A4C34CB9EBCD7D61B5EBD443E41D7738474096157`. O `dsx120.dll` instalado tinha MD5 `E8D7579F15E15451BE300021306EF2AF`, idêntico ao identificador previsto no código-fonte para essa versão. A saída bruta do executável foi suprimida porque o código pode imprimir tokens da conta. Ele foi executado com cópias de pastas selecionadas e diretório temporário mapeado para a pasta de ensaio; não criou `C:\Data`.

Foi usado Calibre Portable 9.15.0, obtido da publicação oficial (instalador SHA-256 `55A8C89BC0739A2DC6D496742EA625FCCC6DFDEC1413EB805805A28E7227536C`, assinatura Windows válida) e o plugin KFX Input 2.34.2. O primeiro ensaio gerou um `kfx-zip` com quatro componentes de cabeçalho `CONT`, depois EPUB e PDF. O segundo gerou dois `kfx-zip` e dois EPUB. Os títulos abaixo foram lidos dos metadados dos EPUB gerados, não inferidos pela ordem da biblioteca:

| Identificador | Título confirmado | Resultado |
| --- | --- | --- |
| `B07FCS663K_EBOK` | Sou péssimo em português | EPUB e PDF; PDF com 185 páginas, 178 com texto extraível. |
| `B0DLBS3HMV_EBOK` | Vigiar e punir | EPUB gerado; PDF não solicitado neste ensaio. |
| `B0F6TBJPY1_EBOK` | Código Penal Militar e Código de Processo Penal Militar | EPUB e PDF; PDF com 319 páginas, 318 com texto extraível e 503.199 caracteres extraídos por PyMuPDF. |

O EPUB jurídico continha sete documentos HTML; a inspeção estrutural encontrou zero tabelas e zero referências explícitas a notas. As páginas 101 e 251 do PDF foram renderizadas e inspecionadas: texto, títulos de artigos e parágrafos apareceram legíveis. Isso comprova conversão deste exemplar, mas não fidelidade integral contra a edição original. O [PDF local de prova](../../outputs/Codigo%20Penal%20Militar%20e%20Codigo%20de%20Processo%20Penal%20Militar.pdf) tem 2.459.480 bytes e SHA-256 `2C104281B01608419135FD18D611EAB4BB26D18C01C3224795FBCD76F31981D4`.

**Histórico da limpeza:** o utilitário criou `books.keyfile`, `keys.k4i`, `keys-legal.k4i` e as pastas `Data` e `storage` em `.tmp/kindle-pilot-25218/`, junto a cópias e derivados dos livros. O ambiente bloqueou duas tentativas de limpeza com `Remove-Item`; nenhuma técnica alternativa de exclusão foi usada. O usuário informou que removeu a pasta. Em verificação posterior, `.tmp/kindle-pilot-25218/` não existia, a unidade temporária `R:` não estava mapeada e `C:\Data` não existia. O PDF final em `outputs/` permaneceu. Nenhum segredo foi escrito neste relatório.

## Prova de renderização portátil no Windows

O teste [`tests/test_portable_smoke.py`](../../tests/test_portable_smoke.py) foi escrito antes do gerador. A primeira execução falhou porque `scripts.portable_smoke` não existia. Após criá-lo, a importação da biblioteca WeasyPrint falhou por ausência de `libgobject-2.0-0`/Pango no Windows. O código foi ajustado para chamar o executável Windows **oficial** do WeasyPrint como processo local, com `--allowed-protocols file`; o teste passou.

Artefato de prova: [`artifacts/KindlePdfSmoke-win-x64.zip`](../../artifacts/KindlePdfSmoke-win-x64.zip), **83.288.446 bytes**, SHA-256 `06B4249857B7D791E9669D0A17C4E4C76B5CBA754859213BE23A11B2EA0C6F38`. Conteúdo descompactado: **175.724.948 bytes**, incluindo a licença do WeasyPrint. É uma prova de PDF, não a interface nem o conversor de livros.

Versões usadas: Python `3.12.14`, WeasyPrint `70.0`, PyMuPDF `1.28.2`, PyInstaller `6.22.3`, pytest `9.1.1`. O arquivo oficial `weasyprint-windows-onedir.zip` v70.0 tinha SHA-256 `AB1151F210B4E6BB7AA7A79E91A67E8DDB760094C107BFDA55241B6AAEFE7D53`.

Comandos relevantes, executados no diretório do projeto:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe pytest weasyprint pymupdf pyinstaller
Invoke-WebRequest -Uri 'https://github.com/Kozea/WeasyPrint/releases/download/v70.0/weasyprint-windows-onedir.zip' -OutFile '.tmp\weasyprint-windows-onedir-v70.0.zip'
Expand-Archive -LiteralPath '.tmp\weasyprint-windows-onedir-v70.0.zip' -DestinationPath '.tmp\weasyprint-v70' -Force
$env:WEASYPRINT_EXE=(Resolve-Path '.tmp\weasyprint-v70\onedir\weasyprint\weasyprint.exe').Path
.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp\pytest
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --name KindlePdfSmoke --add-data '.tmp\weasyprint-v70\onedir\weasyprint;weasyprint' scripts\portable_smoke.py
Copy-Item -LiteralPath '.tmp\weasyprint-v70\LICENSE' -Destination 'dist\KindlePdfSmoke\WEASYPRINT_LICENSE.txt'
Compress-Archive -LiteralPath 'dist\KindlePdfSmoke' -DestinationPath 'artifacts\KindlePdfSmoke-win-x64.zip' -Force
Expand-Archive -LiteralPath 'artifacts\KindlePdfSmoke-win-x64.zip' -DestinationPath '.tmp\relocated-smoke-v2'
Remove-Item Env:WEASYPRINT_EXE -ErrorAction SilentlyContinue
$env:PATH="$env:WINDIR\System32;$env:WINDIR"
& '.tmp\relocated-smoke-v2\KindlePdfSmoke\KindlePdfSmoke.exe' --output '.tmp\relocated-smoke-v2.pdf'
```

Última suíte: **2 testes aprovados** — geração de PDF e resolução do nome do renderizador por plataforma. O PDF gerado a partir do ZIP reconstruído tinha **1 página**, **7.310 bytes** e texto extraível `Teste portátil` mais um parágrafo. A página foi renderizada e inspecionada visualmente: título e parágrafo estão legíveis. O caminho `PATH` reduzido não comprova independência de todas as bibliotecas do sistema; somente um teste em Windows limpo faz essa comprovação.

## Pendências para encerrar a Fase 1

1. Avaliar sumário, capítulos e fidelidade editorial do volume jurídico de forma mais ampla. As páginas 101 e 251 do PDF foram inspecionadas visualmente; notas e tabelas exigem outra amostra porque não foram encontradas no EPUB jurídico testado.
2. Executar o pacote em Windows limpo (VM ou outra máquina) e registrar resultado. A verificação da opção Windows Sandbox exigiu elevação e não foi realizada.
3. Produzir e testar pacotes macOS/Linux em ambientes desses sistemas, caso permaneçam no escopo da primeira versão. Não atribuir suporte a eles com base no build Windows.
4. Antes de distribuição externa, completar inventário de licenças de todas as dependências incluídas no pacote. A licença principal do WeasyPrint foi incluída nesta prova.

## Fontes externas

- [WeasyPrint: instalação e requisitos nativos](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html).
- [WeasyPrint v70.0: executáveis oficiais Windows](https://github.com/Kozea/WeasyPrint/releases/tag/v70.0).
- [KindleUnpack: escopo de formatos sem DRM](https://github.com/kevinhendricks/KindleUnpack).
- [DeDRM_tools v10.0.32: suporte a MSKindle 1.0.25218](https://github.com/Satsuoni/DeDRM_tools/releases/tag/v10.0.32).
- [KFX Input: formatos, conversão e limitações](https://www.mobileread.com/forums/showthread.php?t=291290).
- [Calibre portátil para Windows](https://calibre-ebook.com/download_portable).
