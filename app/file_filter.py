import re

from pathlib import Path

from app.config import (
    MAX_FILE_SIZE,
    MAX_SCANNED_FILES,
    MAX_SELECTED_FILES,
    MAX_SELECTED_TEXT_SIZE,
)


SKIPPED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "cache",
    "build",
    "dist",
}


SKIPPED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".mp3",
    ".mp4",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
    ".pyc",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".crt",
}


SECRET_FILE_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "token.json",
}


def should_skip_file(
    file_path: Path,
    repository_root: Path,
) -> bool:
    relative_path = file_path.relative_to(repository_root)

    directory_names = {
        part.lower()
        for part in relative_path.parts[:-1]
    }

    if directory_names.intersection(SKIPPED_DIRECTORIES):
        return True

    file_name = file_path.name.lower()

    if file_name in SECRET_FILE_NAMES:
        return True

    if (
        file_name.startswith(".env.")
        and file_name not in {
            ".env.example",
            ".env.sample",
            ".env.template",
        }
    ):
        return True

    if file_path.suffix.lower() in SKIPPED_EXTENSIONS:
        return True

    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return True
    except OSError:
        return True

    return False


def read_text_file(file_path: Path) -> str | None:
    try:
        file_content = file_path.read_bytes()
    except OSError:
        return None

    if b"\x00" in file_content:
        return None

    try:
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def redact_sensitive_text(text: str) -> str:
    assignment_pattern = re.compile(
        r"(?im)(\b(?:api[_-]?key|password|token|secret)"
        r"\b\s*[:=]\s*)[^\s,;]+"
    )

    email_pattern = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )

    aws_key_pattern = re.compile(
        r"\bAKIA[0-9A-Z]{16}\b"
    )

    text = assignment_pattern.sub(
        r"\1[REDACTED]",
        text,
    )

    text = email_pattern.sub(
        "[REDACTED]",
        text,
    )

    text = aws_key_pattern.sub(
        "[REDACTED]",
        text,
    )

    return text


def get_file_priority(file_path: Path) -> int:
    file_name = file_path.name.lower()

    path_parts = {
        part.lower()
        for part in file_path.parts
    }

    if file_name.startswith("readme"):
        return 1

    if file_name in {
        "requirements.txt",
        "package.json",
        "pyproject.toml",
        "pom.xml",
        "go.mod",
    }:
        return 2

    if file_name.startswith("dockerfile"):
        return 3

    if file_name in {
        "main.py",
        "app.py",
        "server.py",
        "index.js",
        "index.ts",
    }:
        return 4

    if "docs" in path_parts:
        return 5

    if "tests" in path_parts:
        return 6

    return 7


def scan_repository(repository_root: Path) -> list[dict]:
    repository_root = repository_root.resolve()

    candidate_files = []
    scanned_file_count = 0

    for file_path in repository_root.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.is_symlink():
            continue

        scanned_file_count += 1

        if scanned_file_count > MAX_SCANNED_FILES:
            raise ValueError(
                "Repository contains too many files"
            )

        if should_skip_file(
            file_path,
            repository_root,
        ):
            continue

        candidate_files.append(file_path)

    candidate_files.sort(
        key=lambda path: (
            get_file_priority(
                path.relative_to(repository_root)
            ),
            str(path).lower(),
        )
    )

    selected_files = []
    total_text_size = 0

    for file_path in candidate_files:
        if len(selected_files) >= MAX_SELECTED_FILES:
            break

        text = read_text_file(file_path)

        if text is None:
            continue

        text = redact_sensitive_text(text)

        text_size = len(text.encode("utf-8"))

        if (
            total_text_size + text_size
            > MAX_SELECTED_TEXT_SIZE
        ):
            continue

        relative_path = file_path.relative_to(
            repository_root
        )

        selected_files.append({
            "path": relative_path.as_posix(),
            "content": text,
            "size": text_size,
        })

        total_text_size += text_size

    return selected_files