param([string]$Compiler = "C:\Program Files\Inno Setup 7\ISCC.exe")

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$bundle = Join-Path $root "dist\KindlePDF"
if (-not (Test-Path -LiteralPath (Join-Path $bundle "KindlePDF.exe")) -or
    -not (Test-Path -LiteralPath (Join-Path $bundle "KindlePDF-CLI.exe")) -or
    -not (Test-Path -LiteralPath (Join-Path $bundle "_internal"))) {
    throw "Bundle Windows ausente. Execute scripts/build_windows.ps1 primeiro."
}
$archiver = Join-Path $bundle "tools\MSIXKFXArchiver_x64_1_25218.exe"
$calibre = Join-Path $bundle "tools\Calibre"
$plugin = Join-Path $bundle "tools\KFX Input.zip"
if (-not (Test-Path -LiteralPath $archiver) -or
    -not (Test-Path -LiteralPath (Join-Path $calibre "calibre-customize.exe")) -or
    -not (Test-Path -LiteralPath (Join-Path $calibre "calibre-debug.exe")) -or
    -not (Test-Path -LiteralPath $plugin)) {
    throw "Ferramentas locais ausentes: o instalador completo não pode ser compilado."
}
& ".tmp\phase8-build-venv\Scripts\python.exe" -c "from pathlib import Path; from kindle_pdf.windows_tools import windows_tools_status; import sys; sys.exit(0 if windows_tools_status(Path(sys.argv[1])) == 'ready' else 1)" $bundle
if ($LASTEXITCODE -ne 0) { throw "Ferramentas do pacote não correspondem às versões validadas." }
$compilerPath = (Resolve-Path -LiteralPath $Compiler).Path
& $compilerPath "installer\KindlePDF.iss"
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o instalador." }
$installer = Join-Path $root "artifacts\KindlePDF-Setup-win-x64-candidate.exe"
if (-not (Test-Path -LiteralPath $installer)) { throw "Instalador esperado ausente." }
Get-Item -LiteralPath $installer | Select-Object FullName, Length
Get-FileHash -LiteralPath $installer -Algorithm SHA256
Get-AuthenticodeSignature -LiteralPath $installer | Select-Object Status, SignerCertificate
