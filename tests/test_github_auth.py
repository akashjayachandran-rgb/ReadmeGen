from urllib.parse import parse_qs, urlparse

import app.github_auth as github_auth


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def configure_auth(monkeypatch):
    monkeypatch.setattr(
        github_auth,
        "GITHUB_CLIENT_ID",
        "client-id",
    )
    monkeypatch.setattr(
        github_auth,
        "GITHUB_CLIENT_SECRET",
        "client-secret",
    )


def test_authorization_url_contains_state_and_callback(monkeypatch):
    configure_auth(monkeypatch)

    authorization_url = github_auth.build_authorization_url(
        "state-value"
    )
    parsed_url = urlparse(authorization_url)
    query = parse_qs(parsed_url.query)

    assert parsed_url.path == "/login/oauth/authorize"
    assert query["client_id"] == ["client-id"]
    assert query["state"] == ["state-value"]
    assert query["redirect_uri"] == [
        github_auth.GITHUB_CALLBACK_URL
    ]


def test_code_is_exchanged_without_exposing_client_secret(
    monkeypatch,
):
    configure_auth(monkeypatch)
    captured_request = {}

    def fake_post(url, headers, data, timeout):
        captured_request.update(
            {
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            200,
            {"access_token": "user-token"},
        )

    monkeypatch.setattr(
        github_auth.requests,
        "post",
        fake_post,
    )

    token = github_auth.exchange_code_for_token(
        "temporary-code"
    )

    assert token == "user-token"
    assert captured_request["data"]["code"] == "temporary-code"
    assert (
        captured_request["data"]["client_secret"]
        == "client-secret"
    )


def test_installations_are_reduced_to_safe_fields(monkeypatch):
    def fake_get(url, headers, params, timeout):
        assert headers["Authorization"] == "Bearer user-token"
        return FakeResponse(
            200,
            {
                "installations": [
                    {
                        "id": 77,
                        "account": {
                            "login": "example-company",
                            "type": "Organization",
                        },
                        "repository_selection": "selected",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        github_auth.requests,
        "get",
        fake_get,
    )

    installations = github_auth.list_user_installations(
        "user-token"
    )

    assert installations == [
        {
            "installation_id": 77,
            "account": "example-company",
            "account_type": "Organization",
            "repository_selection": "selected",
        }
    ]
