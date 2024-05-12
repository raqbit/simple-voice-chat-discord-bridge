import os
import sys

from minecraft_launcher_lib import microsoft_account

from bridge.minecraft.auth import do_auth_flow as do_minecraft_auth_flow


def prompt_for_url_input(login_url: str) -> str:
    print(f"Please open {login_url} in your browser and copy the url you are redirected into the prompt below:")
    has_code = False
    code_url = ""
    while not has_code:
        code_url = input()
        has_code = microsoft_account.url_contains_auth_code(code_url)

        if not has_code:
            print("Invalid URL, does not contain an auth code, try again:")

    return code_url

def main() -> int:
    client_id = os.getenv("MSA_CLIENT_ID")
    redirect_url = os.getenv("MSA_REDIRECT_URL")

    do_minecraft_auth_flow(client_id, redirect_url, prompt_for_url_input)

    print("Refresh token saved to file")

    return 0


if __name__ == '__main__':
    ret = main()
    sys.exit(ret)
