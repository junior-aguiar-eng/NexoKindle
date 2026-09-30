# Operabilidade e confiança — KindlePDF 0.6.4

Análise de 29/09/2026 do checkout `C:\Users\Boni Jr\Desktop\Extração Kindle`, branch `main`, HEAD `a4870a0`, remoto `junior-aguiar-eng/NexoKindle`. O checkout estava limpo antes da análise. Escopo: comportamento existente, sem funcionalidades novas e sem alterações no código do app, instalação, build, publicação ou execução do arquivador real.

## Caso observado por Boni

O arquivo `B0DLBS3HMV_EBOK.azw` da biblioteca local possui o mesmo SHA-256 registrado no manifesto de `Vigiar e punir`. O resultado é `review_required`, com o diagnóstico `Nota ausente no texto extraído.`. O arquivo publicado está em `%LOCALAPPDATA%\KindlePDF\PDFs\review\Vigiar e punir--b0db62894ece2f91--21d81ad700.pdf`.

Inspeção atual: 204 páginas, todas com texto extraível, 754.140 caracteres somados após remoção de espaços nas extremidades por página e 37 entradas no sumário PDF. Esses números confirmam a existência de uma conversão legível; não demonstram preservação integral do conteúdo, das notas ou da ordem de leitura. A origem não foi novamente extraída nesta análise.

A mensagem da imagem corresponde à validação posterior à geração do PDF. O app não baixa livros: lê arquivos já baixados pelo Kindle. Outros livros locais também têm esse diagnóstico, enquanto há resultados `converted` na mesma pasta.

## Achados priorizados

| Prioridade | Problema confirmado | Consequência e correção restrita ao comportamento atual |
| --- | --- | --- |
| Alta | `validate.py:70` monta o texto de notas com espaços entre todos os fragmentos de `itertext()`. No caso `<aside>Alpha <em>beta</em>.</aside>`, espera `Alpha beta .`, embora o PDF real contenha `Alpha beta.`. | Nota integralmente presente é classificada como ausente. Corrigir a reconstrução e comparação do texto, com regressões que distingam formatação e perda real; manter ressalvas quando houver dúvida. O defeito foi reproduzido com WeasyPrint, mas ainda não foi demonstrado como causa exclusiva do caso de Vigiar e punir. |
| Alta | `validate.py:37-48` verifica texto global, títulos e sumário, sem verificar cobertura do corpo dos capítulos. Um PDF sintético contendo apenas `Chapter` e o marcador `1. Chapter` recebe `valid` contra um modelo que contém corpo ausente. | `converted` não assegura conteúdo preservado. Aprimorar o critério de aprovação existente para detectar omissões relevantes no corpo, com tolerância explícita a paginação e formatação. |
| Alta | `gui.py:402-414` só acrescenta PDFs ao mapa de resultados; não invalida o PDF anterior quando uma nova tentativa retorna revisão ou falha. | Reproduzido: após sucesso seguido de `review_required`, `Abrir PDF` segue habilitado e vinculado ao arquivo anterior. Invalidar o resultado anterior no início da nova tentativa e nos estados sem PDF aprovado. |
| Alta | `gui.py:209` oculta permanentemente a tabela que contém diagnósticos e caminhos. A mensagem de revisão não apresenta esses dados; o caminho `review_path` também não é exibido. | O usuário sabe apenas que o resultado exige revisão, sem motivo nem localização. Exibir de forma concisa o motivo e o caminho já existentes, preservando a distinção entre resultado aprovado e arquivo para conferência. |
| Média | `gui.py:353-386` deixa `Selecionar livro` e `Configurações` habilitados durante a conversão. O seletor pode alterar o rótulo, enquanto `clear_sources` e `add_paths` recusam alterar a seleção durante o trabalho. | A janela pode identificar um livro diferente daquele em processamento; uma troca de destino também só afeta a próxima tentativa. Aplicar o bloqueio de controles já utilizado aos dois botões. Estado habilitado reproduzido; o desencontro de rótulo decorre do fluxo do seletor. |
| Média | `gui.py:302-306` permite selecionar vários arquivos no diálogo, mas utiliza somente `files[0]`. Arrastar arquivos/pastas, por outro lado, aceita múltiplos itens, com resultados individuais ocultos. | O contrato visível é inconsistente. Ajustar o diálogo à seleção de um livro ou processar a seleção conforme o contrato já existente; informar resultados de cada item quando houver vários. Não criar nova modalidade de lote. |
| Média | A retomada em `batch.py` verifica hashes do PDF e do arquivo principal, mas a assinatura identifica o adaptador pela classe. Não inclui o conteúdo dos arquivos auxiliares do livro protegido nem as versões efetivas de todas as ferramentas. | Mudanças nos auxiliares ou ferramentas podem reutilizar resultado antigo. Corrigir a identidade do checkpoint existente; alterações futuras no validador também precisam invalidar aprovações anteriores mediante revisão de `PIPELINE_VERSION`. Limitação confirmada no código, sem ensaio de alteração dos auxiliares nesta análise. |

## Verificação executada

- `.venv\Scripts\python.exe -m pytest -q --basetemp .tmp/pytest-operability-audit`, com `WEASYPRINT_EXE` apontado para o v70 no bundle: **118 aprovados, 1 ignorado, 1 aviso** em 82,15 s. O aviso é a depreciação de `imghdr` no código vendorizado.
- Sonda `.tmp/audit_operability.py`: reproduziu nota presente com revisão, corpo ausente com aprovação, PDF anterior mantido após revisão, tabela oculta e controles habilitados durante trabalho. Qt em modo `offscreen`; isso verifica estados e sinais, não a aparência da janela instalada.
- Leitura do manifesto e inspeção do PDF existente com PyMuPDF; correlação do livro por SHA-256.
- Ruff global, com configuração do projeto e regras adicionais herdadas do ambiente: 34 apontamentos predominantemente de estilo. O ambiente `.venv` não contém os módulos Ruff/mypy; não se confirmou uma execução útil de mypy nesta análise. Esses resultados não são tratados como falhas funcionais nem justificam reformatação geral.

## Avaliação

O núcleo já possui publicação sem sobrescrita, validação antes da publicação e separação de resultados em `review/`. O principal déficit confirmado está na confiabilidade do veredito e na comunicação do resultado. Priorizar a comparação de notas, a invalidação de resultados antigos e a apresentação dos diagnósticos; depois reforçar a cobertura de conteúdo e a coerência de seleção/checkpoint.

Não converter automaticamente `review_required` em sucesso nem diminuir a exigência de validação para fazer mais livros parecerem aprovados. O caso real exige comparar as notas da origem com o PDF antes de concluir perda ou falso alarme. Máquina limpa, conversão pela GUI instalada e comportamento após encerramento forçado continuam fora da evidência produzida aqui.
