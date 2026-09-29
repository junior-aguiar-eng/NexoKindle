# KindlePDF: selecionar livro e converter

Data: 26/09/2026. Estado em 29/09/2026: implementação e testes locais concluídos; distribuição a terceiros ainda depende de revisão de licenças e teste em Windows limpo. O seletor automático na instalação Kindle ativa aguarda livros baixados nessa instalação.

## Resultado esperado

Em um Windows compatível, com o aplicativo Kindle instalado e o livro já baixado nessa instalação, a pessoa abre o KindlePDF, escolhe um livro e clica em **Converter**. O aplicativo decide qual rota usar, gera um PDF pesquisável, valida o resultado e oferece **Abrir PDF**. Não aparecem campos de arquivador, Calibre, plugin, unidade temporária, chave ou pasta de saída no fluxo comum. A pessoa não instala Python nem procura três ferramentas separadas.

O aplicativo continua aceitando EPUB, MOBI e AZW3 locais compatíveis sem proteção. A integração com Kindle para Windows é específica dessa plataforma e não pressupõe que uma conta Amazon esteja configurada no KindlePDF. O usuário entra na própria conta no aplicativo Kindle.

## Tela e interação

A tela principal tem **Selecionar livro**, **Converter**, progresso, resultado e **Abrir PDF**. No Windows, **Selecionar livro** apresenta os arquivos principais dos livros já baixados pelo Kindle, reunidos em uma lista; a pessoa não percorre pastas internas `_EBOK`. O app mostra o nome legível quando houver metadados locais confiáveis; quando não houver, mostra o identificador do arquivo sem inventar um título. **Outro arquivo** abre o seletor comum para EPUB, MOBI, AZW3 ou outros arquivos locais compatíveis. Selecionar outro livro substitui a seleção atual. A conversão em lote existente permanece disponível na CLI; não ocupa a tela principal.

O destino padrão é uma pasta local de PDFs do usuário fora da instalação do aplicativo. O caminho pode ser alterado em **Configurações**. Para a rota protegida, o aplicativo verifica antes de iniciar que o destino não está dentro de uma pasta conhecida de sincronização; se não puder garantir isso, explica o risco e pede outro destino. O resultado exibe **PDF pronto**, **Revisão necessária** ou uma falha explicada em linguagem comum. Não afirma sucesso quando o formato, a proteção ou a validação impedirem a conversão.

## Decisão da rota

`detect_book` determina a rota pelo conteúdo, sem confiar apenas na extensão. Para um livro sem proteção e com formato suportado, a GUI chama o núcleo com `ConvertOptions()`; não inicia ferramentas externas. Para o contêiner Kindle protegido já suportado, a GUI fornece o adaptador Windows validado e mantém a pasta original `_EBOK` intacta. O núcleo existente executa extração, preparação, renderização, validação e publicação. Formato desconhecido, arquivo isolado sem os demais componentes do livro ou versão incompatível recebem estado explícito. Não há uma tentativa silenciosa de descriptografia para todo arquivo.

As ferramentas da rota protegida são resolvidas por um componente interno, a partir de caminhos relativos ao pacote instalado e de metadados de versão e hash. Não são gravados caminhos absolutos do computador do desenvolvedor no produto. A GUI não expõe nem exige preencher três campos. A compatibilidade continua vinculada às versões efetivamente validadas; o aplicativo Kindle pode atualizar e invalidar essa rota. O programa deve detectar a incompatibilidade antes da conversão quando possível e explicar o que falta.

## Instalador e distribuição

O objetivo é um instalador Windows único que inclua o aplicativo e as ferramentas necessárias à rota protegida, configuradas automaticamente e sem instalação global separada. Esse artefato só pode ser chamado de pronto para terceiros após: confirmar a licença de redistribuição do arquivador específico; cumprir as obrigações de Calibre, KFX Input e todas as dependências do aplicativo; incluir avisos, licenças e fontes/ofertas de fonte exigidos; validar os hashes dos binários; e testar instalação, conversão e desinstalação em um Windows limpo. O pacote não contém livros, credenciais, chaves ou materiais intermediários. Se a redistribuição de algum componente não puder ser autorizada, não será apresentada uma distribuição incompleta como se atendesse ao fluxo de um clique.

O Kindle para Windows e os livros baixados são pré-requisitos do computador de destino. O instalador não instala o Kindle, não acessa a conta Amazon e não promete compatibilidade com todos os livros. macOS, Linux e Kindle físico dependem de adaptações e validação próprias; a arquitetura do núcleo permanece independente da origem do arquivo.

## Privacidade e falhas

A rota protegida conserva chaves e arquivos intermediários apenas na área temporária local da conversão e remove a área após o término normal. Logs e manifesto não registram chaves, tokens, conteúdo do livro, KFX-ZIP nem EPUB intermediário. O original não é modificado. Falha, cancelamento ou incompatibilidade não publicam um PDF como se fosse válido. A interface não apresenta exceções brutas das ferramentas externas, pois elas podem conter dados sensíveis.

## Validação necessária

- Teste de GUI: um EPUB local aciona apenas a rota básica; um contêiner Kindle protegido selecionado aciona apenas a rota Windows; arquivo não suportado recebe explicação e não produz PDF.
- Teste de configuração: a instalação resolve as ferramentas pelo próprio pacote em um diretório diferente do usado no build; caminhos do desenvolvedor não aparecem na interface, nos logs ou no manifesto.
- Teste de privacidade: original preservado; temporários removidos na conclusão normal; nenhum segredo ou intermediário no manifesto, logs ou instalador.
- Teste de uso real: selecionar e converter um livro previamente autorizado pelo usuário por meio do executável instalado, inspecionar PDF e confirmar que a janela permanece aberta sem PowerShell.
- Teste de distribuição: instalar em Windows limpo, sem Python ou Calibre prévio, converter amostras sem proteção e um livro autorizado da rota Kindle compatível, e desinstalar. Registrar versão do Kindle e limites do ensaio.

## Fora do escopo desta mudança

Login Amazon dentro do KindlePDF, download de livros, suporte universal a todas as versões do Kindle, remoção de proteção de livros sem autorização, instalação global de ferramentas, garantia editorial integral do PDF e builds macOS/Linux não testados.
