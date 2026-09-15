import os

from dotenv import load_dotenv


load_dotenv()


GITHUB_API_URL = "https://api.github.com"
GITHUB_WEB_URL = "https://github.com"

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_CALLBACK_URL = os.getenv(
    "GITHUB_CALLBACK_URL",
    "http://localhost:8000/auth/github/callback",
)

SESSION_COOKIE_NAME = "ReadmeGen_session"
OAUTH_STATE_COOKIE_NAME = "ReadmeGen_oauth_state"
OAUTH_STATE_TTL_SECONDS = 10 * 60
SESSION_TTL_SECONDS = 8 * 60 * 60
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

REQUEST_TIMEOUT = 10

MAX_DOWNLOAD_SIZE = 25 * 1024 * 1024
MAX_EXTRACTED_SIZE = 100 * 1024 * 1024
MAX_ARCHIVE_FILES = 5000

MAX_SCANNED_FILES = 5000
MAX_SELECTED_FILES = 200
MAX_FILE_SIZE = 512 * 1024
MAX_SELECTED_TEXT_SIZE = 2 * 1024 * 1024
