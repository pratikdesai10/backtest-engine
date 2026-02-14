"""Fyers API OAuth2 authentication flow."""

from pathlib import Path

from fyers_apiv3 import fyersModel


TOKEN_FILE = Path(".fyers_token")


def get_session(client_id: str, secret_key: str, redirect_uri: str) -> fyersModel.SessionModel:
    """Create a SessionModel and print the auth URL for the user to visit."""
    session = fyersModel.SessionModel(
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type="code",
        state="backtest-engine",
        secret_key=secret_key,
        grant_type="authorization_code",
    )
    auth_url = session.generate_authcode()
    print(f"\nOpen this URL in your browser to authorize:\n{auth_url}\n")
    return session


def generate_token(session: fyersModel.SessionModel, auth_code: str) -> str:
    """Exchange auth code for an access token."""
    session.set_token(auth_code)
    response = session.generate_token()
    if "access_token" not in response:
        raise RuntimeError(f"Token generation failed: {response}")
    return response["access_token"]


def save_token(access_token: str, path: Path = TOKEN_FILE) -> None:
    """Save access token to file for reuse (valid for one day)."""
    path.write_text(access_token)


def load_token(path: Path = TOKEN_FILE) -> str | None:
    """Load saved access token, or return None if not found."""
    if path.exists():
        token = path.read_text().strip()
        if token:
            return token
    return None


def get_fyers_client(client_id: str, access_token: str) -> fyersModel.FyersModel:
    """Return an initialized FyersModel client ready for API calls."""
    return fyersModel.FyersModel(
        token=access_token,
        is_async=False,
        client_id=client_id,
        log_path="",
    )
