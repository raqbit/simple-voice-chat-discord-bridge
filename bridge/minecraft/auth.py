import json
from typing import Callable

from minecraft_launcher_lib import microsoft_account

FILE_NAME = ".auth.json"

class AuthDetails():
    id: str
    name: str
    refresh_token: str

    def __init__(self, data: dict[str, str]):
        self.id = data['id']
        self.name = data['name']
        self.refresh_token = data['refresh_token']

    def to_dict(self) -> dict[str, str]:
        return {
            'id': self.id,
            'name': self.name,
            'refresh_token': self.refresh_token,
        }

def _save_auth_details(auth_details: AuthDetails):
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(auth_details.to_dict(), f, ensure_ascii=False, indent=4)

def _load_auth_details() -> AuthDetails:
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        json_data = json.load(f)
        return AuthDetails(json_data)

def refresh_auth(client_id: str) -> (str, str, str):
    auth_details = _load_auth_details()

    response = microsoft_account.complete_refresh(client_id, None, None, auth_details.refresh_token)

    details = AuthDetails(response)

    _save_auth_details(details)

    return (details.id, details.name, response['access_token'])

def do_auth_flow(client_id: str, redirect_url: str, get_url: Callable[[str], str]) -> str:
    login_url, state, code_verifier = microsoft_account.get_secure_login_data(client_id, redirect_url)

    code_url = get_url(login_url)

    try:
        auth_code = microsoft_account.parse_auth_code_url(code_url, state)
    except AssertionError:
        raise Exception("states do not match")
    except KeyError:
        raise Exception("url not valid")

    login_data = microsoft_account.complete_login(client_id, None, redirect_url, auth_code, code_verifier)

    details = AuthDetails(login_data)

    _save_auth_details(details)

    return login_data['access_token']
