from urllib.parse import urlencode

import requests

from app.config import (
    GITHUB_API_URL,
    GITHUB_CALLBACK_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_WEB_URL,
    REQUEST_TIMEOUT,
)


class GitHubAuthError(ValueError):
    pass


def ensure_github_auth_is_configured() -> None:
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise GitHubAuthError(
            "GitHub authentication is not configured. Add the GitHub App "
            "client ID and client secret to the local .env file."
        )


def build_authorization_url(state: str) -> str:
    ensure_github_auth_is_configured()
    query = urlencode(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_CALLBACK_URL,
            "state": state,
            "allow_signup": "false",
        }
    )
    return f"{GITHUB_WEB_URL}/login/oauth/authorize?{query}"


def exchange_code_for_token(code: str) -> str:
    ensure_github_auth_is_configured()

    try:
        response = requests.post(
            f"{GITHUB_WEB_URL}/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_CALLBACK_URL,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise GitHubAuthError(
            "Unable to complete GitHub authentication"
        ) from error

    if response.status_code != 200:
        raise GitHubAuthError("GitHub authentication was rejected")

    payload = response.json()
    access_token = payload.get("access_token")

    if not access_token:
        raise GitHubAuthError(
            payload.get("error_description", "GitHub returned no access token")
        )

    return access_token


def _authorized_headers(access_token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "Project-Anker",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_authenticated_user(access_token: str) -> dict:
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/user",
            headers=_authorized_headers(access_token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise GitHubAuthError("Unable to read the GitHub user") from error

    if response.status_code != 200:
        raise GitHubAuthError("GitHub login is invalid or expired")

    user = response.json()
    return {
        "id": user["id"],
        "login": user["login"],
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
    }


def list_user_installations(access_token: str) -> list[dict]:
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/user/installations",
            headers=_authorized_headers(access_token),
            params={"per_page": 100},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise GitHubAuthError(
            "Unable to connect to GitHub installations"
        ) from error

    if response.status_code == 401:
        raise GitHubAuthError("GitHub login is invalid or expired")
    if response.status_code != 200:
        raise GitHubAuthError("Unable to list GitHub App installations")

    return [
        {
            "installation_id": item["id"],
            "account": item["account"]["login"],
            "account_type": item["account"]["type"],
            "repository_selection": item["repository_selection"],
        }
        for item in response.json().get("installations", [])
    ]


def list_installation_repositories(
    access_token: str,
    installation_id: int,
) -> list[dict]:
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/user/installations/{installation_id}/repositories",
            headers=_authorized_headers(access_token),
            params={"per_page": 100},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise GitHubAuthError(
            "Unable to connect to GitHub repositories"
        ) from error

    if response.status_code == 401:
        raise GitHubAuthError("GitHub login is invalid or expired")
    if response.status_code in (403, 404):
        raise GitHubAuthError(
            "The GitHub App installation is unavailable or not authorized"
        )
    if response.status_code != 200:
        raise GitHubAuthError("Unable to list authorized repositories")

    return [
        {
            "full_name": item["full_name"],
            "private": item["private"],
            "default_branch": item["default_branch"],
        }
        for item in response.json().get("repositories", [])
    ]
