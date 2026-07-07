"""GitHub live-auth token providers."""

from __future__ import annotations

import os
import time
import typing as T
from dataclasses import dataclass, field
from pathlib import Path


JsonMap = dict[str, T.Any]
AUTH_AUTO = "auto"
AUTH_ENV_TOKEN = "env-token"
AUTH_GITHUB_APP = "github-app"
AUTH_CHOICES = (AUTH_AUTO, AUTH_ENV_TOKEN, AUTH_GITHUB_APP)
ISSUE_WRITE_PERMISSIONS = {"issues": "write"}
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_API_VERSION = "2022-11-28"


class GitHubAuthError(ValueError):
    """Raised when GitHub auth cannot produce a usable token."""


@dataclass(frozen=True)
class GitHubAuthToken:
    token: str
    source: str
    expires_at: str | None = None
    repositories: tuple[str, ...] = ()
    permissions: JsonMap = field(default_factory=dict)

    def to_safe_dict(self) -> JsonMap:
        return {
            "source": self.source,
            "token_available": bool(self.token),
            "expires_at": self.expires_at,
            "repositories": list(self.repositories),
            "permissions": self.permissions,
        }


@dataclass(frozen=True)
class GitHubAuthResolution:
    mode: str
    status: str
    message: str
    token: GitHubAuthToken | None = None
    next_action: str | None = None
    missing: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def token_value(self) -> str | None:
        return self.token.token if self.token else None

    @property
    def source(self) -> str:
        return self.token.source if self.token else self.mode

    def to_dict(self) -> JsonMap:
        return {
            "mode": self.mode,
            "status": self.status,
            "message": self.message,
            "source": self.source,
            "token": self.token.to_safe_dict() if self.token else None,
            "next_action": self.next_action,
            "missing": list(self.missing),
        }


@dataclass(frozen=True)
class GitHubAppCredentials:
    client_id: str
    installation_id: str
    private_key: str
    api_url: str = DEFAULT_GITHUB_API_URL
    api_version: str = DEFAULT_GITHUB_API_VERSION


def env_token_from_env(env: T.Mapping[str, str] | None = None) -> GitHubAuthToken | None:
    values = env or os.environ
    token = values.get("GITHUB_TOKEN") or values.get("GH_TOKEN")
    if isinstance(token, str) and token.strip():
        return GitHubAuthToken(token=token.strip(), source=AUTH_ENV_TOKEN)
    return None


def github_app_credentials_from_env(
    env: T.Mapping[str, str] | None = None,
    *,
    cwd: Path | None = None,
) -> tuple[GitHubAppCredentials | None, tuple[str, ...]]:
    values = env or os.environ
    client_id = _first_env(
        values,
        "DELEGATION_GITHUB_APP_CLIENT_ID",
        "GITHUB_APP_CLIENT_ID",
        "DELEGATION_GITHUB_APP_ID",
        "GITHUB_APP_ID",
    )
    installation_id = _first_env(
        values,
        "DELEGATION_GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_INSTALLATION_ID",
    )
    private_key = _private_key_from_env(values, cwd=cwd)
    api_url = _first_env(values, "DELEGATION_GITHUB_API_URL", "GITHUB_API_URL") or DEFAULT_GITHUB_API_URL
    api_version = (
        _first_env(values, "DELEGATION_GITHUB_API_VERSION", "GITHUB_API_VERSION")
        or DEFAULT_GITHUB_API_VERSION
    )

    missing: list[str] = []
    if not client_id:
        missing.append("DELEGATION_GITHUB_APP_CLIENT_ID")
    if not installation_id:
        missing.append("DELEGATION_GITHUB_APP_INSTALLATION_ID")
    if not private_key:
        missing.append("DELEGATION_GITHUB_APP_PRIVATE_KEY or DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH")
    if missing:
        return None, tuple(missing)
    return (
        GitHubAppCredentials(
            client_id=client_id,
            installation_id=installation_id,
            private_key=private_key,
            api_url=api_url,
            api_version=api_version,
        ),
        (),
    )


class GitHubAppInstallationTokenProvider:
    """Mint short-lived installation tokens from a GitHub App private key."""

    def __init__(
        self,
        credentials: GitHubAppCredentials,
        *,
        requests_module: T.Any = None,
        jwt_encoder: T.Callable[[JsonMap, str], str] | None = None,
        now: T.Callable[[], float] | None = None,
    ) -> None:
        self.credentials = credentials
        self.requests = requests_module
        self.jwt_encoder = jwt_encoder
        self.now = now or time.time

    def create_token(
        self,
        *,
        repositories: T.Sequence[str],
        permissions: T.Mapping[str, str],
    ) -> GitHubAuthToken:
        jwt_token = self.create_jwt()
        requests = self.requests or _requests_module()
        body = _installation_token_body(repositories=repositories, permissions=permissions)
        response = requests.post(
            (
                f"{self.credentials.api_url.rstrip('/')}/app/installations/"
                f"{self.credentials.installation_id}/access_tokens"
            ),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {jwt_token}",
                "X-GitHub-Api-Version": self.credentials.api_version,
            },
            json=body,
            timeout=20,
        )
        _raise_for_response(response)
        data = response.json()
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("token"), str)
            or not data["token"].strip()
        ):
            raise GitHubAuthError("GitHub App installation token response did not include a token")
        response_repositories = _response_repositories(data.get("repositories")) or tuple(repositories)
        response_permissions = (
            data.get("permissions")
            if isinstance(data.get("permissions"), dict)
            else dict(permissions)
        )
        return GitHubAuthToken(
            token=data["token"],
            source=AUTH_GITHUB_APP,
            expires_at=data.get("expires_at") if isinstance(data.get("expires_at"), str) else None,
            repositories=response_repositories,
            permissions=dict(response_permissions),
        )

    def create_jwt(self) -> str:
        now = int(self.now())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": self.credentials.client_id,
        }
        encoder = self.jwt_encoder or _jwt_encode
        return encoder(payload, self.credentials.private_key)


def resolve_github_auth_token(
    *,
    mode: str,
    apply: bool,
    repositories: T.Sequence[str],
    permissions: T.Mapping[str, str],
    env: T.Mapping[str, str] | None = None,
    app_provider: GitHubAppInstallationTokenProvider | None = None,
) -> GitHubAuthResolution:
    if mode not in AUTH_CHOICES:
        raise GitHubAuthError(f"unknown GitHub auth mode: {mode}")
    if not apply:
        return GitHubAuthResolution(
            mode=mode,
            status="preview",
            message="Preview mode does not mint or require a GitHub token.",
        )

    values = env or os.environ
    if mode == AUTH_ENV_TOKEN:
        return _resolve_env_token(mode=mode, env=values)
    if mode == AUTH_GITHUB_APP:
        return _resolve_github_app_token(
            mode=mode,
            repositories=repositories,
            permissions=permissions,
            env=values,
            app_provider=app_provider,
        )

    app_resolution: GitHubAuthResolution | None = None
    if app_provider is not None or _github_app_env_present(values):
        app_resolution = _resolve_github_app_token(
            mode=mode,
            repositories=repositories,
            permissions=permissions,
            env=values,
            app_provider=app_provider,
        )
        if not app_resolution.blocked:
            return app_resolution
        return app_resolution
    env_resolution = _resolve_env_token(mode=mode, env=values)
    if not env_resolution.blocked:
        return env_resolution
    return app_resolution or env_resolution


def render_github_auth_resolution(resolution: GitHubAuthResolution) -> str:
    lines = [
        "GitHub Auth",
        f"- mode: {resolution.mode}",
        f"- status: {resolution.status}",
        f"- source: {resolution.source}",
        f"- message: {resolution.message}",
    ]
    if resolution.token:
        lines.append(f"- token available: {'yes' if resolution.token.token else 'no'}")
        if resolution.token.expires_at:
            lines.append(f"- expires: {resolution.token.expires_at}")
        if resolution.token.repositories:
            lines.append(f"- repositories: {', '.join(resolution.token.repositories)}")
        if resolution.token.permissions:
            pairs = [f"{key}={value}" for key, value in sorted(resolution.token.permissions.items())]
            lines.append(f"- permissions: {', '.join(pairs)}")
    if resolution.missing:
        lines.append(f"- missing: {', '.join(resolution.missing)}")
    if resolution.next_action:
        lines.append(f"- next: {resolution.next_action}")
    return "\n".join(lines)


def _resolve_env_token(*, mode: str, env: T.Mapping[str, str]) -> GitHubAuthResolution:
    token = env_token_from_env(env)
    if token:
        return GitHubAuthResolution(mode=mode, status="ready", message="Using GITHUB_TOKEN/GH_TOKEN.", token=token)
    return GitHubAuthResolution(
        mode=mode,
        status="blocked",
        message="No environment GitHub token is available.",
        next_action="Set GITHUB_TOKEN or GH_TOKEN, or configure GitHub App auth.",
        missing=("GITHUB_TOKEN or GH_TOKEN",),
    )


def _resolve_github_app_token(
    *,
    mode: str,
    repositories: T.Sequence[str],
    permissions: T.Mapping[str, str],
    env: T.Mapping[str, str],
    app_provider: GitHubAppInstallationTokenProvider | None,
) -> GitHubAuthResolution:
    provider = app_provider
    missing: tuple[str, ...] = ()
    if provider is None:
        try:
            credentials, missing = github_app_credentials_from_env(env)
        except GitHubAuthError as exc:
            return GitHubAuthResolution(
                mode=mode,
                status="blocked",
                message=str(exc),
                next_action="Fix GitHub App auth configuration before live apply.",
            )
        if credentials is None:
            return GitHubAuthResolution(
                mode=mode,
                status="blocked",
                message="GitHub App auth is missing required configuration.",
                next_action="Set GitHub App client id, installation id, and private key env vars.",
                missing=missing,
            )
        provider = GitHubAppInstallationTokenProvider(credentials)
    try:
        token = provider.create_token(repositories=repositories, permissions=permissions)
    except GitHubAuthError as exc:
        return GitHubAuthResolution(
            mode=mode,
            status="blocked",
            message=str(exc),
            next_action="Fix GitHub App auth configuration before live apply.",
            missing=missing,
        )
    return GitHubAuthResolution(
        mode=mode,
        status="ready",
        message="Using a scoped GitHub App installation token.",
        token=token,
    )


def _github_app_env_present(values: T.Mapping[str, str]) -> bool:
    names = (
        "DELEGATION_GITHUB_APP_CLIENT_ID",
        "GITHUB_APP_CLIENT_ID",
        "DELEGATION_GITHUB_APP_ID",
        "GITHUB_APP_ID",
        "DELEGATION_GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_INSTALLATION_ID",
        "DELEGATION_GITHUB_APP_PRIVATE_KEY",
        "GITHUB_APP_PRIVATE_KEY",
        "DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH",
        "GITHUB_APP_PRIVATE_KEY_PATH",
    )
    return any(isinstance(values.get(name), str) and values[name].strip() for name in names)


def _first_env(values: T.Mapping[str, str], *names: str) -> str:
    for name in names:
        value = values.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _private_key_from_env(values: T.Mapping[str, str], *, cwd: Path | None) -> str:
    raw_key = _first_env(values, "DELEGATION_GITHUB_APP_PRIVATE_KEY", "GITHUB_APP_PRIVATE_KEY")
    if raw_key:
        return raw_key.replace("\\n", "\n")
    key_path = _first_env(
        values,
        "DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH",
        "GITHUB_APP_PRIVATE_KEY_PATH",
    )
    if not key_path:
        return ""
    path = Path(key_path)
    if not path.is_absolute() and cwd is not None:
        path = cwd / path
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GitHubAuthError(f"Could not read GitHub App private key path: {path}") from exc


def _installation_token_body(
    *,
    repositories: T.Sequence[str],
    permissions: T.Mapping[str, str],
) -> JsonMap:
    owner_names = [_split_repository(repository) for repository in repositories]
    owners = {owner for owner, _ in owner_names}
    if len(owners) > 1:
        raise GitHubAuthError("A single GitHub App installation token cannot span multiple owners")
    body: JsonMap = {"permissions": dict(permissions)}
    if owner_names:
        body["repositories"] = sorted({name for _, name in owner_names})
    return body


def _split_repository(repository: str) -> tuple[str, str]:
    parts = str(repository).split("/", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise GitHubAuthError(f"repository must be in owner/name form: {repository!r}")
    return parts[0].strip(), parts[1].strip()


def _response_repositories(value: T.Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        full_name = item.get("full_name")
        if isinstance(full_name, str) and full_name.strip():
            names.append(full_name)
    return tuple(names)


def _jwt_encode(payload: JsonMap, private_key: str) -> str:
    try:
        import jwt
    except ImportError as exc:
        raise GitHubAuthError(
            "GitHub App auth requires PyJWT with cryptography; install `delegationhq[github-app]`."
        ) from exc
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token.decode("utf-8") if isinstance(token, bytes) else str(token)


def _requests_module() -> T.Any:
    try:
        import requests
    except ImportError as exc:
        raise GitHubAuthError(
            "The `requests` package is required for GitHub App installation token auth."
        ) from exc
    return requests


def _raise_for_response(response: T.Any) -> None:
    if response.status_code < 400:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    raise GitHubAuthError(f"GitHub App auth API error {response.status_code}: {payload}")
