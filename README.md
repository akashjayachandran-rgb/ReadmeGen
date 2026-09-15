# Project Anker

Project Anker accepts an authorized GitHub repository URL, safely downloads
the default branch, filters unsafe files and extracts structured repository
facts for README generation.

The local authentication flow supports:

- public repositories;
- private repositories owned by an individual user;
- private repositories shared with the user; and
- repositories belonging to a GitHub Organization.

The signed-in user and the Project Anker GitHub App must both be allowed to
access a repository. Project Anker requests read-only metadata and contents
permissions and never pushes changes to GitHub.

## 1 Create the GitHub App

Open GitHub **Settings > Developer settings > GitHub Apps > New GitHub App**.
Use these local-development values:

```text
GitHub App name: Project Anker Local <your-name>
Homepage URL: http://localhost:8000/docs
Callback URL: http://localhost:8000/auth/github/callback
Webhook: Inactive
Repository permissions > Contents: Read-only
Where can this GitHub App be installed: Any account
```

Metadata permission is included automatically. Do not enable write
permissions. After creating the App, copy its Client ID and generate a client
secret. Install the App on selected repositories in your personal account. An
Organization owner must approve and install it for company repositories.

## 2 Configure the local environment

Create `.env` from `.env.example` and replace the placeholder values:

```powershell
Copy-Item .env.example .env
```

```dotenv
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_CALLBACK_URL=http://localhost:8000/auth/github/callback
COOKIE_SECURE=false
```

Never commit `.env` or share the client secret.

## 3 Install and start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open this URL in the same browser that will use Swagger:

```text
http://localhost:8000/auth/github/login
```

After GitHub redirects back, open `http://localhost:8000/docs` and use:

1. `GET /auth/me` to confirm the login.
2. `GET /github/installations` to find an installation ID.
3. `GET /github/repositories` to list repositories in that installation.
4. `POST /generate-readme` with an authorized repository URL.
5. `POST /auth/logout` when finished.

Example request:

```json
{
  "github_url": "https://github.com/owner/repository"
}
```

## Tests

```powershell
pytest -q
```

The current session store is intentionally in memory for local development.
Sessions disappear when the application restarts. Production deployment will
replace this with an encrypted shared store.
