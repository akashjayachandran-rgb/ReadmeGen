import shutil

from fastapi import FastAPI, HTTPException

from app.file_filter import scan_repository
from app.github_reader import (
    download_repository,
    get_repository_info,
    parse_github_url,
)
from app.models.request import RepositoryRequest


app = FastAPI(
    title="Project Anker",
    description=(
        "Generate README files from public GitHub repositories"
    ),
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/generate-readme")
def generate_readme(request: RepositoryRequest):
    temporary_directory = None

    try:
        owner, repository = parse_github_url(
            request.github_url
        )

        repository_info = get_repository_info(
            owner,
            repository,
        )

        temporary_directory, repository_root = (
            download_repository(
                repository_info["owner"],
                repository_info["repository"],
                repository_info["default_branch"],
            )
        )

        selected_files = scan_repository(
            repository_root
        )

        return {
            "message": "Repository scanned safely",
            "repository": repository_info,
            "selected_file_count": len(
                selected_files
            ),
            "selected_files": [
                selected_file["path"]
                for selected_file in selected_files
            ],
            "temporary_files_deleted": True,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    finally:
        if temporary_directory:
            shutil.rmtree(
                temporary_directory,
                ignore_errors=True,
            )