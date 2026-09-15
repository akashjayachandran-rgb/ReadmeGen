import secrets

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.config import OAUTH_STATE_TTL_SECONDS, SESSION_TTL_SECONDS


@dataclass(frozen=True)
class UserSession:
    session_id: str
    access_token: str = field(repr=False)
    github_user_id: int
    github_login: str
    expires_at: datetime


_oauth_states: dict[str, datetime] = {}
_sessions: dict[str, UserSession] = {}
_lock = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_oauth_state() -> str:
    state = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)

    with _lock:
        _oauth_states[state] = expires_at

    return state


def consume_oauth_state(state: str) -> bool:
    now = _now()

    with _lock:
        expired = [
            key
            for key, expires_at in _oauth_states.items()
            if expires_at <= now
        ]
        for key in expired:
            _oauth_states.pop(key, None)

        expires_at = _oauth_states.pop(state, None)

    return expires_at is not None and expires_at > now


def create_session(
    access_token: str,
    github_user_id: int,
    github_login: str,
) -> UserSession:
    session_id = secrets.token_urlsafe(32)
    session = UserSession(
        session_id=session_id,
        access_token=access_token,
        github_user_id=github_user_id,
        github_login=github_login,
        expires_at=_now() + timedelta(seconds=SESSION_TTL_SECONDS),
    )

    with _lock:
        _sessions[session_id] = session

    return session


def get_session(session_id: str | None) -> UserSession | None:
    if not session_id:
        return None

    with _lock:
        session = _sessions.get(session_id)

        if session and session.expires_at <= _now():
            _sessions.pop(session_id, None)
            return None

        return session


def delete_session(session_id: str | None) -> None:
    if not session_id:
        return

    with _lock:
        _sessions.pop(session_id, None)
