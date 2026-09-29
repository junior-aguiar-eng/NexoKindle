# Matriz de aceitação dos pacotes

| Ambiente | Build | CLI portátil | GUI portátil | PDF sem Python | Máquina limpa | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| Windows 11 x64, estação de desenvolvimento | ZIP com executáveis separados; instalador Inno 7 compilado e atualização local executada | MOBI sintético e livro Kindle autorizado convertidos pelo bundle corrigido; EPUB também validado no pacote anterior | `KindlePDF.exe` tem subsistema gráfico PE 2 e permaneceu ativo após o PowerShell lançador encerrar, inclusive na cópia instalada; `KindlePDF-CLI.exe` tem subsistema de console PE 3 | MOBI: 1 página; Kindle: 230 páginas, todas com texto no bundle corrigido; EPUB: 2 páginas com revisão no pacote anterior | Não | Desinstalação e distribuição pendentes |
| Windows x64 limpo | Não | Não | Não | Não | Não | Pendente |
| macOS | Não | Não | Não | Não | Não | Pendente |
| Linux | Não | Não | Não | Não | Não | Pendente |

## Candidato de conversão em um clique, 26/09/2026

| Ambiente | GUI simples | Ferramentas no pacote | Livro protegido | Instalação | Distribuição |
| --- | --- | --- | --- | --- | --- |
| Windows 11 x64 desta estação | Captura nativa da GUI em ambiente Python e teste da escolha automática | Arquivador, Calibre Portable e KFX Input incluídos em `dist/KindlePDF/tools` e no instalador candidato | Livro autorizado: 230 páginas, todas com texto, pela GUI em ambiente Python e pelo executável CLI empacotado | Candidato compilado; atualização local descrita no relatório de 26/09 | Pendente: licenças e Windows limpo |
| Windows x64 limpo | Não testado | Não testado | Não testado | Não testado | Não liberado |

Em 29/09/2026, o candidato foi reconstruído após a revisão da GUI, da escolha do pacote Kindle e dos hashes das ferramentas. A suíte terminou com 108 testes aprovados; o bundle reconverteu o EPUB sintético e o livro autorizado com texto em todas as páginas, sem temporários remanescentes. O instalador atualizou a cópia por usuário, cujos executáveis e ferramentas conferem com o bundle. A janela instalada abriu e permaneceu ativa após o PowerShell lançador terminar. A conversão real pela GUI instalada e a instalação em Windows limpo ainda não foram executadas; não há liberação para terceiros.

O aplicativo Kindle ativo nesta estação está na versão `1.0.25218.0` x64, mas sua pasta de conteúdo está vazia. O ensaio protegido usou a cópia local do livro já autorizado, preservando o hash da entrada. A ausência de livros na pasta ativa significa que a lista **Selecionar livro** ficará vazia até que o usuário baixe os títulos de novo no Kindle. O botão **Outro arquivo** permite escolher a cópia local.

O ZIP anterior foi descompactado em outra pasta e executado com `PATH` reduzido a Windows e System32, sem `WEASYPRINT_EXE` nem `PYTHONPATH`. O novo ZIP também foi extraído em outra pasta: o diagnóstico MOBI funcionou e a GUI permaneceu ativa após o PowerShell lançador terminar. A correção do subsistema gráfico foi ensaiada no bundle reconstruído nesta estação, inclusive conversão MOBI pela nova CLI e do livro Kindle autorizado com 230 páginas de texto. O hash da origem permaneceu igual, sem pasta temporária remanescente nem marcadores de segredo no manifesto. O instalador atualizou a cópia no perfil do usuário, com atalho para o executável gráfico correto; os executáveis instalados coincidiram com os do bundle e a GUI instalada permaneceu ativa após o PowerShell lançador terminar. Isso não substitui uma VM sem Python, uma inspeção visual interativa da GUI ou monitoramento de rede. Os scripts macOS/Linux exigem um renderizador nativo já empacotado e não foram executados. A distribuição depende da revisão das obrigações de licença dos componentes incluídos.

Evidências e hashes: [relatório da Fase 8](2026-09-25-phase8-release.md).
