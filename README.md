## Review Buddy

Local, distributable **PR review + suggestions** app for devs. Paste a PR link (GitHub/GitLab/Bitbucket/Azure DevOps), pick (or auto-detect) a language, and get a review summary + actionable suggestions.

### Highlights
- **One-click PR comments**: post any suggestion back to the PR from the UI.
- **Code examples**: LLM can include a pasteable code snippet per suggestion.
- **Line ranges**: suggestions can include best-effort `Lx–Ly` ranges (validated against diff hunks).
- **Custom OpenAI endpoint**: point OpenAI calls at a corporate gateway (e.g. `genai-nexus`).

### What’s supported
- **GitHub**: `github.com` + GitHub Enterprise (`https://your-gh-host/.../pull/123`)
- **GitLab**: `gitlab.com` + self-hosted GitLab (`.../-/merge_requests/123`)
- **Bitbucket Cloud**: `bitbucket.org/.../pull-requests/123`
- **Azure DevOps**: `dev.azure.com/.../pullrequest/123` + `*.visualstudio.com/.../pullrequest/123`
- **Gitea**: self-hosted (`https://your-gitea-host/owner/repo/pulls/123`)

If your PR URL matches one of the formats above, **private repos work** via token auth configured in Settings.

### Goals
- **Easy to run**: one command to start, opens a local web UI.
- **Works with private repos**: token-based auth stored locally.
- **Model auto-selection**: chooses a recommended model/provider by language, with user override.

### Quickstart (dev mode)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
prreviewbot serve
```

Then open `http://127.0.0.1:8765` (Home page links to Tool and Settings).

### Headless mode (CLI)

```bash
prreviewbot review "https://github.com/org/repo/pull/123" --language python
```

### Configuration (no headache)
- Go to **Settings** in the UI and paste tokens for your host(s).
- Tokens are stored at `~/.prreviewbot/config.json` (chmod 600).

Supported auth methods (typical):
- **GitHub**: Personal Access Token (classic or fine-grained) with repo read access.
- **GitLab**: Personal Access Token with `read_api`.
- **Bitbucket Cloud**: App password with repo read access (store as `username:app_password`).
- **Azure DevOps**: PAT with Code (Read).

### Optional: OpenAI reviews
Install extras and set an API key in Settings:

```bash
pip install -e ".[openai]"
```

If no LLM is configured, the app uses a **local heuristic reviewer** (still useful, but less deep).

### Custom OpenAI endpoint (corporate gateway)
Set these in **Settings**:
- **Provider**: `openai`
- **OpenAI API key**: `openai_api_key`
- **OpenAI custom endpoint (optional)**: `openai_endpoint` (example: `https://genai-nexus.api.corpinter.net/apikey/`)

You can also use env vars:
- `OPENAI_API_KEY`
- `OPENAI_ENDPOINT`
- (optional) `OPENAI_API_VERSION`, `OPENAI_DEPLOYMENT`

### Build a distributable executable (PyInstaller)

```bash
pip install -e ".[build]"
python scripts/build_pyinstaller.py
```

The output binary will be under `dist/`.

### Docker + Kubernetes (ACR)

Build and push (amd64):

```bash
docker buildx build --platform linux/amd64 -t YOUR_ACR.azurecr.io/prreviewbot:0.1.0 --push .
```

Deploy:

```bash
kubectl apply -f k8s/prreviewbot.yaml
```


