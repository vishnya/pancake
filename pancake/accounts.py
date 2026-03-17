"""Account, profile, and membership management for multi-user Pancake.

Storage: JSON config files in a config directory.
- accounts.json: [{id, display_name, password_hash}]
- profiles.json: [{id, display_name, owner}]
- memberships.json: [{account, profile, role}]

Passwords use PBKDF2-SHA256 (stdlib, no deps).
"""

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

def _config_dir() -> Path:
    return Path(os.environ.get("PANCAKE_CONFIG_DIR",
                                Path(os.environ.get("PANCAKE_DATA_ROOT", "/home/pancake")) / "config"))

# Module-level aliases for backward compat (read at import time for non-test use)
CONFIG_DIR = _config_dir()
DATA_ROOT = Path(os.environ.get("PANCAKE_DATA_ROOT", "/home/pancake"))


def _data_root() -> Path:
    return Path(os.environ.get("PANCAKE_DATA_ROOT", "/home/pancake"))


def _config_path(name: str) -> Path:
    return _config_dir() / name


def _load_json(name: str) -> list:
    path = _config_path(name)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_json(name: str, data: list) -> None:
    _config_dir().mkdir(parents=True, exist_ok=True)
    _config_path(name).write_text(json.dumps(data, indent=2))


# --- Password hashing (PBKDF2-SHA256) ---

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"pbkdf2:sha256:100000:{salt}:{dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        parts = hashed.split(":")
        if parts[0] != "pbkdf2" or len(parts) != 5:
            return False
        _, algo, iterations, salt, stored_hash = parts
        dk = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(dk.hex(), stored_hash)
    except (ValueError, IndexError):
        return False


# --- Accounts ---

def load_accounts() -> list[dict]:
    return _load_json("accounts.json")


def save_accounts(accounts: list[dict]) -> None:
    _save_json("accounts.json", accounts)


def get_account(account_id: str) -> dict | None:
    for a in load_accounts():
        if a["id"] == account_id:
            return a
    return None


def create_account(account_id: str, display_name: str, email: str, password: str) -> dict:
    accounts = load_accounts()
    if any(a["id"] == account_id for a in accounts):
        raise ValueError(f"Account '{account_id}' already exists")
    if email and any(a.get("email", "").lower() == email.lower() for a in accounts):
        raise ValueError(f"Email '{email}' is already registered")
    account = {"id": account_id, "display_name": display_name, "password_hash": hash_password(password)}
    if email:
        account["email"] = email.lower()
    accounts.append(account)
    save_accounts(accounts)
    return account


def authenticate(account_id: str, password: str) -> dict | None:
    account = get_account(account_id)
    if account and verify_password(password, account["password_hash"]):
        return account
    return None


# --- Profiles ---

def load_profiles() -> list[dict]:
    return _load_json("profiles.json")


def save_profiles(profiles: list[dict]) -> None:
    _save_json("profiles.json", profiles)


def get_profile(profile_id: str) -> dict | None:
    for p in load_profiles():
        if p["id"] == profile_id:
            return p
    return None


def create_profile(profile_id: str, display_name: str, owner: str) -> dict:
    profiles = load_profiles()
    if any(p["id"] == profile_id for p in profiles):
        raise ValueError(f"Profile '{profile_id}' already exists")
    profile = {"id": profile_id, "display_name": display_name, "owner": owner}
    profiles.append(profile)
    save_profiles(profiles)
    # Auto-create admin membership for owner
    add_membership(owner, profile_id, "admin")
    # Create vault and data directories
    root = _data_root()
    vault_dir = root / "vault" / profile_id
    vault_dir.mkdir(parents=True, exist_ok=True)
    data_dir = root / "data" / "profiles" / profile_id
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "chat_sessions").mkdir(exist_ok=True)
    return profile


# --- Memberships ---

def load_memberships() -> list[dict]:
    return _load_json("memberships.json")


def save_memberships(memberships: list[dict]) -> None:
    _save_json("memberships.json", memberships)


def get_memberships_for_account(account_id: str) -> list[dict]:
    """Return all memberships for an account, enriched with profile info."""
    memberships = load_memberships()
    profiles = {p["id"]: p for p in load_profiles()}
    result = []
    for m in memberships:
        if m["account"] == account_id:
            profile = profiles.get(m["profile"])
            if profile:
                result.append({
                    "profile_id": m["profile"],
                    "display_name": profile["display_name"],
                    "role": m["role"],
                })
    return result


def get_memberships_for_profile(profile_id: str) -> list[dict]:
    """Return all memberships for a profile, enriched with account info."""
    memberships = load_memberships()
    accounts = {a["id"]: a for a in load_accounts()}
    result = []
    for m in memberships:
        if m["profile"] == profile_id:
            account = accounts.get(m["account"])
            if account:
                result.append({
                    "account_id": m["account"],
                    "display_name": account["display_name"],
                    "role": m["role"],
                })
    return result


def has_access(account_id: str, profile_id: str) -> bool:
    return any(
        m["account"] == account_id and m["profile"] == profile_id
        for m in load_memberships()
    )


def get_role(account_id: str, profile_id: str) -> str | None:
    for m in load_memberships():
        if m["account"] == account_id and m["profile"] == profile_id:
            return m["role"]
    return None


def add_membership(account_id: str, profile_id: str, role: str = "member") -> None:
    memberships = load_memberships()
    # Don't duplicate
    if any(m["account"] == account_id and m["profile"] == profile_id for m in memberships):
        return
    memberships.append({"account": account_id, "profile": profile_id, "role": role})
    save_memberships(memberships)


def remove_membership(account_id: str, profile_id: str) -> None:
    memberships = load_memberships()
    memberships = [m for m in memberships if not (m["account"] == account_id and m["profile"] == profile_id)]
    save_memberships(memberships)


# --- Path helpers ---

def vault_path_for_profile(profile_id: str) -> Path:
    return _data_root() / "vault" / profile_id / "PRIORITIES.md"


def data_dir_for_profile(profile_id: str) -> Path:
    return _data_root() / "data" / "profiles" / profile_id


def user_context_path_for_profile(profile_id: str) -> Path:
    return _data_root() / "vault" / profile_id / "About Me.md"


def projects_dir_for_profile(profile_id: str) -> Path:
    return _data_root() / "vault" / profile_id / "Projects"


# --- Bootstrap: ensure at least one account and profile exist ---

def ensure_initialized(default_password: str | None = None) -> None:
    """Create default account and profile if config is empty."""
    accounts = load_accounts()
    if accounts:
        return
    password = default_password or os.environ.get("PANCAKE_PASSWORD", "")
    if not password:
        return
    create_account("rachel", "Rachel", "", password)
    create_profile("personal", "Personal", "rachel")
