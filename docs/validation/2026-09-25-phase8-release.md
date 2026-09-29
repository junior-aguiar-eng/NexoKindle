# Fase 8 — candidato portátil e aceitação

Data: 25/09/2026. Ambiente disponível: Windows 11 x64. O checkout local não é um repositório Git. O ZIP é um **candidato local**, sem publicação, instalação global ou distribuição a terceiros.

## Construção

`requirements.in` fixa as dependências diretas de build, teste e interface; `requirements.txt` fixa a resolução transitiva universal. `scripts/build_windows.ps1` verifica o SHA-256 `AB1151F210B4E6BB7AA7A79E91A67E8DDB760094C107BFDA55241B6AAEFE7D53` do ZIP oficial WeasyPrint 70.0, usa ambiente Python local, constrói com PyInstaller 6.22.3 em modo pasta e inclui licenças disponíveis. O bundle corrigido tem `KindlePDF.exe` com subsistema gráfico para a GUI e `KindlePDF-CLI.exe` com subsistema de console para comandos e o processo filho do KindleUnpack. `scripts/verify_windows_bundle.py` impede empacotar novamente a GUI como aplicação de console.

O primeiro build gerou `ImportError` ao importar `QtCore`: o PyInstaller coletara `icuuc.dll` 78.3 de uma instalação de Poppler presente no `PATH` da estação. A remoção experimental dessa DLL do bundle fez a CLI iniciar. O script final de build restringe o `PATH` durante a análise, e o ZIP final não contém essa DLL estranha. Esta foi uma falha de contaminação do ambiente de build, não do EPUB.

O primeiro ZIP tinha **113.201.581 bytes**, SHA-256 `C196D28485B66E09FDA7BA630F01519F50EAF77C8F4EE70094600F917A9D9C17`; seu `KindlePDF.exe` era de console (subsistema PE 3). Ao fechar a janela do PowerShell, o usuário observou que a GUI se encerrava. Esse candidato foi substituído. O script padrão criou um ambiente novo em `.tmp` a partir de `requirements.txt`; o build corrigido reutilizou esse ambiente fixado. O teste de relocação em outra pasta com `PATH` restrito a Windows/System32, sem `PYTHONPATH` nem `WEASYPRINT_EXE`, pertence ao candidato anterior e precisa ser repetido para o novo ZIP antes de afirmar independência em máquina limpa.

## Matriz de conversão local

| Entrada | SHA-256 da entrada | Diagnóstico | Resultado do primeiro ZIP | PDF |
| --- | --- | --- | --- | --- |
| EPUB sintético com texto e SVG | `4c6ca38a054170607812af832ed7100e69a66a5a14bf8bf7a37ed2daf72c2f91` | `supported`, EPUB | `review_required` por SVG | 2 páginas, 2 com texto |
| MOBI sintético gerado localmente com Calibre a partir do EPUB acima | `32380d228b2ac65e1e7f81b098e1ad5cc2cef125118fa677782a2a55075b54f1` | `supported`, MOBI | `converted`; exercitou KindleUnpack no executável congelado | 1 página, 1 com texto |
| “Código Penal Militar e Código de Processo Penal Militar”, amostra real autorizada | `5b9804c68a4ea1d98761ab0b1b6da124ae252d832231c668cc5c2d21fb978e35` | `protected_or_unreadable` na Fase 2 | `converted` pelo adaptador Windows com as ferramentas externas já preparadas | 230 páginas, 230 com texto |

O PDF real gerado pelo executável do primeiro ZIP teve SHA-256 `48453510037cee03e031c6eb713822429b48588f612f2016174ecfcd806260f7`. Execuções sucessivas tiveram hashes de PDF diferentes e as mesmas 230 páginas; o PDF não é binariamente determinístico neste fluxo. Essa conversão levou **43 segundos** nesta estação. As páginas 1, 101 e 230 foram renderizadas e examinadas no primeiro ensaio do candidato: capa, texto legal, links e página final estão legíveis. Isto não verifica a equivalência editorial integral. O hash do `.azw` original permaneceu igual. A saída não continha pasta temporária `.kindle-pdf-*`; o manifesto não continha marcadores de chaves, EPUB intermediário ou KFX-ZIP; `C:\Data` não existia e não restou unidade `SUBST` entre `R:` e `Z:`. Esses são resultados da conclusão normal do ensaio, não garantias de apagamento seguro após interrupção forçada.

O executável do ZIP anterior iniciou a GUI e permaneceu ativo por quatro segundos com `QT_QPA_PLATFORM=offscreen`, após o que o processo foi encerrado pelo teste. Esse ensaio não detectou que o arquivo era de console. No bundle corrigido, a verificação do cabeçalho PE confirmou subsistema **2** (Windows GUI) em `KindlePDF.exe` e **3** (Windows console) em `KindlePDF-CLI.exe`; a GUI permaneceu ativa por quatro segundos em modo Qt offscreen, e a nova CLI converteu o MOBI sintético em PDF. A interação visual do executável empacotado não foi ensaiada; a GUI em ambiente Python foi ensaiada na Fase 7. Não houve monitoramento de rede nesta fase. A matriz completa dos demais livros da Fase 1 e seus tempos de conversão ainda não foram repetidos.

## Instalador Windows

Após a pergunta do usuário sobre a entrega em ZIP, `installer/KindlePDF.iss` e `scripts/build_installer_windows.ps1` passaram a compilar **o mesmo bundle** em um instalador por usuário. O script usa o Inno Setup 7.1.0 já instalado nesta estação, com assistente `modern dynamic`, `PrivilegesRequired=lowest`, destino `{localappdata}\Programs\KindlePDF`, atalho no menu Iniciar e desinstalador. Não instala Python nem incorpora as ferramentas externas do fluxo protegido.

O instalador anterior tinha **78.942.820 bytes**, SHA-256 `FF014AA44EDA7AAD0FF65D3022A0860B07165FE699E527FD57E9E9001EAD955B`, e incluía a GUI compilada como console. Foi substituído. A assinatura Authenticode estava `NotSigned`. O compilador local indicou `Non-commercial use only`; um uso comercial exige verificar a licença do Inno Setup. **Instalação, atualização, execução após instalar e desinstalação não foram testadas**. A compilação não equivale a aceite em máquina limpa, assinatura ou autorização de distribuição.

## Correção do vínculo ao PowerShell

O relato do usuário revelou um defeito que o ensaio Qt offscreen anterior não cobria: `KindlePDF.exe` tinha subsistema PE **3** (console), e a GUI se encerrava quando o PowerShell era fechado. `KindlePDF-Windows.spec` agora produz dois lançadores na mesma pasta: `KindlePDF.exe` com subsistema **2** (Windows GUI) e `KindlePDF-CLI.exe` com subsistema **3** (console). O processo KindleUnpack congelado usa o segundo executável, com a janela auxiliar oculta. O build verifica os dois cabeçalhos PE antes de criar o ZIP.

O novo executável gráfico, extraído do ZIP final, continuou ativo por quatro segundos **depois que o processo PowerShell que o iniciou terminou**. O teste usou `QT_QPA_PLATFORM=offscreen`; ele confirma a independência do processo, mas não substitui uma inspeção visual interativa. A nova CLI converteu o MOBI sintético em PDF. Ela reconverteu o livro Kindle autorizado: `converted`, **230 páginas, 230 com texto**, SHA-256 da origem `5B9804C68A4EA1D98761AB0B1B6DA124AE252D832231C668CC5C2D21FB978E35` sem alteração e nenhuma pasta `.kindle-pdf-*` restante no destino. Esta execução unitária não produz manifesto; a ausência dos marcadores `keys.k4i`, `books.keyfile`, `converted.epub` e `kfx-zip` no manifesto foi verificada no ensaio em lote anterior. Esses resultados são do bundle corrigido na estação de desenvolvimento; o novo ZIP extraído foi usado para diagnóstico MOBI e teste de permanência da GUI, mas a conversão protegida não foi repetida a partir da pasta extraída.

O [ZIP corrigido](../../artifacts/KindlePDF-win-x64-candidate.zip) tem **117.186.768 bytes**, SHA-256 `A1434A6296E10E531266B63AC3576B3E9EE1EC4A91985508F8EECB5FEE923DE3`. Suas **495 entradas** não contêm livros, PDFs, arquivos de chave nem as ferramentas externas do fluxo protegido. O [instalador recompilado](../../artifacts/KindlePDF-Setup-win-x64-candidate.exe) tem **78.993.754 bytes**, SHA-256 `11CB76A9ADDD91A78277D8A6B1474BD620EBB8BBABF3612C867482B457FB7B2A` e está `NotSigned`. A suíte fechou com **91 testes aprovados**; `mypy` verificou 15 arquivos de código próprio sem erros, e Ruff aprovou os arquivos alterados.

Após autorização do usuário, o instalador atualizou a cópia em `%LOCALAPPDATA%\Programs\KindlePDF`. `KindlePDF.exe` e `KindlePDF-CLI.exe` instalados, o guia e a matriz coincidem por SHA-256 com o bundle final; os subsistemas PE são respectivamente **2** e **3**. O atalho `KindlePDF.lnk` do menu Iniciar aponta para o executável gráfico instalado. No ensaio final, o processo PowerShell lançador terminou e a GUI instalada permaneceu ativa por quatro segundos em modo Qt offscreen. O teste encerrou intencionalmente apenas a instância de ensaio. A desinstalação, a inspeção visual interativa e uma máquina Windows limpa ainda não foram ensaiadas.

A limpeza da pasta de trabalho intermediária criada pelo pipeline foi confirmada. Inicialmente, o PDF final do ensaio permaneceu em `.tmp/gui-regression-protected`, pois a revisão automática da estação rejeitou sua exclusão (`blocked by policy`). O usuário informou que o apagou manualmente; em verificação posterior, tanto o PDF quanto a pasta de ensaio estavam ausentes. O arquivo nunca integrou o ZIP nem o instalador.

## Verificações de código e pacote

- Suíte completa: `91 passed`, um aviso de depreciação de `imghdr` no KindleUnpack v0.83, em Python 3.12.
- `mypy` 1.18.2: nenhum erro em 14 arquivos de código próprio; código de terceiro excluído.
- Ruff 0.13.2: nenhuma ocorrência no código próprio e nos testes da nova rota; código de terceiro excluído.
- Inspeção do primeiro ZIP: 494 entradas, sem `.azw`, `.mobi`, `.epub`, `.pdf`, `.k4i` ou `.keyfile`, e sem o arquivador externo, Calibre ou ZIP KFX Input. O pacote inclui um guia portátil e os arquivos de licença encontrados no ambiente de build; o inventário ainda é incompleto.

## Licenças e condições de distribuição

O inventário aponta [PyMuPDF sob AGPL ou licença comercial](https://pymupdf.readthedocs.io/en/latest/faq/index.html), [KindleUnpack sob GPLv3](https://github.com/kevinhendricks/KindleUnpack), [PySide6 sob LGPLv3/GPLv3 ou licença comercial](https://doc.qt.io/qtforpython-6/), e [WeasyPrint sob BSD 3-Clause](https://github.com/Kozea/WeasyPrint/blob/main/LICENSE). Os arquivos de licença encontrados no ambiente de build foram copiados ao ZIP. A revisão independente constatou que os metadados locais do PySide6 fornecem somente `LicenseRef-Qt-Commercial.txt`, sem o texto LGPL/GPL correspondente; também falta o inventário completo dos binários transitivos. Permanecem abertas a análise das obrigações aplicáveis ao aplicativo, a definição de licença do código próprio e a análise específica das ferramentas externas que **não** acompanham o pacote. Portanto, a existência do ZIP local não autoriza distribuição.

Os scripts macOS/Linux estão preparados para aceitar um build nativo do WeasyPrint fornecido por caminho; não foram executados nem há pacote dessas plataformas. Faltam Windows limpo, validação visual interativa do executável, teste de rede e repetição da matriz de todos os exemplares da Fase 1. A [matriz de aceitação](release-matrix.md) permanece aberta.
