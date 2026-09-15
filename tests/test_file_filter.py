from pathlib import Path

import pytest

import app.file_filter as file_filter
from app.file_filter import scan_repository


def create_file(
    root: Path,
    relative_path: str,
    content: bytes,
):
    file_path = root / relative_path

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path.write_bytes(content)

    return file_path


def test_useful_files_are_selected_in_priority_order(
    tmp_path,
):
    create_file(
        tmp_path,
        "app/helper.py",
        b"def helper(): pass",
    )

    create_file(
        tmp_path,
        "app/main.py",
        b"print('hello')",
    )

    create_file(
        tmp_path,
        "requirements.txt",
        b"fastapi",
    )

    create_file(
        tmp_path,
        "README.md",
        b"# Example project",
    )

    selected_files = scan_repository(tmp_path)

    selected_paths = [
        selected_file["path"]
        for selected_file in selected_files
    ]

    assert selected_paths == [
        "README.md",
        "requirements.txt",
        "app/main.py",
        "app/helper.py",
    ]


def test_secret_and_binary_files_are_skipped(
    tmp_path,
):
    create_file(
        tmp_path,
        "README.md",
        b"# Safe project",
    )

    create_file(
        tmp_path,
        ".env",
        b"PASSWORD=secret",
    )

    create_file(
        tmp_path,
        "credentials.json",
        b'{"token": "secret"}',
    )

    create_file(
        tmp_path,
        "database.db",
        b"database content",
    )

    create_file(
        tmp_path,
        "image.png",
        b"fake image",
    )

    selected_files = scan_repository(tmp_path)

    selected_paths = [
        selected_file["path"]
        for selected_file in selected_files
    ]

    assert selected_paths == ["README.md"]


def test_binary_content_with_text_extension_is_skipped(
    tmp_path,
):
    create_file(
        tmp_path,
        "normal.txt",
        b"normal readable text",
    )

    create_file(
        tmp_path,
        "fake.txt",
        b"text\x00binary",
    )

    selected_files = scan_repository(tmp_path)

    selected_paths = [
        selected_file["path"]
        for selected_file in selected_files
    ]

    assert "normal.txt" in selected_paths
    assert "fake.txt" not in selected_paths


def test_oversized_file_is_skipped(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        file_filter,
        "MAX_FILE_SIZE",
        10,
    )

    create_file(
        tmp_path,
        "large.txt",
        b"This file is larger than ten bytes",
    )

    create_file(
        tmp_path,
        "small.txt",
        b"safe",
    )

    selected_files = scan_repository(tmp_path)

    selected_paths = [
        selected_file["path"]
        for selected_file in selected_files
    ]

    assert "large.txt" not in selected_paths
    assert "small.txt" in selected_paths


def test_sensitive_content_is_redacted(
    tmp_path,
):
    create_file(
        tmp_path,
        "main.py",
        (
            b"API_KEY=supersecret\n"
            b"email=owner@example.com\n"
        ),
    )

    selected_files = scan_repository(tmp_path)

    selected_content = selected_files[0]["content"]

    assert "supersecret" not in selected_content
    assert "owner@example.com" not in selected_content
    assert "[REDACTED]" in selected_content


def test_symbolic_link_is_skipped(
    tmp_path,
):
    outside_file = tmp_path.parent / "outside.txt"

    outside_file.write_text(
        "PASSWORD=secret",
        encoding="utf-8",
    )

    symbolic_link = tmp_path / "linked.txt"

    try:
        symbolic_link.symlink_to(outside_file)
    except OSError:
        pytest.skip(
            "Symbolic links are unavailable on this system"
        )

    selected_files = scan_repository(tmp_path)

    assert selected_files == []