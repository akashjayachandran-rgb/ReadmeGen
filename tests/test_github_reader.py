import pytest

from app.github_reader import _github_headers, parse_github_url


def test_valid_github_url():
    owner, repository = parse_github_url(
        "https://github.com/octocat/Hello-World"
    )

    assert owner == "octocat"
    assert repository == "Hello-World"


def test_git_extension_is_removed():
    owner, repository = parse_github_url(
        "https://github.com/octocat/Hello-World.git"
    )

    assert owner == "octocat"
    assert repository == "Hello-World"


@pytest.mark.parametrize(
    "github_url",
    [
        "http://github.com/octocat/Hello-World",
        "https://gitlab.com/octocat/Hello-World",
        "https://github.com/octocat",
        "https://github.com/",
    ],
)
def test_invalid_github_urls(github_url):
    with pytest.raises(ValueError):
        parse_github_url(github_url)


def test_authenticated_headers_include_bearer_token():
    headers = _github_headers("private-token")

    assert headers["Authorization"] == "Bearer private-token"


def test_public_headers_do_not_include_authorization():
    headers = _github_headers()

    assert "Authorization" not in headers
