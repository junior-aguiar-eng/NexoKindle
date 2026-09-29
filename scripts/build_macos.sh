#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == "Darwin" ]] || { echo "Execute em macOS." >&2; exit 2; }
: "${WEASYPRINT_BUNDLE_DIR:?Informe a pasta portatil nativa do WeasyPrint em WEASYPRINT_BUNDLE_DIR}"
: "${WEASYPRINT_LICENSE_FILE:?Informe a licenca do build nativo em WEASYPRINT_LICENSE_FILE}"
[[ -x "$WEASYPRINT_BUNDLE_DIR/weasyprint" && -f "$WEASYPRINT_LICENSE_FILE" ]] || { echo "Renderizador nativo ou licenca ausente." >&2; exit 2; }
uv venv --python 3.12 .tmp/phase8-build-venv
uv pip sync requirements.txt --python .tmp/phase8-build-venv/bin/python
.tmp/phase8-build-venv/bin/python -m PyInstaller --noconfirm --clean --onedir --console \
  --name KindlePDF --paths src --add-data "$WEASYPRINT_BUNDLE_DIR:weasyprint" scripts/portable_app.py
mkdir -p dist/KindlePDF/LICENSES artifacts
cp "$WEASYPRINT_LICENSE_FILE" dist/KindlePDF/LICENSES/WeasyPrint-LICENSE
cp src/kindle_pdf/_vendor/KindleUnpack/COPYING.txt dist/KindlePDF/LICENSES/KindleUnpack-COPYING.txt
cp README.md dist/KindlePDF/PROJECT-README.md
cp docs/validation/release-matrix.md dist/KindlePDF/RELEASE-MATRIX.md
tar -czf "artifacts/KindlePDF-macos-$(uname -m)-candidate.tar.gz" -C dist KindlePDF
shasum -a 256 "artifacts/KindlePDF-macos-$(uname -m)-candidate.tar.gz"
