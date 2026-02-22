from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config


def get_credentials() -> Credentials:
    """Return valid Google OAuth2 credentials, refreshing or running the
    interactive flow as needed."""
    creds = None

    # Reuse saved token if available
    try:
        creds = Credentials.from_authorized_user_file(config.TOKEN_PATH, config.GOOGLE_SCOPES)
    except Exception:
        pass

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(config.CREDENTIALS_PATH, config.GOOGLE_SCOPES)
        creds = flow.run_local_server(port=0)

    # Persist for next run
    with open(config.TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    return creds


def build_service(api: str, version: str):
    """Build and return a Google API service client."""
    creds = get_credentials()
    return build(api, version, credentials=creds)
