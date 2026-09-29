# Fase 3 — extração e modelo intermediário

Data: 25/09/2026. Ambiente executado: Windows, Python 3.12.14. Escopo: EPUB, Kindle KF8/AZW3 e MOBI sem DRM, convertidos em memória para `BookModel`. Nenhum PDF foi produzido nesta fase. Os quatro livros comerciais diagnosticados na Fase 2 permaneceram fora do fluxo.

## Implementação entregue

- `unpack_book(input_path, work_dir) -> UnpackedBook` identifica o conteúdo, rejeita entradas protegidas ou incompatíveis, extrai EPUB em diretório novo e chama KindleUnpack v0.83 para KF8/MOBI com argumentos literais, sem shell. Em erro de extração, remove a saída parcial. O original permanece intacto.
- `prepare_book(unpacked) -> BookModel` lê metadados e ordem do spine no OPF, devolve capítulos com HTML/XHTML normalizado, recursos locais e avisos. O HTML legado passa por `html5lib`; nomes proprietários como `mbp:pagebreak` são normalizados para XML reutilizável. O limite do HTML legado é 64 MiB por item, pois o MOBI antigo pode concentrar o livro inteiro num item; XML e CSS usam limites menores.
- Recursos fora da pasta extraída e referências de carregamento remoto são recusados. A verificação cobre manifesto, atributos de capítulos, CSS externo e embutido e referências dentro de SVG; `base` e `srcset` são recusados porque alteram a resolução local ou permitem fontes adicionais. Referências ausentes viram aviso e não descartam o texto. A Fase 4 ainda deve usar um carregador de recursos que bloqueie rede no renderizador.
- KindleUnpack está incluído em `src/kindle_pdf/_vendor/KindleUnpack`, com fonte, licença GPLv3 e proveniência. O wheel local inclui esses arquivos e `html5lib==1.1`. O licenciamento e os pacotes finais para distribuição serão tratados na Fase 8.

## Amostras reais

As três variantes foram obtidas da [página de *Dom Casmurro* no Project Gutenberg](https://www.gutenberg.org/ebooks/55752). O [registro de formatos do projeto](https://www.gutenberg.org/help/bibliographic_record.html) explica os downloads sem DRM. Os arquivos de teste e as saídas extraídas ficaram somente em `.tmp/`.

| Entrada | SHA-256 | Formato detectado | Itens no spine | Recursos | Avisos |
| --- | --- | --- | ---: | ---: | --- |
| EPUB3, 222.389 bytes | `847B26BBC6BFEFCF7CC323A94EACEFD3C7A9657E66749CB360B77B34A3E994FD` | `epub` | 5 | 6 | 0 |
| Kindle KF8, 366.154 bytes | `D19B5132D03681ACBC2C638B2A9CF89C6C254F64B870991EB163FFA84B05A0A7` | `azw3` | 7 | 5 | 1 |
| Kindle antigo, 348.416 bytes | `FF083F5F946B2F3AEC4CE45E526312BF133406D9D188F0A38932AC122AABC576` | `mobi` | 1 | 2 | 0 |

Os três modelos apresentaram título `Dom Casmurro` e idioma `pt`. Cada capítulo produzido voltou a ser analisado como XML sem erro após a normalização. A ordem inicial dos títulos no EPUB e KF8 foi capa, título e prólogo, conforme seus spines. No MOBI antigo, o OPF gerado pelo KindleUnpack contém um único HTML e não fornece título para esse item; por isso o modelo registra um capítulo com `title=None`. A Fase 4 poderá paginar o texto, mas não deve prometer divisão editorial que essa fonte não descreve.

O aviso do KF8 identifica `mobi8/OEBPS/Text/5395069773648315329_cover02.jpg`, referenciado no pacote mas ausente na extração. O EPUB e o MOBI antigo não geraram avisos. As amostras reais não apresentaram marcadores `noteref` nem `<aside>`; preservação de nota interna, imagem relativa e ordem fora da sequência alfabética foram comprovadas pela fixture sintética. Isso limita a validação de notas reais antes da Fase 4.

## Testes e pacote

A suíte focada começou com falha de importação e depois falhou nos stubs `NotImplementedError`; novos testes de regressão também falharam antes dos ajustes de HTML legado, SVG, CSS embutido, `base` e `srcset`. Resultado final: **35 testes aprovados** na suíte completa, incluindo detecção da Fase 2, fixture com spine fora de ordem, nota e imagem, proteção de caminho/URL, HTML legado grande, normalização dos marcadores MOBI e limpeza de saída parcial.

O wheel `kindle_pdf-0.3.0-py3-none-any.whl` foi construído localmente e instalado em ambiente virtual isolado. A presença do script KindleUnpack, código fonte e licença foi conferida dentro do wheel. A partir da instalação isolada, sem `KINDLEUNPACK_SCRIPT`, as amostras KF8 e MOBI antigo foram extraídas novamente com os mesmos totais de capítulos, recursos e avisos. Isso verifica o pacote Python no Windows; ainda não valida aplicativo portátil, macOS ou Linux.

O [KindleUnpack v0.83](https://github.com/kevinhendricks/KindleUnpack/releases/tag/v083) foi copiado sem alterações do ZIP de origem, SHA-256 `4EC7942D35E774BB1C9AF06D4B9E8E979E2673888082824EA3654B059E7E14EE`. Sua licença GPLv3 acompanha o código. Nenhum dado ou chave do ensaio sensível da Fase 1 foi necessário.
