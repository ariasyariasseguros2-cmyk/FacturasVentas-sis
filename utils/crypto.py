import hashlib
import base64
import re
from typing import List, Optional

from bd import FERNET_PASSPHRASE

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes as _c_hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

try:
    from werkzeug.security import check_password_hash as _wz_check
    _WERKZEUG_AVAILABLE = True
except ImportError:
    try:
        import werkzeug.security
        _wz_check = werkzeug.security.check_password_hash
        _WERKZEUG_AVAILABLE = True
    except Exception:
        _WERKZEUG_AVAILABLE = False
        _wz_check = None  # type: ignore


FERNET_LEGACY_SALT_DEFAULT = "SIS-ARIAS"


def _detect_form(stored: str) -> str:
    s = (stored or "").strip()
    if not s:
        return "plain"
    if re.fullmatch(r"[A-Fa-f0-9]{32}", s):
        return "md5"
    if re.fullmatch(r"[A-Fa-f0-9]{64}", s):
        return "sha256"
    if s.count("$") >= 2 or s.startswith(("pbkdf2:", "scrypt:", "argon2:", "sha256:", "sha512:", "md5:")):
        return "werkzeug"
    if re.fullmatch(r"^gAAAAA[A-Za-z0-9_\-]{50,}={0,2}$", s):
        return "fernet"
    if len(s) > 64 and (s.endswith("=") or "-" in s or "_" in s):
        if _CRYPTO_AVAILABLE:
            return "fernet"
    return "plain"


def _legacy_derive_fernet_key(passphrase: str, salt: str) -> Optional[bytes]:
    if not _CRYPTO_AVAILABLE:
        return None
    try:
        salt_bytes = salt.encode("utf-8") if isinstance(salt, str) else salt
        kdf = PBKDF2HMAC(
            algorithm=_c_hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=100_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
    except Exception:
        return None


_PRIMARY_KEY: Optional[bytes] = None
_SECONDARY_KEYS: List[bytes] = []
_KEYS_READY = False


def _ensure_legacy_keys() -> List[bytes]:
    global _PRIMARY_KEY, _SECONDARY_KEYS, _KEYS_READY
    if _KEYS_READY:
        out = []
        if _PRIMARY_KEY:
            out.append(_PRIMARY_KEY)
        out.extend(_SECONDARY_KEYS)
        return out

    primaries = [
        (FERNET_PASSPHRASE, FERNET_LEGACY_SALT_DEFAULT),
        ("MiPassphraseSegura$2025", FERNET_LEGACY_SALT_DEFAULT),
        ("MiPassphraseSegura2025", FERNET_LEGACY_SALT_DEFAULT),
        (FERNET_PASSPHRASE, "SIS ARIAS"),
        (FERNET_PASSPHRASE, "sis_arias"),
        (FERNET_PASSPHRASE, "arias"),
        (FERNET_PASSPHRASE, "dominioncream"),
    ]
    seen = set()
    ordered: List[bytes] = []
    for pp, salt in primaries:
        k = _legacy_derive_fernet_key(pp, salt)
        if k and k not in seen:
            seen.add(k)
            ordered.append(k)

    if ordered:
        _PRIMARY_KEY = ordered[0]
        _SECONDARY_KEYS = ordered[1:]
    _KEYS_READY = True
    return list(ordered)


def verify_password(password: str, stored: str) -> bool:
    if not password or not stored:
        return False

    s_stored = stored.strip()
    s_pass = password

    if s_pass == s_stored:
        return True

    form = _detect_form(s_stored)

    if form == "md5":
        return hashlib.md5(s_pass.encode("utf-8")).hexdigest().lower() == s_stored.lower()

    if form == "sha256":
        return hashlib.sha256(s_pass.encode("utf-8")).hexdigest().lower() == s_stored.lower()

    if form == "werkzeug" and _WERKZEUG_AVAILABLE and _wz_check is not None:
        try:
            if _wz_check(s_stored, s_pass):
                return True
        except Exception:
            pass

    if form == "fernet" and _CRYPTO_AVAILABLE:
        pass_bytes = s_pass.encode("utf-8")
        tokens = [s_stored.encode("utf-8")]
        alt = s_stored
        rem = len(alt) % 4
        if rem:
            alt += "=" * (4 - rem)
        try:
            raw = base64.urlsafe_b64decode(alt.encode("utf-8"))
            norm = base64.urlsafe_b64encode(raw)
            tokens.append(norm)
        except Exception:
            pass
        tokens.append(s_stored.rstrip("=").encode("utf-8"))

        for key in _ensure_legacy_keys():
            try:
                f = Fernet(key)
            except Exception:
                continue
            for tok in tokens:
                try:
                    dec = f.decrypt(tok, ttl=None)
                    if dec == pass_bytes:
                        return True
                    try:
                        if dec.decode("utf-8", errors="strict") == s_pass:
                            return True
                    except Exception:
                        pass
                except (InvalidToken, Exception):
                    continue

    if form == "werkzeug" and _WERKZEUG_AVAILABLE and _wz_check is not None:
        try:
            if _wz_check(s_stored, s_pass):
                return True
        except Exception:
            pass
    if hashlib.md5(s_pass.encode("utf-8")).hexdigest().lower() == s_stored.lower():
        return True
    if hashlib.sha256(s_pass.encode("utf-8")).hexdigest().lower() == s_stored.lower():
        return True
    return False
