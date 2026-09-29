param(
    [string]$Python = "",
    [string]$Archiver = "",
    [string]$CalibreDir = "",
    [string]$KfxInputZip = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
if (-not ($Archiver -and $CalibreDir -and $KfxInputZip)) {
    throw "Informe arquivador, Calibre Portable e KFX Input para gerar o candidato completo."
}
if (-not $Python) {
    $buildVenv = Join-Path $root ".tmp\phase8-build-venv"
    uv venv --python 3.12 $buildVenv
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar ambiente local." }
    $Python = Join-Path $buildVenv "Scripts\python.exe"
    uv pip sync requirements.txt --python $Python
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências fixadas." }
}
$pythonPath = (Resolve-Path $Python).Path
uv pip install --python $pythonPath --no-deps --editable .
if ($LASTEXITCODE -ne 0) { throw "Falha ao vincular o código atual ao ambiente local de build." }
$sourceCheck = (& $pythonPath -c "from pathlib import Path; import kindle_pdf.gui as g; print('ok' if Path(g.__file__).resolve() == Path('src/kindle_pdf/gui.py').resolve() else 'stale')").Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCheck -ne "ok") {
    throw "O build está importando uma cópia antiga da GUI."
}
$rendererArchive = Join-Path $root ".tmp\weasyprint-windows-onedir-v70.0.zip"
$rendererRoot = Join-Path $root ".tmp\weasyprint-v70"
$renderer = Join-Path $rendererRoot "onedir\weasyprint"
$expected = "AB1151F210B4E6BB7AA7A79E91A67E8DDB760094C107BFDA55241B6AAEFE7D53"

if (-not (Test-Path -LiteralPath $rendererArchive)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $rendererArchive) | Out-Null
    Invoke-WebRequest -Uri "https://github.com/Kozea/WeasyPrint/releases/download/v70.0/weasyprint-windows-onedir.zip" -OutFile $rendererArchive
}
if ((Get-FileHash -LiteralPath $rendererArchive -Algorithm SHA256).Hash -ne $expected) {
    throw "Hash do WeasyPrint v70 divergente."
}
if (-not (Test-Path -LiteralPath (Join-Path $renderer "weasyprint.exe"))) {
    Expand-Archive -LiteralPath $rendererArchive -DestinationPath $rendererRoot -Force
}
$previousPath = $env:PATH
try {
    # Prevent an unrelated ICU DLL on the workstation PATH from entering Qt's bundle.
    $env:PATH = "$env:WINDIR\System32;$env:WINDIR"
    & $pythonPath -m PyInstaller --noconfirm --clean KindlePDF-Windows.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha no PyInstaller." }
} finally {
    $env:PATH = $previousPath
}

$bundle = Join-Path $root "dist\KindlePDF"
& $pythonPath scripts\verify_windows_bundle.py $bundle
if ($LASTEXITCODE -ne 0) { throw "O bundle Windows não passou na verificação dos subsistemas." }
New-Item -ItemType Directory -Force -Path (Join-Path $bundle "LICENSES") | Out-Null
Copy-Item -LiteralPath (Join-Path $rendererRoot "LICENSE") -Destination (Join-Path $bundle "LICENSES\WeasyPrint-LICENSE")
Copy-Item -LiteralPath "src\kindle_pdf\_vendor\KindleUnpack\COPYING.txt" -Destination (Join-Path $bundle "LICENSES\KindleUnpack-COPYING.txt")
$sitePackages = Join-Path (Split-Path $pythonPath -Parent) "..\Lib\site-packages"
$sitePackages = (Resolve-Path $sitePackages).Path
foreach ($pattern in @("pymupdf-*.dist-info", "pyside6-*.dist-info", "pyside6_essentials-*.dist-info", "pyside6_addons-*.dist-info", "shiboken6-*.dist-info", "html5lib-*.dist-info", "tinycss2-*.dist-info")) {
    Get-ChildItem -Path (Join-Path $sitePackages $pattern) -Directory | ForEach-Object {
        $licenseDir = Join-Path $bundle ("LICENSES\" + $_.Name)
        New-Item -ItemType Directory -Force -Path $licenseDir | Out-Null
        Get-ChildItem -LiteralPath $_.FullName | Where-Object { $_.Name -match '^(LICENSE|COPYING|licenses)' } | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $licenseDir -Recurse
        }
    }
}
Copy-Item -LiteralPath "docs\portable-windows.md" -Destination (Join-Path $bundle "README.md")
Copy-Item -LiteralPath "docs\validation\release-matrix.md" -Destination (Join-Path $bundle "RELEASE-MATRIX.md")
& $pythonPath scripts\stage_windows_tools.py $bundle $Archiver $CalibreDir $KfxInputZip
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar ferramentas locais." }
$zip = Join-Path $root "artifacts\KindlePDF-win-x64-candidate.zip"
New-Item -ItemType Directory -Force -Path (Split-Path $zip) | Out-Null
Compress-Archive -LiteralPath $bundle -DestinationPath $zip -Force
Write-Output "Candidato local: $zip"
Get-FileHash -LiteralPath $zip -Algorithm SHA256
