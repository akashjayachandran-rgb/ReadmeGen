import shutil

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import RedirectResponse, Response

from app.config import (
    COOKIE_SECURE,
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
    description="""
ReadmeGen analyses authorized public and private GitHub repositories.

## GitHub authentication

[Click here to log in with GitHub](/auth/github/login)

After completing GitHub authorization, GitHub will redirect you
back to this Swagger page.

Then use `GET /auth/me` to confirm that you are logged in.
""",
)


@app.get("/", include_in_schema=False)
def home():
    """
    Redirect the root URL to the Swagger documentation.
    """

    return RedirectResponse(
        url="/docs",
        status_code=302,
    )


@app.get("/health")
def health_check():
    """
    Check whether the ReadmeGen API is running.
    """

    return {
        "status": "healthy",
    }


def require_session(request: Request) -> UserSession:
    """
    Read and validate the user's login session cookie.
    """

    session_id = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    session = get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "GitHub login is required. Open "
                "/auth/github/login in the browser."
            ),
        )

    return session


@app.get(
    "/auth/github/login",
    include_in_schema=False,
)
def github_login():
    """
    Start the GitHub OAuth login process.

    This route must be opened directly in the browser.
    """

    try:
        state = create_oauth_state()

        authorization_url = build_authorization_url(
            state
        )

        return RedirectResponse(
            url=authorization_url,
            status_code=302,
        )

    except GitHubAuthError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get(
    "/auth/github/callback",
    include_in_schema=False,
)
def github_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """
    Receive the OAuth result from GitHub.

    GitHub calls this endpoint automatically.
    Users should not open it manually.
    """

    if error:
        raise HTTPException(
            status_code=401,
            detail=(
                "GitHub authorization was cancelled "
                "or denied."
            ),
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail=(
                "GitHub OAuth callback is incomplete. "
                "Start login from /auth/github/login."
            ),
        )

    if not consume_oauth_state(state):
        raise HTTPException(
            status_code=400,
            detail=(
                "GitHub OAuth state is invalid or expired. "
                "Start a new login without restarting "
                "the application."
            ),
        )

    try:
        access_token = exchange_code_for_token(code)

        user = get_authenticated_user(
            access_token
        )

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

    response = RedirectResponse(
        url="/docs",
        status_code=302,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    return response


@app.get("/auth/me")
def authenticated_user(
    session: UserSession = Depends(require_session),
):
    """
    Return information about the logged-in GitHub user.
    """

    return {
        "authenticated": True,
        "github_user_id": session.github_user_id,
        "github_login": session.github_login,
        "expires_at": session.expires_at,
    }


@app.post(
    "/auth/logout",
    status_code=204,
)
def logout(
    session: UserSession = Depends(require_session),
):
    """
    Delete the current GitHub login session.
    """

    delete_session(
        session.session_id
    )

    response = Response(
        status_code=204
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return response


@app.get("/github/installations")
def github_installations(
    session: UserSession = Depends(require_session),
):
    """
    List the GitHub App installations available to the user.
    """

    try:
        installations = list_user_installations(
            session.access_token
        )

        return {
            "installations": installations,
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
    """
    List repositories available through a GitHub App installation.
    """

    try:
        repositories = list_installation_repositories(
            session.access_token,
            installation_id,
        )

        return {
            "repositories": repositories,
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
    """
    Download, filter and analyse an authorized repository.

    The Bedrock README-generation stage will be added later.
    """

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
        normalized_message = message.lower()

        if "invalid or expired" in normalized_message:
            status_code = 401

        elif (
            "not authorized" in normalized_message
            or "access was denied" in normalized_message
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