"""OpenID Connect (OIDC) Authentication and Session Management for HomeNotifications.

Supports standard OIDC Authorization Code Flow, JWKS verification,
secure signed HTTP-only session cookies, and API Bearer / API-Key validation.
"""

from __future__ import annotations

import logging
import secrets
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import aiohttp
import jwt
from jwt import PyJWKClient

from home_notifications.config import OIDCConfig

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages OIDC discovery, code exchange, token validation, and session cookies."""

    def __init__(
        self,
        config: OIDCConfig,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.config = config
        self._external_session = session
        self._session: Optional[aiohttp.ClientSession] = session
        self._session_secret = config.session_secret or secrets.token_hex(32)
        self._openid_config: Optional[Dict[str, Any]] = None
        self._jwks_client: Optional[PyJWKClient] = None
        self._pending_states: Dict[str, Dict[str, Any]] = {}

    async def _get_http_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15.0)
            )
        return self._session

    async def close(self) -> None:
        """Close internally managed HTTP session if any."""
        if (
            self._session
            and not self._session.closed
            and self._session is not self._external_session
        ):
            await self._session.close()

    async def get_openid_config(self) -> Dict[str, Any]:
        """Fetch and cache OpenID Connect Discovery configuration document."""
        if self._openid_config is not None:
            return self._openid_config

        if not self.config.issuer_url:
            self._openid_config = {}
            return self._openid_config

        issuer = self.config.issuer_url.rstrip("/")
        discovery_url = f"{issuer}/.well-known/openid-configuration"
        session = await self._get_http_session()
        try:
            async with session.get(discovery_url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Failed to fetch OIDC configuration from {discovery_url}: "
                        f"HTTP {resp.status} - {text}"
                    )
                self._openid_config = await resp.json()
                return self._openid_config
        except Exception as e:
            logger.error("Error loading OIDC configuration from %s: %s", discovery_url, e)
            raise

    async def get_authorization_endpoint(self) -> str:
        """Resolve authorization endpoint URL."""
        if self.config.authorization_endpoint:
            return self.config.authorization_endpoint
        cfg = await self.get_openid_config()
        ep = cfg.get("authorization_endpoint")
        if not ep:
            raise ValueError(
                "No authorization_endpoint available in OIDC discovery or configuration"
            )
        return ep

    async def get_token_endpoint(self) -> str:
        """Resolve token endpoint URL."""
        if self.config.token_endpoint:
            return self.config.token_endpoint
        cfg = await self.get_openid_config()
        ep = cfg.get("token_endpoint")
        if not ep:
            raise ValueError(
                "No token_endpoint available in OIDC discovery or configuration"
            )
        return ep

    async def get_jwks_uri(self) -> str:
        """Resolve JWKS URI."""
        if self.config.jwks_uri:
            return self.config.jwks_uri
        cfg = await self.get_openid_config()
        ep = cfg.get("jwks_uri")
        if not ep:
            raise ValueError(
                "No jwks_uri available in OIDC discovery or configuration"
            )
        return ep

    async def get_userinfo_endpoint(self) -> Optional[str]:
        """Resolve userinfo endpoint URL if available."""
        if self.config.userinfo_endpoint:
            return self.config.userinfo_endpoint
        cfg = await self.get_openid_config()
        return cfg.get("userinfo_endpoint")

    async def get_end_session_endpoint(self) -> Optional[str]:
        """Resolve end session / logout endpoint URL if available."""
        if self.config.end_session_endpoint:
            return self.config.end_session_endpoint
        cfg = await self.get_openid_config()
        return cfg.get("end_session_endpoint")

    async def get_authorization_url(self, return_to: str = "/") -> str:
        """Construct the IdP authorization URL with random state and nonce."""
        # Evict expired pending states (> 15 minutes)
        now = time.time()
        expired = [s for s, data in self._pending_states.items() if now > data.get("expires_at", 0)]
        for s in expired:
            self._pending_states.pop(s, None)

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        self._pending_states[state] = {
            "nonce": nonce,
            "return_to": return_to,
            "expires_at": now + 900,
        }

        auth_endpoint = await self.get_authorization_endpoint()
        scope_str = " ".join(self.config.scopes)
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": scope_str,
            "state": state,
            "nonce": nonce,
        }
        delimiter = "&" if "?" in auth_endpoint else "?"
        return f"{auth_endpoint}{delimiter}{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code with IdP token endpoint and validate identity."""
        state_data = self._pending_states.pop(state, None)
        if not state_data:
            raise ValueError("Invalid or unknown OIDC state parameter")
        if time.time() > state_data.get("expires_at", 0):
            raise ValueError("OIDC state parameter has expired")

        nonce = state_data.get("nonce", "")
        return_to = state_data.get("return_to", "/")

        token_endpoint = await self.get_token_endpoint()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        session = await self._get_http_session()
        async with session.post(token_endpoint, data=data, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(
                    f"OIDC token exchange failed: HTTP {resp.status} - {body}"
                )
            token_response = await resp.json()

        id_token = token_response.get("id_token")
        access_token = token_response.get("access_token")
        claims: Dict[str, Any] = {}

        if id_token:
            claims = await self.verify_id_token(id_token, nonce=nonce)
        elif access_token:
            userinfo_ep = await self.get_userinfo_endpoint()
            if userinfo_ep:
                async with session.get(
                    userinfo_ep,
                    headers={"Authorization": f"Bearer {access_token}"},
                ) as uresp:
                    if uresp.status == 200:
                        claims = await uresp.json()

        sub = str(claims.get("sub", ""))
        email = str(claims.get("email", "")).lower()
        name = (
            claims.get("name")
            or claims.get("preferred_username")
            or email
            or sub
            or "Authenticated User"
        )
        username = (
            claims.get("preferred_username")
            or claims.get("nickname")
            or (email.split("@")[0] if email else sub)
        )

        groups_val = claims.get(self.config.roles_claim, [])
        if isinstance(groups_val, str):
            groups = [g.strip() for g in groups_val.split(",") if g.strip()]
        elif isinstance(groups_val, list):
            groups = [str(g) for g in groups_val]
        else:
            groups = []

        # Validate email whitelist if configured
        if self.config.allowed_emails:
            if not email or email not in [e.lower() for e in self.config.allowed_emails]:
                raise PermissionError(f"Email '{email}' is not permitted to access this application")

        # Validate groups whitelist if configured
        if self.config.allowed_groups:
            matched = set(groups).intersection(set(self.config.allowed_groups))
            if not matched:
                raise PermissionError(
                    f"User does not belong to any authorized groups ({self.config.allowed_groups})"
                )

        user_info = {
            "sub": sub,
            "email": email,
            "name": name,
            "username": username,
            "groups": groups,
        }

        return {
            "user": user_info,
            "return_to": return_to,
            "id_token": id_token,
            "access_token": access_token,
        }

    async def verify_id_token(
        self, id_token: str, nonce: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate OIDC ID Token signature, issuer, audience, and nonce."""
        jwks_uri = await self.get_jwks_uri()
        if self._jwks_client is None or self._jwks_client.jwks_uri != jwks_uri:
            self._jwks_client = PyJWKClient(
                jwks_uri, cache_keys=True, max_cached_keys=16
            )

        signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)

        cfg = await self.get_openid_config()
        expected_issuer = cfg.get("issuer") or self.config.issuer_url
        valid_issuers = []
        if expected_issuer:
            valid_issuers.append(expected_issuer)
            valid_issuers.append(expected_issuer.rstrip("/"))

        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "HS256"],
            audience=self.config.client_id if self.config.client_id else None,
            options={"verify_aud": bool(self.config.client_id), "verify_exp": True},
        )

        if valid_issuers and claims.get("iss") not in valid_issuers:
            raise jwt.InvalidIssuerError(
                f"Invalid issuer '{claims.get('iss')}'; expected '{expected_issuer}'"
            )

        if nonce and claims.get("nonce") and claims.get("nonce") != nonce:
            raise jwt.InvalidTokenError("Nonce mismatch in ID token")

        return claims

    def create_session_token(self, user: Dict[str, Any]) -> str:
        """Create a signed JWT session token for the browser session cookie."""
        now = int(time.time())
        payload = {
            "sub": str(user.get("sub", "")),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "username": user.get("username", ""),
            "groups": user.get("groups", []),
            "iat": now,
            "exp": now + self.config.cookie_max_age,
        }
        return jwt.encode(payload, self._session_secret, algorithm="HS256")

    def verify_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify the browser's signed JWT session cookie."""
        if not token:
            return None
        try:
            payload = jwt.decode(
                token,
                self._session_secret,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
            return payload
        except Exception as e:
            logger.debug("Session token verification failed: %s", e)
            return None

    async def verify_bearer_token(self, auth_header: str) -> Optional[Dict[str, Any]]:
        """Validate API Bearer token, static API token, or session token."""
        if not auth_header:
            return None

        token = auth_header.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        # 1. Check against static API tokens
        if self.config.api_tokens:
            for allowed in self.config.api_tokens:
                if secrets.compare_digest(token, allowed):
                    return {
                        "sub": "api_token",
                        "name": "API Service Client",
                        "username": "api_service",
                        "email": "",
                        "groups": ["admin"],
                        "type": "api_token",
                    }

        # 2. Check if token is a session JWT
        session_claims = self.verify_session_token(token)
        if session_claims:
            return session_claims

        # 3. Check if token is a JWT from the OIDC IdP
        try:
            jwks_uri = await self.get_jwks_uri()
            if self._jwks_client is None or self._jwks_client.jwks_uri != jwks_uri:
                self._jwks_client = PyJWKClient(
                    jwks_uri, cache_keys=True, max_cached_keys=16
                )
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            cfg = await self.get_openid_config()
            expected_issuer = cfg.get("issuer") or self.config.issuer_url
            valid_issuers = []
            if expected_issuer:
                valid_issuers.append(expected_issuer)
                valid_issuers.append(expected_issuer.rstrip("/"))

            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                options={"verify_aud": False, "verify_exp": True},
            )
            if valid_issuers and claims.get("iss") not in valid_issuers:
                return None
            return claims
        except Exception as e:
            logger.debug("Bearer token verification against IdP failed: %s", e)
            return None

    async def get_logout_url(self) -> Optional[str]:
        """Construct the IdP end-session logout URL if supported."""
        try:
            end_session = await self.get_end_session_endpoint()
        except Exception as e:
            logger.debug("Could not resolve end_session_endpoint for logout: %s", e)
            return None

        if not end_session:
            return None

        params = {}
        if self.config.client_id:
            params["client_id"] = self.config.client_id
        if self.config.redirect_uri:
            # Point post-logout redirect to base URL
            parsed = urllib.parse.urlparse(self.config.redirect_uri)
            base_origin = f"{parsed.scheme}://{parsed.netloc}/"
            params["post_logout_redirect_uri"] = base_origin

        delimiter = "&" if "?" in end_session else "?"
        return f"{end_session}{delimiter}{urllib.parse.urlencode(params)}"
