# KindlePDF — candidato Windows x64

Abra `KindlePDF.exe` pelo Explorador ou menu Iniciar, sem PowerShell. No ZIP, mantenha o aplicativo, `_internal` e `tools` juntos. Para usar o terminal:

```powershell
.\KindlePDF-CLI.exe diagnosticar "C:\livros\livro.epub"
.\KindlePDF-CLI.exe converter "C:\livros\livro.epub" --saida "C:\pdfs"
```

Na interface, clique em **Selecionar livro** para escolher um livro já baixado no Kindle para Windows, ou em **Outro arquivo** para um EPUB, MOBI ou AZW3 local. Clique em **Converter** e depois em **Abrir PDF**. O destino padrão é `%LOCALAPPDATA%\KindlePDF\PDFs`; **Configurações** permite alterá-lo. Os PDFs que precisam de inspeção ficam na subpasta `review`. A origem não é alterada.

O candidato local completo inclui o arquivador validado, Calibre Portable e KFX Input em `tools`, e a interface escolhe a rota protegida automaticamente. O Kindle precisa estar instalado, com o livro baixado no computador e a conta configurada no próprio Kindle. O KindlePDF não acessa a conta Amazon nem baixa livros. A combinação protegida foi validada apenas com Kindle para Windows `1.0.25218.0` x64.

Se o Kindle tiver cache de chaves `PCPKSP`, o arquivador tentará copiá-lo para o perfil do Windows. O KindlePDF só executa essa rota quando nenhum arquivo existente seria sobrescrito; depois remove as cópias verificadas. Se houver colisão, interrompe a conversão e não cria PDF. O candidato ainda não foi testado com o livro do outro PC que motivou esta mudança. Um encerramento forçado pode deixar cópias no perfil; não apague nem mova o cache original do Kindle para tentar contornar uma falha.

O aplicativo foi testado somente na estação Windows 11 de desenvolvimento. A distribuição externa depende de licença de redistribuição comprovada para o arquivador, inventário das demais dependências e teste em Windows limpo. Os arquivos de licença localizados estão em `LICENSES` e no Calibre, mas o inventário ainda é incompleto; a matriz está em `RELEASE-MATRIX.md`.
