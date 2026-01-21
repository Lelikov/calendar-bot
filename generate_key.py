import secrets


def generate_key() -> None:
    secrets.token_urlsafe(32)


if __name__ == "__main__":
    generate_key()
