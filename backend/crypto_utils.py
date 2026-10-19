"""Encryption at rest: Fernet (AES-128-CBC + HMAC). Key comes from FORMATIFY_ENC_KEY."""
import os
import tempfile

from cryptography.fernet import Fernet

_TEXT_PREFIX = "enc::"
_FILE_MAGIC = b"FMTENC1"


def _f() -> Fernet:
    key = os.environ.get("FORMATIFY_ENC_KEY")
    if not key:
        raise RuntimeError("FORMATIFY_ENC_KEY is not set")
    return Fernet(key.encode())


# ---- secrets stored in the DB (OAuth tokens, SMTP passwords) ----
def encrypt_text(value):
    if not value or str(value).startswith(_TEXT_PREFIX):
        return value
    return _TEXT_PREFIX + _f().encrypt(str(value).encode()).decode()


def decrypt_text(value):
    if not value or not str(value).startswith(_TEXT_PREFIX):
        return value  # legacy plaintext keeps working
    return _f().decrypt(str(value)[len(_TEXT_PREFIX):].encode()).decode()


# ---- files on disk ----
def encrypt_file(path: str) -> None:
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(_FILE_MAGIC):
        return
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(_FILE_MAGIC + _f().encrypt(data))
    os.replace(tmp, path)


def read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(_FILE_MAGIC):
        return _f().decrypt(data[len(_FILE_MAGIC):])
    return data  # legacy plaintext file


def decrypted_temp_copy(path: str) -> str:
    suffix = os.path.splitext(path)[1]
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        with open(tmp, "wb") as fh:
            fh.write(read_file_bytes(path))
    except Exception:
        os.remove(tmp)
        raise
    return tmp