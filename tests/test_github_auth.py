from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from delegation_bot.github_auth import (
    AUTH_AUTO,
    AUTH_ENV_TOKEN,
    AUTH_GITHUB_APP,
    GitHubAppCredentials,
    GitHubAppInstallationTokenProvider,
    GitHubAuthError,
    github_app_credentials_from_env,
    resolve_github_auth_token,
)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 201) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = "fake response"

    def json(self) -> dict:
        return self.payload


class FakeRequests:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: int) -> FakeResponse:
        self.posts.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "token": "installation-token",
                "expires_at": "2026-07-07T17:00:00Z",
                "permissions": {"issues": "write"},
                "repositories": [{"full_name": "AmmarAlBalkhi/delegation-bot"}],
            }
        )


class GitHubAuthTests(unittest.TestCase):
    def test_env_token_resolution_is_safe_to_render(self) -> None:
        resolution = resolve_github_auth_token(
            mode=AUTH_ENV_TOKEN,
            apply=True,
            repositories=["AmmarAlBalkhi/delegation-bot"],
            permissions={"issues": "write"},
            env={"GITHUB_TOKEN": "secret-token"},
        )

        self.assertFalse(resolution.blocked)
        self.assertEqual(resolution.token_value, "secret-token")
        self.assertNotIn("secret-token", str(resolution.to_dict()))

    def test_github_app_credentials_read_private_key_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "app.pem"
            key_path.write_text("-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----\n", encoding="utf-8")

            credentials, missing = github_app_credentials_from_env(
                {
                    "DELEGATION_GITHUB_APP_CLIENT_ID": "client-1",
                    "DELEGATION_GITHUB_APP_INSTALLATION_ID": "123",
                    "DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH": str(key_path),
                }
            )

        self.assertEqual(missing, ())
        self.assertIsNotNone(credentials)
        self.assertIn("BEGIN PRIVATE KEY", credentials.private_key if credentials else "")

    def test_github_app_missing_config_blocks_without_network(self) -> None:
        resolution = resolve_github_auth_token(
            mode=AUTH_GITHUB_APP,
            apply=True,
            repositories=["AmmarAlBalkhi/delegation-bot"],
            permissions={"issues": "write"},
            env={},
        )

        self.assertTrue(resolution.blocked)
        self.assertIn("DELEGATION_GITHUB_APP_CLIENT_ID", resolution.missing)
        self.assertIn("GitHub App auth is missing", resolution.message)

    def test_auto_auth_reports_broken_app_config_when_no_env_token_exists(self) -> None:
        resolution = resolve_github_auth_token(
            mode=AUTH_AUTO,
            apply=True,
            repositories=["AmmarAlBalkhi/delegation-bot"],
            permissions={"issues": "write"},
            env={"DELEGATION_GITHUB_APP_CLIENT_ID": "client-1"},
        )

        self.assertTrue(resolution.blocked)
        self.assertIn("GitHub App auth is missing", resolution.message)
        self.assertIn("DELEGATION_GITHUB_APP_INSTALLATION_ID", resolution.missing)

    def test_auto_auth_does_not_fallback_when_app_config_is_partial_even_with_env_token(self) -> None:
        resolution = resolve_github_auth_token(
            mode=AUTH_AUTO,
            apply=True,
            repositories=["AmmarAlBalkhi/delegation-bot"],
            permissions={"issues": "write"},
            env={"DELEGATION_GITHUB_APP_CLIENT_ID": "client-1", "GITHUB_TOKEN": "broad-token"},
        )

        self.assertTrue(resolution.blocked)
        self.assertIsNone(resolution.token_value)
        self.assertIn("GitHub App auth is missing", resolution.message)
        self.assertNotIn("broad-token", str(resolution.to_dict()))

    def test_github_app_provider_scopes_repository_names_and_permissions(self) -> None:
        fake_requests = FakeRequests()
        seen_payloads: list[dict] = []

        def fake_jwt(payload: dict, private_key: str) -> str:
            seen_payloads.append(payload)
            self.assertEqual(private_key, "private-key")
            return "signed-jwt"

        provider = GitHubAppInstallationTokenProvider(
            GitHubAppCredentials(
                client_id="client-1",
                installation_id="123",
                private_key="private-key",
                api_url="https://api.github.test",
                api_version="2022-11-28",
            ),
            requests_module=fake_requests,
            jwt_encoder=fake_jwt,
            now=lambda: 1000,
        )

        token = provider.create_token(
            repositories=["AmmarAlBalkhi/delegation-bot"],
            permissions={"issues": "write"},
        )

        self.assertEqual(token.token, "installation-token")
        self.assertEqual(token.source, AUTH_GITHUB_APP)
        self.assertEqual(token.repositories, ("AmmarAlBalkhi/delegation-bot",))
        self.assertEqual(seen_payloads[0], {"iat": 940, "exp": 1600, "iss": "client-1"})
        self.assertEqual(fake_requests.posts[0]["json"], {"permissions": {"issues": "write"}, "repositories": ["delegation-bot"]})
        self.assertEqual(fake_requests.posts[0]["headers"]["Authorization"], "Bearer signed-jwt")

    def test_github_app_provider_rejects_cross_owner_repository_scope(self) -> None:
        provider = GitHubAppInstallationTokenProvider(
            GitHubAppCredentials(client_id="client-1", installation_id="123", private_key="private-key"),
            requests_module=FakeRequests(),
            jwt_encoder=lambda payload, private_key: "signed-jwt",
        )

        with self.assertRaises(GitHubAuthError):
            provider.create_token(
                repositories=["AmmarAlBalkhi/delegation-bot", "OtherOwner/other-repo"],
                permissions={"issues": "write"},
            )


if __name__ == "__main__":
    unittest.main()
