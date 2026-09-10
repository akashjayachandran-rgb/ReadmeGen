import shutil

from fastapi import FastAPI, HTTPException

from app.github_reader import (
    download_repository,
    get_repository_info,
    parse_github_url,
)
from app.models.request import RepositoryRequest


app = FastAPI(
    title="Project Anker",
    description="Generate README files from public GitHub repositories",
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

        file_count = sum(
            1
            for path in repository_root.rglob("*")
            if path.is_file()
        )

        return {
            "message": "Repository downloaded and extracted",
            "repository": repository_info,
            "file_count": file_count,
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