import os
import secrets
from pathlib import Path
import pyzipper  # AES encryption

def gen_password(n=14):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))

def zip_with_password(files, zip_stream, password):
    """
    files, lista de tuplas, [(path, arcname), ...]
    zip_stream, io.BytesIO aberto para escrita
    password, str
    """
    with pyzipper.AESZipFile(zip_stream, "w", compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode("utf-8"))
        for path, arcname in files:
            path = Path(path)
            zf.write(str(path), arcname)

