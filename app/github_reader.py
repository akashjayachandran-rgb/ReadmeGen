import shutil
import stat
import tempfile
import zipfile


from pathlib import Path
from urllib.parse import quote, urlparse

import requests

from app.config import (
    GITHUB_API_URL,
    MAX_ARCHIVE_FILES,
    MAX_DOWNLOAD_SIZE,
    MAX_EXTRACTED_SIZE,
    REQUEST_TIMEOUT,
)


def parse_github_url(github_url: str):
    parsed_url = urlparse(github_url)

    if parsed_url.scheme != "https":
        raise ValueError("Only HTTPS URLs are allowed")

    if parsed_url.hostname != "github.com":
        raise ValueError("Only github.com URLs are allowed")

    path_parts = parsed_url.path.strip("/").split("/")

    if len(path_parts) != 2:
        raise ValueError(
            "URL must contain a repository owner and repository name"
        )

    owner, repository = path_parts

    if repository.endswith(".git"):
        repository = repository[:-4]

    if not owner or not repository:
        raise ValueError("Invalid GitHub repository URL")

    return owner, repository


def _github_headers(access_token: str | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Project-Anker",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    return headers


def get_repository_info(
    owner: str,
    repository: str,
    access_token: str | None = None,
):
    api_url = f"{GITHUB_API_URL}/repos/{owner}/{repository}"

    try:
        response = requests.get(
            api_url,
            headers=_github_headers(access_token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as error:
        raise ValueError("GitHub request timed out") from error
    except requests.RequestException as error:
        raise ValueError("Unable to connect to GitHub") from error

    if response.status_code == 404:
        raise ValueError(
            "Repository not found or access is not authorized"
        )

    if response.status_code == 401:
        raise ValueError("GitHub login is invalid or expired")

    if response.status_code == 403:
        raise ValueError(
            "GitHub access was denied or the rate limit was reached"
        )

    if response.status_code != 200:
        raise ValueError(
            f"GitHub returned status code {response.status_code}"
        )

    repository_data = response.json()

    return {
        "owner": repository_data["owner"]["login"],
        "repository": repository_data["name"],
        "default_branch": repository_data["default_branch"],
        "description": repository_data.get("description"),
        "language": repository_data.get("language"),
        "private": repository_data.get("private", False),
    }


def safe_extract_archive(zip_path: Path, extraction_directory: Path):
    extraction_directory.mkdir(parents=True, exist_ok=True)
    safe_root = extraction_directory.resolve()

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            members = archive.infolist()

            if len(members) > MAX_ARCHIVE_FILES:
                raise ValueError("Repository contains too many files")

            extracted_size = sum(
                member.file_size for member in members
            )

            if extracted_size > MAX_EXTRACTED_SIZE:
                raise ValueError(
                    "Extracted repository is too large"
                )

            for member in members:
                destination = (
                    extraction_directory / member.filename
                ).resolve()

                try:
                    destination.relative_to(safe_root)
                except ValueError:
                    raise ValueError(
                        "Unsafe path found inside repository archive"
                    )

                file_mode = member.external_attr >> 16

                if stat.S_ISLNK(file_mode):
                    raise ValueError(
                        "Repository archive contains a symbolic link"
                    )

            archive.extractall(extraction_directory)

    except zipfile.BadZipFile as error:
        raise ValueError(
            "GitHub returned an invalid ZIP archive"
        ) from error


def download_repository(
    owner: str,
    repository: str,
    default_branch: str,
    access_token: str | None = None,
):
    temporary_directory = Path(
        tempfile.mkdtemp(prefix="project_anker_")
    )

    zip_path = temporary_directory / "repository.zip"
    extraction_directory = temporary_directory / "repository"

    encoded_branch = quote(default_branch, safe="")

    download_url = (
        f"{GITHUB_API_URL}/repos/{owner}/{repository}"
        f"/zipball/{encoded_branch}"
    )

    try:
        with requests.get(
            download_url,
            headers=_github_headers(access_token),
            stream=True,
            timeout=(10, 30),
        ) as response:
            if response.status_code == 401:
                raise ValueError("GitHub login is invalid or expired")

            if response.status_code in (403, 404):
                raise ValueError(
                    "Repository download is not authorized"
                )

            if response.status_code != 200:
                raise ValueError(
                    "Failed to download the repository"
                )

            content_length = response.headers.get(
                "Content-Length"
            )

            if (
                content_length
                and int(content_length) > MAX_DOWNLOAD_SIZE
            ):
                raise ValueError(
                    "Repository download is too large"
                )

            downloaded_size = 0

            with open(zip_path, "wb") as zip_file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if not chunk:
                        continue

                    downloaded_size += len(chunk)

                    if downloaded_size > MAX_DOWNLOAD_SIZE:
                        raise ValueError(
                            "Repository download is too large"
                        )

                    zip_file.write(chunk)

        safe_extract_archive(
            zip_path,
            extraction_directory,
        )

        folders = [
            item
            for item in extraction_directory.iterdir()
            if item.is_dir()
        ]

        if len(folders) == 1:
            repository_root = folders[0]
        else:
            repository_root = extraction_directory

        return temporary_directory, repository_root

    except Exception:
        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )
        raise
