import getpass
import hashlib
import secrets


def make_hash(password):
    if len(password) < 12:
        raise ValueError("管理密码至少 12 位")
    salt = secrets.token_hex(16)
    rounds = 310000
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds)
    return f"pbkdf2_sha256${rounds}${salt}${value.hex()}"


def check_hash(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 100000 <= int(rounds) <= 2000000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return secrets.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


if __name__ == "__main__":
    password = getpass.getpass("设置管理密码（至少 12 位）：")
    if password != getpass.getpass("再次输入："):
        raise SystemExit("两次输入不一致")
    print(make_hash(password))
