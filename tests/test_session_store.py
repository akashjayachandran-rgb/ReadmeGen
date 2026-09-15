from app.session_store import (
    consume_oauth_state,
    create_oauth_state,
    create_session,
    delete_session,
    get_session,
)


def test_oauth_state_is_single_use():
    state = create_oauth_state()

    assert consume_oauth_state(state) is True
    assert consume_oauth_state(state) is False


def test_session_can_be_created_and_deleted():
    session = create_session(
        access_token="test-token",
        github_user_id=123,
        github_login="octocat",
    )

    stored_session = get_session(session.session_id)

    assert stored_session is not None
    assert stored_session.github_login == "octocat"
    assert stored_session.access_token == "test-token"

    delete_session(session.session_id)

    assert get_session(session.session_id) is None
