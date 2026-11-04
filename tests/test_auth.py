"""Unit and integration tests for OIDC Authentication and Web Protection."""

import pytest
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import jwt

from home_notifications.auth import AuthManager
from home_notifications.config import AppConfig, DeviceConfig, FeatureConfig, OIDCConfig, SystemConfig, TelegramConfig, load_config
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager
from home_notifications.web.server import WebServer


def test_auth_config_parsing(tmp_path: Path):
    ini_file = tmp_path / "config.ini"
    ini_file.write_text(
        """[auth]
enabled = true
issuer_url = https://auth.example.com
client_id = my-client
client_secret = my-secret
redirect_uri = http://localhost:8085/auth/callback
scopes = openid,profile,email,groups
session_secret = secret-12345678901234567890123456789012
cookie_name = custom_session
cookie_secure = true
cookie_max_age = 3600
api_tokens = token-aaa, token-bbb
allowed_emails = admin@example.com, test@example.com
allowed_groups = homelab-admins
roles_claim = user_roles
""",
        encoding="utf-8",
    )

    devices_file = tmp_path / "devices.yaml"
    devices_file.write_text("devices: []\n", encoding="utf-8")

    cfg = load_config(tmp_path)
    assert cfg.auth.enabled is True
    assert cfg.auth.issuer_url == "https://auth.example.com"
    assert cfg.auth.client_id == "my-client"
    assert cfg.auth.client_secret == "my-secret"
    assert cfg.auth.redirect_uri == "http://localhost:8085/auth/callback"
    assert cfg.auth.scopes == ["openid", "profile", "email", "groups"]
    assert cfg.auth.session_secret == "secret-12345678901234567890123456789012"
    assert cfg.auth.cookie_name == "custom_session"
    assert cfg.auth.cookie_secure is True
    assert cfg.auth.cookie_max_age == 3600
    assert cfg.auth.api_tokens == ["token-aaa", "token-bbb"]
    assert cfg.auth.allowed_emails == ["admin@example.com", "test@example.com"]
    assert cfg.auth.allowed_groups == ["homelab-admins"]
    assert cfg.auth.roles_claim == "user_roles"


def test_session_token_create_and_verify():
    cfg = OIDCConfig(session_secret="super-secret-key-32-bytes-minimum!", cookie_max_age=3600)
    auth = AuthManager(cfg)

    user_info = {
        "sub": "user_123",
        "name": "Phillip Ferland",
        "email": "pferland@example.com",
        "username": "pferland",
        "groups": ["admin", "users"],
    }

    token = auth.create_session_token(user_info)
    assert isinstance(token, str)

    # Verify valid token
    payload = auth.verify_session_token(token)
    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["name"] == "Phillip Ferland"
    assert payload["email"] == "pferland@example.com"
    assert payload["groups"] == ["admin", "users"]

    # Verify tampered token returns None
    tampered = token[:-4] + "abcd"
    assert auth.verify_session_token(tampered) is None

    # Verify expired token returns None
    expired_auth = AuthManager(OIDCConfig(session_secret="super-secret-key-32-bytes-minimum!", cookie_max_age=-10))
    expired_token = expired_auth.create_session_token(user_info)
    assert auth.verify_session_token(expired_token) is None


@pytest.mark.asyncio
async def test_authorization_url_generation():
    cfg = OIDCConfig(
        issuer_url="https://auth.example.com",
        authorization_endpoint="https://auth.example.com/oauth2/auth",
        client_id="test-client-id",
        redirect_uri="http://localhost:8085/auth/callback",
        scopes=["openid", "profile"],
    )
    auth = AuthManager(cfg)

    auth_url = await auth.get_authorization_url(return_to="/resources")
    assert "https://auth.example.com/oauth2/auth?" in auth_url
    assert "client_id=test-client-id" in auth_url
    assert "response_type=code" in auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8085%2Fauth%2Fcallback" in auth_url
    assert "scope=openid+profile" in auth_url or "scope=openid%20profile" in auth_url
    assert "state=" in auth_url
    assert "nonce=" in auth_url

    # Verify pending state was saved
    assert len(auth._pending_states) == 1
    state_key = list(auth._pending_states.keys())[0]
    assert auth._pending_states[state_key]["return_to"] == "/resources"

    await auth.close()


@pytest.mark.asyncio
async def test_bearer_token_verification():
    cfg = OIDCConfig(
        api_tokens=["static-secret-api-token-123"],
        session_secret="secret-key-for-session-tokens-1234",
    )
    auth = AuthManager(cfg)

    # 1. Static API token with 'Bearer ' prefix
    val1 = await auth.verify_bearer_token("Bearer static-secret-api-token-123")
    assert val1 is not None
    assert val1["type"] == "api_token"

    # 2. Static API token without prefix
    val2 = await auth.verify_bearer_token("static-secret-api-token-123")
    assert val2 is not None

    # 3. Session JWT in Bearer header
    session_jwt = auth.create_session_token({"sub": "web_user", "name": "Web User"})
    val3 = await auth.verify_bearer_token(f"Bearer {session_jwt}")
    assert val3 is not None
    assert val3["sub"] == "web_user"

    # 4. Invalid token
    val4 = await auth.verify_bearer_token("Bearer invalid-token-xyz")
    assert val4 is None

    await auth.close()


@pytest.fixture
def auth_test_app(tmp_path: Path):
    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(web_host="127.0.0.1", web_port=8085)
    auth_cfg = OIDCConfig(
        enabled=True,
        issuer_url="https://auth.example.com",
        authorization_endpoint="https://auth.example.com/oauth2/authorize",
        token_endpoint="https://auth.example.com/oauth2/token",
        client_id="test-client",
        client_secret="test-secret",
        redirect_uri="http://localhost:8085/auth/callback",
        session_secret="test-session-secret-key-32-chars-long",
        api_tokens=["valid-api-token-xyz"],
    )
    features = {
        "external_ip": FeatureConfig("external_ip", enabled=True),
    }
    devices = {
        "dev1": DeviceConfig(id="dev1", name="Dev 1", ip="192.168.1.10"),
    }
    config = AppConfig(
        base_dir=tmp_path,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features,
        devices=devices,
        auth=auth_cfg,
    )

    state = StateManager(tmp_path / "data" / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    discovery_mock = MagicMock()
    discovery_mock.is_enabled = False
    device_mock = MagicMock()
    device_mock.is_enabled = False
    ip_mock = MagicMock()
    ip_mock.is_enabled = False
    flag_mock = MagicMock()
    flag_mock.is_enabled = False

    server = WebServer(
        config=config,
        state=state,
        notifier=notifier,
        discovery_feature=discovery_mock,
        device_feature=device_mock,
        ip_feature=ip_mock,
        flag_feature=flag_mock,
    )
    return server


@pytest.mark.asyncio
async def test_auth_middleware_blocks_unauthenticated_api(auth_test_app, aiohttp_client):
    client: TestClient = await aiohttp_client(auth_test_app.app)

    # 1. API request without credentials -> 401 Unauthorized JSON
    resp = await client.get("/api/status")
    assert resp.status == 401
    assert resp.content_type == "application/json"
    data = await resp.json()
    assert data["error"] == "Unauthorized"

    # 2. Browser request to "/" without credentials -> 302 Redirect to /auth/login
    ui_resp = await client.get("/", allow_redirects=False)
    assert ui_resp.status == 302
    location = ui_resp.headers.get("Location", "")
    assert location.startswith("/auth/login?redirect_to=")


@pytest.mark.asyncio
async def test_auth_middleware_allows_valid_bearer_token(auth_test_app, aiohttp_client):
    client: TestClient = await aiohttp_client(auth_test_app.app)

    # Authorized via Authorization: Bearer <token>
    headers = {"Authorization": "Bearer valid-api-token-xyz"}
    resp = await client.get("/api/status", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_auth_middleware_allows_valid_session_cookie(auth_test_app, aiohttp_client):
    client: TestClient = await aiohttp_client(auth_test_app.app)

    # Create session cookie
    session_token = auth_test_app.auth_manager.create_session_token({
        "sub": "user_42",
        "name": "Admin User",
        "email": "admin@example.com",
    })

    client.session.cookie_jar.update_cookies(
        {auth_test_app.config.auth.cookie_name: session_token},
        response_url=client.make_url("/"),
    )

    # API request with valid session cookie succeeds
    api_resp = await client.get("/api/status")
    assert api_resp.status == 200

    # User profile API returns authenticated user info
    user_resp = await client.get("/auth/user")
    assert user_resp.status == 200
    user_data = await user_resp.json()
    assert user_data["authenticated"] is True
    assert user_data["user"]["sub"] == "user_42"
    assert user_data["user"]["name"] == "Admin User"


@pytest.mark.asyncio
async def test_auth_logout_clears_cookie(auth_test_app, aiohttp_client):
    client: TestClient = await aiohttp_client(auth_test_app.app)

    session_token = auth_test_app.auth_manager.create_session_token({
        "sub": "user_42",
        "name": "Admin User",
    })
    client.session.cookie_jar.update_cookies(
        {auth_test_app.config.auth.cookie_name: session_token},
        response_url=client.make_url("/"),
    )

    # Call logout
    logout_resp = await client.get("/auth/logout", allow_redirects=False)
    assert logout_resp.status == 302
    assert "Clear-Site-Data" in logout_resp.headers

    # Subsequent request without cookie should be blocked
    resp_after = await client.get("/api/status")
    assert resp_after.status == 401
