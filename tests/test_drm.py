"""Contrato opcional: proteção, privacidade e integração sem ferramenta real."""

import pickle
from pathlib import Path

import pytest

from kindle_pdf.batch import convert_batch
from kindle_pdf.drm import DecryptResult, SecretInput, diagnose_protected
from kindle_pdf.pipeline import ConvertOptions, convert_one
from tests.book_fixtures import make_text_epub


def protected_sample(path: Path) -> Path:
    path.write_bytes(b"\xeaDRMION\xeeProtectedData")
    return path


def test_secret_is_absent_from_result_log_and_serialization(tmp_path: Path, caplog) -> None:
    source = protected_sample(tmp_path / "book.azw")
    secret = SecretInput("SERIAL-DE-TESTE-NAO-REAL")
    result = diagnose_protected(source, secret, tmp_path / "decrypted")

    assert result.status == "unsupported"
    assert not (tmp_path / "decrypted").exists()
    assert "SERIAL-DE-TESTE-NAO-REAL" not in repr(secret)
    assert "SERIAL-DE-TESTE-NAO-REAL" not in str(secret)
    assert "SERIAL-DE-TESTE-NAO-REAL" not in repr(result)
    assert "SERIAL-DE-TESTE-NAO-REAL" not in caplog.text
    with pytest.raises(TypeError):
        pickle.dumps(secret)


def test_adapter_exception_does_not_expose_secret(tmp_path: Path, caplog) -> None:
    source = protected_sample(tmp_path / "book.azw")
    secret = SecretInput("SEGREDO-SINTETICO")

    class ExplodingAdapter:
        def decrypt(self, input_path, output_dir, credential):
            raise RuntimeError(f"bad key {credential.reveal()}")

    result = diagnose_protected(source, secret, tmp_path / "decrypted", ExplodingAdapter())

    assert result.status == "failed"
    assert "SEGREDO-SINTETICO" not in repr(result)
    assert "SEGREDO-SINTETICO" not in caplog.text


def test_options_and_result_repr_do_not_include_adapter_or_intermediate_secrets(tmp_path: Path) -> None:
    class LeakyAdapter:
        def __repr__(self):
            return "SEGREDO-SINTETICO"

    secret = SecretInput("SEGREDO-SINTETICO")
    options = ConvertOptions(decrypt_adapter=LeakyAdapter(), credential=secret)
    result = DecryptResult("decrypted", tmp_path / "SEGREDO-SINTETICO.epub")
    assert "SEGREDO-SINTETICO" not in repr(options)
    assert "SEGREDO-SINTETICO" not in repr(result)


def test_protected_input_needs_adapter_and_cannot_publish_by_default(tmp_path: Path) -> None:
    source = protected_sample(tmp_path / "book.azw")
    output = tmp_path / "pdfs"
    result = convert_one(source, output, ConvertOptions(credential=SecretInput("fake")))
    assert result.status == "protected_or_unreadable"
    assert result.pdf_path is None
    assert not output.exists()


@pytest.mark.renderer
def test_injected_adapter_may_supply_supported_intermediate_without_leaking_secret(tmp_path: Path) -> None:
    source = protected_sample(tmp_path / "book.azw")
    secret = SecretInput("CHAVE-SINTETICA-NAO-REAL")

    class SyntheticAdapter:
        def decrypt(self, input_path, output_dir, credential):
            assert credential.reveal() == "CHAVE-SINTETICA-NAO-REAL"
            intermediate = make_text_epub(output_dir / "intermediate.epub")
            return DecryptResult("decrypted", intermediate)

    output = tmp_path / "pdfs"
    options = ConvertOptions(decrypt_adapter=SyntheticAdapter(), credential=secret)
    report = convert_batch([source], output, options)

    assert report.results[0].status == "converted"
    assert report.results[0].pdf_path.is_file()
    manifest = report.manifest_path.read_text(encoding="utf-8")
    assert "CHAVE-SINTETICA-NAO-REAL" not in manifest
    assert "intermediate.epub" not in manifest
    assert not [path for path in output.glob(".kindle-pdf-*") if path.is_dir()]


def test_adapter_cannot_return_file_outside_temporary_directory(tmp_path: Path) -> None:
    source = protected_sample(tmp_path / "book.azw")
    outside = make_text_epub(tmp_path / "outside.epub")

    class OutsideAdapter:
        def decrypt(self, input_path, output_dir, credential):
            return DecryptResult("decrypted", outside)

    result = convert_one(source, tmp_path / "pdfs", ConvertOptions(
        decrypt_adapter=OutsideAdapter(), credential=SecretInput("fake")))
    assert result.status == "protected_or_unreadable"
    assert result.pdf_path is None
    assert not list((tmp_path / "pdfs").glob("*.pdf"))


@pytest.mark.renderer
def test_protected_batch_resumes_validated_pdf_without_storing_credential(tmp_path: Path) -> None:
    source = protected_sample(tmp_path / "book.azw")
    calls = 0

    class SyntheticAdapter:
        def decrypt(self, input_path, output_dir, credential):
            nonlocal calls
            calls += 1
            return DecryptResult("decrypted", make_text_epub(output_dir / "book.epub"))

    output = tmp_path / "pdfs"
    options = ConvertOptions(decrypt_adapter=SyntheticAdapter(), credential=SecretInput("PRIVATE-TEST-KEY"))
    first = convert_batch([source], output, options)
    second = convert_batch([source], output, options)
    assert first.results[0].status == second.results[0].status == "converted"
    assert second.resumed_count == 1
    assert second.results[0].pdf_path == first.results[0].pdf_path
    assert calls == 1
    assert "PRIVATE-TEST-KEY" not in second.manifest_path.read_text(encoding="utf-8")


def test_direct_diagnosis_removes_adapter_partial_files_on_failure(tmp_path: Path) -> None:
    source = protected_sample(tmp_path / "book.azw")

    class PartialAdapter:
        def decrypt(self, input_path, output_dir, credential):
            (output_dir / "partial.keyfile").write_text("SENSITIVE-TEST-DATA", encoding="utf-8")
            return DecryptResult("failed")

    destination = tmp_path / "decrypted"
    result = diagnose_protected(source, SecretInput("PRIVATE-TEST-KEY"), destination, PartialAdapter())
    assert result.status == "failed"
    assert not list(destination.rglob("*"))
