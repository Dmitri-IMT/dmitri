from __future__ import annotations

import secrets
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from sqlalchemy import delete, func
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from api.core.config import get_settings
from api.db.session import get_engine
from api.models.identity import User
from api.models.mcp import McpAuthorization, McpClient, McpConnection, McpCredential
from api.models.persistence import utc_now
from api.services.tokens import hash_token

SCOPE = "dmitri:read"
ACCESS_SECONDS = 900
CONNECTION_DAYS = 30


class LocalOAuthClient(OAuthClientInformationFull):
    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        if redirect_uri is not None:
            candidate = urlsplit(str(redirect_uri))
            for registered in self.redirect_uris or []:
                allowed = urlsplit(str(registered))
                if (
                    candidate.scheme == allowed.scheme == "http"
                    and candidate.hostname == allowed.hostname
                    and candidate.hostname in {"localhost", "127.0.0.1", "::1"}
                    and candidate.path == allowed.path
                    and not candidate.query and not candidate.fragment
                    and not candidate.username and not candidate.password
                ):
                    return redirect_uri
        return super().validate_redirect_uri(redirect_uri)


def resource_url() -> str:
    url = get_settings().mcp_public_url
    if not url:
        raise ValueError("MCP is not configured")
    return url


def issuer_url() -> str:
    url = urlsplit(resource_url())
    return f"{url.scheme}://{url.netloc}/"


def get_client(client_id: str) -> OAuthClientInformationFull | None:
    with Session(get_engine()) as session:
        client = session.get(McpClient, client_id)
        if client is None:
            return None
        return LocalOAuthClient.model_validate(client.metadata_json)


def prune_expired(session: Session, *, keep_client_id: str = "") -> None:
    now = utc_now()
    session.execute(delete(McpAuthorization).where(
        McpAuthorization.expires_at < now
    ))
    session.execute(delete(McpCredential).where(McpCredential.expires_at < now))
    session.execute(delete(McpConnection).where(McpConnection.expires_at < now))
    session.execute(delete(McpClient).where(
        McpClient.id != keep_client_id,
        McpClient.created_at < now - timedelta(days=30),
        ~select(McpConnection.id).where(
            McpConnection.client_id == McpClient.id
        ).exists(),
        ~select(McpAuthorization.request_hash).where(
            McpAuthorization.client_id == McpClient.id
        ).exists(),
    ))


def register_client(client: OAuthClientInformationFull) -> None:
    if client.token_endpoint_auth_method != "none":
        raise RegistrationError(
            "invalid_client_metadata",
            "Use token_endpoint_auth_method=none for local public clients.",
        )
    if (
        not client.client_id or not client.redirect_uris
        or len(client.redirect_uris) > 8
    ):
        raise RegistrationError(
            "invalid_redirect_uri", "Register one to eight loopback callbacks."
        )
    for redirect in client.redirect_uris:
        url = urlsplit(str(redirect))
        if (
            url.scheme != "http"
            or url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or url.username or url.password or url.fragment or url.query
        ):
            raise RegistrationError(
                "invalid_redirect_uri",
                "Use an HTTP loopback callback without query or fragment.",
            )
    if len(client.client_name or "") > 120:
        raise RegistrationError("invalid_client_metadata", "Client name is too long.")
    with Session(get_engine()) as session:
        session.execute(select(func.pg_advisory_xact_lock(52452, 1)))
        prune_expired(session)
        if session.exec(select(func.count()).select_from(McpClient)).one() >= 5000:
            raise RegistrationError(
                "invalid_client_metadata", "Registration capacity reached."
            )
        session.add(McpClient(
            id=client.client_id, metadata_json=client.model_dump(mode="json")
        ))
        session.commit()


def authorize(
    client: OAuthClientInformationFull, params: AuthorizationParams
) -> str:
    if params.resource != resource_url():
        raise AuthorizeError(
            "invalid_request", "The resource must identify this MCP endpoint."
        )
    if params.scopes != [SCOPE]:
        raise AuthorizeError("invalid_scope", "Only dmitri:read is supported.")
    token = secrets.token_urlsafe(32)
    with Session(get_engine()) as session:
        session.execute(select(func.pg_advisory_xact_lock(52452, 2)))
        prune_expired(session, keep_client_id=client.client_id)
        pending_count = session.exec(
            select(func.count()).select_from(McpAuthorization)
        ).one()
        if pending_count >= 10000:
            raise AuthorizeError("temporarily_unavailable", "Please try again later.")
        session.add(McpAuthorization(
            request_hash=hash_token(token), client_id=client.client_id,
            params_json=params.model_dump(mode="json"),
            expires_at=utc_now() + timedelta(minutes=10),
        ))
        session.commit()
    return f"{get_settings().app_base_url.rstrip('/')}/mcp/authorize?request={token}"


def pending_authorization(
    session: Session, token: str, *, lock: bool = False
) -> McpAuthorization | None:
    statement = select(McpAuthorization).where(
        McpAuthorization.request_hash == hash_token(token)
    )
    if lock:
        statement = statement.with_for_update()
    row = session.exec(statement).first()
    if row is None or row.expires_at <= utc_now() or row.decided_at is not None:
        return None
    return row


def consent(session: Session, token: str, user: User, approve: bool) -> str | None:
    row = pending_authorization(session, token, lock=True)
    if row is None:
        return None
    params = AuthorizationParams.model_validate(row.params_json)
    row.decided_at = utc_now()
    code = None
    if approve:
        session.execute(select(func.pg_advisory_xact_lock(52452, 3)))
        count = session.exec(select(func.count()).select_from(McpConnection).where(
            McpConnection.user_id == user.id, McpConnection.revoked_at.is_(None),
            McpConnection.expires_at > utc_now(),
        )).one()
        if count >= 50:
            return None
        connection = McpConnection(
            user_id=user.id, org_id=user.org_id, client_id=row.client_id,
            resource=params.resource,
            expires_at=utc_now() + timedelta(days=CONNECTION_DAYS),
        )
        session.add(connection)
        session.flush()
        code = "dmcp_code_" + secrets.token_urlsafe(32)
        row.connection_id = connection.id
        row.code_hash = hash_token(code)
        row.expires_at = utc_now() + timedelta(minutes=5)
    session.add(row)
    session.commit()
    return construct_redirect_uri(
        str(params.redirect_uri), code=code,
        error=None if approve else "access_denied", state=params.state,
        iss=issuer_url(),
    )


def active_connection(
    session: Session, connection_id: UUID, *, lock: bool = False
) -> McpConnection | None:
    statement = select(McpConnection).where(McpConnection.id == connection_id)
    if lock:
        statement = statement.with_for_update()
    connection = session.exec(statement).first()
    if (
        connection is None or connection.revoked_at is not None
        or connection.expires_at <= utc_now()
    ):
        return None
    if connection.resource != resource_url():
        return None
    user = session.get(User, connection.user_id)
    if (
        user is None or user.org_id != connection.org_id
        or user.password_changed_at > connection.created_at
    ):
        return None
    return connection


def issue_credentials(session: Session, connection: McpConnection) -> OAuthToken:
    access = "dmcp_access_" + secrets.token_urlsafe(32)
    refresh = "dmcp_refresh_" + secrets.token_urlsafe(32)
    access_expiry = min(
        utc_now() + timedelta(seconds=ACCESS_SECONDS), connection.expires_at
    )
    for raw, kind, expires in (
        (access, "access", access_expiry),
        (refresh, "refresh", connection.expires_at),
    ):
        session.add(McpCredential(
            token_hash=hash_token(raw), connection_id=connection.id,
            kind=kind, expires_at=expires,
        ))
    session.commit()
    return OAuthToken(
        access_token=access, token_type="Bearer",
        expires_in=max(
            0, int(access_expiry.timestamp()) - int(utc_now().timestamp())
        ),
        refresh_token=refresh, scope=SCOPE,
    )


def load_authorization_code(
    client: OAuthClientInformationFull, code: str
) -> AuthorizationCode | None:
    with Session(get_engine()) as session:
        row = session.exec(select(McpAuthorization).where(
            McpAuthorization.code_hash == hash_token(code),
            McpAuthorization.client_id == client.client_id,
        )).first()
        if row is None or row.connection_id is None:
            return None
        params = AuthorizationParams.model_validate(row.params_json)
        return AuthorizationCode(
            code=code, client_id=row.client_id, scopes=[SCOPE],
            expires_at=row.expires_at.timestamp(),
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )


def exchange_authorization_code(
    client: OAuthClientInformationFull, code: AuthorizationCode
) -> OAuthToken:
    with Session(get_engine()) as session:
        row = session.exec(select(McpAuthorization).where(
            McpAuthorization.code_hash == hash_token(code.code),
            McpAuthorization.client_id == client.client_id,
        ).with_for_update()).first()
        if row is None or row.connection_id is None or row.expires_at <= utc_now():
            raise TokenError("invalid_grant", "Invalid authorization code.")
        connection = active_connection(session, row.connection_id, lock=True)
        if connection is None:
            raise TokenError("invalid_grant", "Connection is no longer valid.")
        if row.exchanged_at is not None:
            connection.revoked_at = utc_now()
            session.add(connection)
            session.commit()
            raise TokenError("invalid_grant", "Authorization code was already used.")
        row.exchanged_at = utc_now()
        session.add(row)
        return issue_credentials(session, connection)


def load_refresh_token(
    client: OAuthClientInformationFull, token: str
) -> RefreshToken | None:
    with Session(get_engine()) as session:
        credential = session.get(McpCredential, hash_token(token))
        if credential is None or credential.kind != "refresh":
            return None
        connection = active_connection(session, credential.connection_id)
        if connection is None or connection.client_id != client.client_id:
            return None
        return RefreshToken(
            token=token, client_id=connection.client_id, scopes=[SCOPE],
            expires_at=int(credential.expires_at.timestamp()),
            resource=connection.resource,
            subject=str(connection.user_id),
        )


def exchange_refresh_token(
    client: OAuthClientInformationFull, token: RefreshToken, scopes: list[str]
) -> OAuthToken:
    if scopes != [SCOPE]:
        raise TokenError("invalid_scope", "Only dmitri:read is supported.")
    with Session(get_engine()) as session:
        credential = session.exec(select(McpCredential).where(
            McpCredential.token_hash == hash_token(token.token),
            McpCredential.kind == "refresh",
        ).with_for_update()).first()
        if credential is None or credential.expires_at <= utc_now():
            raise TokenError("invalid_grant", "Invalid refresh token.")
        connection = active_connection(session, credential.connection_id, lock=True)
        if connection is None or connection.client_id != client.client_id:
            raise TokenError("invalid_grant", "Connection is no longer valid.")
        if credential.rotated_at is not None:
            connection.revoked_at = utc_now()
            session.add(connection)
            session.commit()
            raise TokenError("invalid_grant", "Refresh token was already used.")
        credential.rotated_at = utc_now()
        session.add(credential)
        return issue_credentials(session, connection)


def load_access_token(token: str) -> AccessToken | None:
    with Session(get_engine()) as session:
        credential = session.get(McpCredential, hash_token(token))
        if (
            credential is None or credential.kind != "access"
            or credential.expires_at <= utc_now()
        ):
            return None
        connection = active_connection(session, credential.connection_id)
        if connection is None:
            return None
        return AccessToken(
            token=token, client_id=connection.client_id, scopes=[SCOPE],
            expires_at=int(credential.expires_at.timestamp()),
            resource=connection.resource,
            subject=str(connection.user_id),
            claims={
                "connection_id": str(connection.id),
                "org_id": str(connection.org_id),
            },
        )


def revoke_token(token: AccessToken | RefreshToken) -> None:
    with Session(get_engine()) as session:
        credential = session.get(McpCredential, hash_token(token.token))
        if credential is not None:
            connection = session.get(McpConnection, credential.connection_id)
            if connection is not None:
                connection.revoked_at = utc_now()
                session.add(connection)
                session.commit()


class DmitriOAuthProvider:
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return await run_in_threadpool(get_client, client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        await run_in_threadpool(register_client, client_info)

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        return await run_in_threadpool(authorize, client, params)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        return await run_in_threadpool(
            load_authorization_code, client, authorization_code
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        return await run_in_threadpool(
            exchange_authorization_code, client, authorization_code
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        return await run_in_threadpool(load_refresh_token, client, refresh_token)

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull,
        refresh_token: RefreshToken, scopes: list[str],
    ) -> OAuthToken:
        return await run_in_threadpool(
            exchange_refresh_token, client, refresh_token, scopes
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        return await run_in_threadpool(load_access_token, token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        await run_in_threadpool(revoke_token, token)
