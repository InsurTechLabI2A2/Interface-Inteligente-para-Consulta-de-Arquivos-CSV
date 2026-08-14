from __future__ import annotations

"""Loading and describing CSV files contained in ZIP archives."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

import pandas as pd


MAX_FILES = 40
MAX_UNCOMPRESSED_BYTES = 800 * 1024 * 1024
DICTIONARY_SUFFIXES = (".txt", ".md", ".json", ".yaml", ".yml", ".csv")


@dataclass
class LoadedDataset:
    tables: dict[str, pd.DataFrame]
    dictionary_text: str | None
    dictionary_table: pd.DataFrame | None = None
    source_name: str = "upload.zip"

    @property
    def summary(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for name, frame in self.tables.items():
            rows.append(
                {
                    "arquivo": name,
                    "linhas": len(frame),
                    "colunas": len(frame.columns),
                    "campos": ", ".join(map(str, frame.columns)),
                }
            )
        return pd.DataFrame(rows)

    def schema(self) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for name, frame in self.tables.items():
            fields = []
            for column in frame.columns:
                series = frame[column]
                fields.append(
                    {
                        "column": str(column),
                        "dtype": str(series.dtype),
                        "nulls": int(series.isna().sum()),
                        "unique": int(series.nunique(dropna=True)),
                        "examples": [str(value) for value in series.dropna().head(3).tolist()],
                    }
                )
            result[name] = fields
        return result


def _safe_members(archive: ZipFile):
    members = [member for member in archive.infolist() if not member.is_dir()]
    if len(members) > MAX_FILES:
        raise ValueError(f"O ZIP possui mais de {MAX_FILES} arquivos.")
    if sum(member.file_size for member in members) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("O conteúdo descompactado excede 800 MB.")
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("O ZIP contém um caminho de arquivo inválido.")
    return members


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="replace")


def _read_csv(raw: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        for separator in (None, ";", ",", "\\t"):
            try:
                frame = pd.read_csv(BytesIO(raw), encoding=encoding, sep=separator, engine="python")
                if len(frame.columns) > 1 or separator is not None:
                    return frame
            except Exception as exc:  # pandas exposes parser-specific exceptions
                last_error = exc
    raise ValueError("Não foi possível interpretar um arquivo CSV do ZIP.") from last_error


def _is_dictionary(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(DICTIONARY_SUFFIXES) and any(
        token in lower for token in ("dicion", "dictionary", "layout", "schema", "campo")
    )


def load_zip(uploaded_bytes: bytes, source_name: str = "upload.zip") -> LoadedDataset:
    """Read CSVs and an optional dictionary directly from an uploaded ZIP."""
    try:
        with ZipFile(BytesIO(uploaded_bytes)) as archive:
            members = _safe_members(archive)
            csv_members = [member for member in members if member.filename.lower().endswith(".csv")]
            if not csv_members:
                raise ValueError("O ZIP deve conter ao menos um arquivo .csv.")

            tables: dict[str, pd.DataFrame] = {}
            dictionary_table: pd.DataFrame | None = None
            dictionary_parts: list[str] = []
            for member in csv_members:
                name = PurePosixPath(member.filename).stem
                raw = archive.read(member)
                if _is_dictionary(member.filename):
                    try:
                        dictionary_table = _read_csv(raw)
                    except ValueError:
                        dictionary_parts.append(_decode(raw))
                    continue
                if name in tables:
                    raise ValueError(f"Há dois CSVs com o nome '{name}'.")
                tables[name] = _read_csv(raw)

            for member in members:
                if _is_dictionary(member.filename) and not member.filename.lower().endswith(".csv"):
                    dictionary_parts.append(_decode(archive.read(member)))

            if not tables:
                raise ValueError("O ZIP contém apenas arquivos de dicionário; falta um CSV de dados.")
            return LoadedDataset(
                tables=tables,
                dictionary_text="\n\n".join(dictionary_parts) or None,
                dictionary_table=dictionary_table,
                source_name=source_name,
            )
    except BadZipFile as exc:
        raise ValueError("O arquivo enviado não é um ZIP válido.") from exc

