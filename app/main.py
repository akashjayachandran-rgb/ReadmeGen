import shutil
import secrets

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response

from app.config import (
    COOKIE_SECURE,
    OAUTH_STATE_COOKIE_NAME,
    OAUTH_STATE_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
)
from app.file_filter import scan_repository
from app.github_auth import (
    GitHubAuthError,
    build_authorization_url,
    exchange_code_for_token,
    get_authenticated_user,
    list_installation_repositories,
    list_user_installations,
)
from app.github_reader import (
    download_repository,
    get_repository_info,
    parse_github_url,
)
from app.models.request import RepositoryRequest
from app.repo_analyzer import analyze_repository
from app.session_store import (
    UserSession,
    consume_oauth_state,
    create_oauth_state,
    create_session,
    delete_session,
    get_session,
)


app = FastAPI(
    title="ReadmeGen",
    description=(
        "Generate README files from authorized public and private GitHub "
        "repositories"
    ),
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


def require_session(request: Request) -> UserSession:
    session = get_session(
        request.cookies.get(SESSION_COOKIE_NAME)
    )

    if session is None:
        raise HTTPException(
            status_code=401,
            detail="GitHub login is required",
        )

    return session


@app.get("/auth/github/login")
def github_login():
    try:
        state = create_oauth_state()
        response = RedirectResponse(
            build_authorization_url(state)
        )
        response.set_cookie(
            key=OAUTH_STATE_COOKIE_NAME,
            value=state,
            max_age=OAUTH_STATE_TTL_SECONDS,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
        )
        return response
    except GitHubAuthError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get("/auth/github/callback")
def github_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        raise HTTPException(
            status_code=401,
            detail="GitHub authorization was cancelled or denied",
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="GitHub OAuth callback is incomplete",
        )

    cookie_state = request.cookies.get(
        OAUTH_STATE_COOKIE_NAME
    )

    if (
        not cookie_state
        or not secrets.compare_digest(cookie_state, state)
        or not consume_oauth_state(state)
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired GitHub OAuth state",
        )

    try:
        access_token = exchange_code_for_token(code)
        user = get_authenticated_user(access_token)
        session = create_session(
            access_token=access_token,
            github_user_id=user["id"],
            github_login=user["login"],
        )
    except GitHubAuthError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
        ) from error

    response = RedirectResponse(url="/docs")
    response.delete_cookie(OAUTH_STATE_COOKIE_NAME)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return response


@app.get("/auth/me")
def authenticated_user(
    session: UserSession = Depends(require_session),
):
    return {
        "github_user_id": session.github_user_id,
        "github_login": session.github_login,
        "expires_at": session.expires_at,
    }


@app.post("/auth/logout", status_code=204)
def logout(
    session: UserSession = Depends(require_session),
):
    delete_session(session.session_id)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/github/installations")
def github_installations(
    session: UserSession = Depends(require_session),
):
    try:
        return {
            "installations": list_user_installations(
                session.access_token
            )
        }
    except GitHubAuthError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error


@app.get("/github/repositories")
def github_repositories(
    installation_id: int,
    session: UserSession = Depends(require_session),
):
    try:
        return {
            "repositories": list_installation_repositories(
                session.access_token,
                installation_id,
            )
        }
    except GitHubAuthError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error


@app.post("/generate-readme")
def generate_readme(
    request: RepositoryRequest,
    session: UserSession = Depends(require_session),
):
    temporary_directory = None

    try:
        owner, repository = parse_github_url(
            request.github_url
        )

        repository_info = get_repository_info(
            owner,
            repository,
            session.access_token,
        )

        temporary_directory, repository_root = (
            download_repository(
                repository_info["owner"],
                repository_info["repository"],
                repository_info["default_branch"],
                session.access_token,
            )
        )

        selected_files = scan_repository(
            repository_root
        )

        repository_facts = analyze_repository(
            repository_info,
            selected_files,
        )

        return {
            "message": "Repository analyzed successfully",
            "repository": repository_info,
            "selected_file_count": len(
                selected_files
            ),
            "selected_files": [
                selected_file["path"]
                for selected_file in selected_files
            ],
            "repository_facts": repository_facts,
            "temporary_files_deleted": True,
        }

    except ValueError as error:
        message = str(error)
        if "invalid or expired" in message.lower():
            status_code = 401
        elif (
            "not authorized" in message.lower()
            or "access was denied" in message.lower()
        ):
            status_code = 403
        else:
            status_code = 400

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    finally:
        if temporary_directory:
            shutil.rmtree(
                temporary_directory,
                ignore_errors=True,
            )
