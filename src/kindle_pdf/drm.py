"""Contrato para arquivos protegidos e validação do intermediário local."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import tempfile
from typing import Literal, Protocol, SupportsIndex

from .detect import detect_book

DecryptStatus = Literal["decrypted", "unsupported", "invalid_credential", "failed"]


class SecretInput:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("Credencial vazia ou inválida.")
        self._value = value

    def reveal(self) -> str:
        """Entrega o valor somente ao adaptador autorizado pelo chamador."""
        return self._value

    def __repr__(self) -> str:
        return "SecretInput(<redacted>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: SupportsIndex):
        raise TypeError("SecretInput não pode ser serializado.")


@dataclass(frozen=True, slots=True)
class DecryptResult:
    status: DecryptStatus
    output_path: Path | None = field(default=None, repr=False)


class DecryptAdapter(Protocol):
    def decrypt(self, input_path: Path, output_dir: Path, credential: SecretInput) -> DecryptResult: ...


def diagnose_protected(input_path: Path, credential: SecretInput, output_dir: Path,
                       adapter: DecryptAdapter | None = None) -> DecryptResult:
    """Tenta um adaptador fornecido pelo chamador e aceita só intermediário local legível."""
    source = Path(input_path).resolve()
    detection = detect_book(source)
    if detection.status != "protected_or_unreadable" or adapter is None:
        return DecryptResult("unsupported")
    destination = Path(output_dir).resolve()
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".kindle-pdf-decrypt-", dir=destination) as scratch:
            workspace = Path(scratch)
            candidate = adapter.decrypt(source, workspace, credential)
            if not isinstance(candidate, DecryptResult):
                return DecryptResult("failed")
            if candidate.status != "decrypted":
                if candidate.status in {"unsupported", "invalid_credential", "failed"}:
                    return DecryptResult(candidate.status)
                return DecryptResult("failed")
            if candidate.output_path is None:
                return DecryptResult("failed")
            output = Path(candidate.output_path).resolve()
            if not output.is_relative_to(workspace) or not output.is_file():
                return DecryptResult("failed")
            intermediate = detect_book(output)
            if intermediate.status != "supported" or intermediate.format not in {"epub", "mobi", "azw3"}:
                return DecryptResult("unsupported")
            if detection.sha256 is None:
                return DecryptResult("failed")
            target = destination / f"decrypted-{detection.sha256[:16]}.{intermediate.format}"
            os.link(output, target)
        return DecryptResult("decrypted", target)
    except Exception:
        # Exceções de ferramentas externas podem conter tokens; nunca as propagamos.
        return DecryptResult("failed")
