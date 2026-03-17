"""Tests for multi-account, multi-profile system."""

import json
import os
import tempfile
import shutil

_acct_tmpdir = tempfile.mkdtemp(prefix="pancake_acct_test_")
_orig_config = os.environ.get("PANCAKE_CONFIG_DIR")
_orig_root = os.environ.get("PANCAKE_DATA_ROOT")
_orig_vault = os.environ.get("PANCAKE_VAULT")
os.environ["PANCAKE_CONFIG_DIR"] = os.path.join(_acct_tmpdir, "config")
os.environ["PANCAKE_DATA_ROOT"] = _acct_tmpdir
os.environ["PANCAKE_VAULT"] = os.path.join(_acct_tmpdir, "vault", "test", "PRIORITIES.md")

from pancake.accounts import (
    hash_password, verify_password,
    load_accounts, save_accounts, get_account, create_account, authenticate,
    load_profiles, save_profiles, get_profile, create_profile,
    load_memberships, get_memberships_for_account, get_memberships_for_profile,
    has_access, get_role, add_membership, remove_membership,
    vault_path_for_profile, data_dir_for_profile, user_context_path_for_profile,
    projects_dir_for_profile, ensure_initialized,
    _config_dir, _data_root,
)

import pytest


@pytest.fixture(autouse=True)
def clean_config():
    """Reset config files before and after each test."""
    def _clean():
        config_dir = _config_dir()
        if config_dir.exists():
            shutil.rmtree(config_dir)
        config_dir.mkdir(parents=True, exist_ok=True)
        root = _data_root()
        vault_dir = root / "vault"
        if vault_dir.exists():
            shutil.rmtree(vault_dir)
        data_dir = root / "data"
        if data_dir.exists():
            shutil.rmtree(data_dir)
    _clean()
    yield
    # Clean after test too, so server tests don't see leftover accounts
    _clean()
    # Restore original env vars so server tests use their own paths
    if _orig_config:
        os.environ["PANCAKE_CONFIG_DIR"] = _orig_config
    elif "PANCAKE_CONFIG_DIR" in os.environ:
        os.environ["PANCAKE_CONFIG_DIR"] = os.path.join(os.environ.get("PANCAKE_DATA_ROOT", "/tmp"), "config")
    if _orig_root:
        os.environ["PANCAKE_DATA_ROOT"] = _orig_root
    if _orig_vault:
        os.environ["PANCAKE_VAULT"] = _orig_vault


# === Password hashing ===

def test_hash_and_verify():
    h = hash_password("mypassword")
    assert verify_password("mypassword", h)
    assert not verify_password("wrongpassword", h)


def test_hash_format():
    h = hash_password("test")
    parts = h.split(":")
    assert parts[0] == "pbkdf2"
    assert parts[1] == "sha256"
    assert parts[2] == "100000"
    assert len(parts) == 5


def test_verify_rejects_invalid_hash():
    assert not verify_password("test", "invalid")
    assert not verify_password("test", "")
    assert not verify_password("test", "a:b:c")


def test_different_passwords_different_hashes():
    h1 = hash_password("password1")
    h2 = hash_password("password1")
    # Different salts = different hashes
    assert h1 != h2
    # Both verify
    assert verify_password("password1", h1)
    assert verify_password("password1", h2)


# === Accounts ===

def test_create_account():
    a = create_account("alice", "Alice", "", "pass123")
    assert a["id"] == "alice"
    assert a["display_name"] == "Alice"
    assert "password_hash" in a


def test_create_duplicate_account_raises():
    create_account("alice", "Alice", "", "pass")
    with pytest.raises(ValueError, match="already exists"):
        create_account("alice", "Alice2", "", "pass2")


def test_get_account():
    create_account("bob", "Bob", "", "bobpass")
    a = get_account("bob")
    assert a is not None
    assert a["id"] == "bob"
    assert get_account("nonexistent") is None


def test_authenticate_success():
    create_account("carol", "Carol", "", "secret")
    a = authenticate("carol", "secret")
    assert a is not None
    assert a["id"] == "carol"


def test_authenticate_wrong_password():
    create_account("dave", "Dave", "", "correct")
    assert authenticate("dave", "wrong") is None


def test_authenticate_nonexistent_user():
    assert authenticate("nobody", "pass") is None


def test_load_save_accounts_roundtrip():
    create_account("eve", "Eve", "", "evepass")
    create_account("frank", "Frank", "", "frankpass")
    accounts = load_accounts()
    assert len(accounts) == 2
    assert accounts[0]["id"] == "eve"
    assert accounts[1]["id"] == "frank"


# === Profiles ===

def test_create_profile():
    create_account("alice", "Alice", "", "pass")
    p = create_profile("alice-personal", "Personal", "alice")
    assert p["id"] == "alice-personal"
    assert p["display_name"] == "Personal"
    assert p["owner"] == "alice"


def test_create_profile_creates_directories():
    create_account("alice", "Alice", "", "pass")
    create_profile("myprof", "My Profile", "alice")
    root = _data_root()
    assert (root / "vault" / "myprof").is_dir()
    assert (root / "data" / "profiles" / "myprof").is_dir()
    assert (root / "data" / "profiles" / "myprof" / "chat_sessions").is_dir()


def test_create_duplicate_profile_raises():
    create_account("alice", "Alice", "", "pass")
    create_profile("unique", "Unique", "alice")
    with pytest.raises(ValueError, match="already exists"):
        create_profile("unique", "Unique2", "alice")


def test_get_profile():
    create_account("alice", "Alice", "", "pass")
    create_profile("prof1", "Prof One", "alice")
    p = get_profile("prof1")
    assert p is not None
    assert p["display_name"] == "Prof One"
    assert get_profile("nonexistent") is None


def test_create_profile_auto_creates_admin_membership():
    create_account("alice", "Alice", "", "pass")
    create_profile("autoprof", "Auto", "alice")
    assert has_access("alice", "autoprof")
    assert get_role("alice", "autoprof") == "admin"


# === Memberships ===

def test_add_membership():
    create_account("alice", "Alice", "", "pass")
    create_account("bob", "Bob", "", "pass")
    create_profile("shared", "Shared", "alice")
    add_membership("bob", "shared", "member")
    assert has_access("bob", "shared")
    assert get_role("bob", "shared") == "member"


def test_no_duplicate_membership():
    create_account("alice", "Alice", "", "pass")
    create_profile("prof", "Prof", "alice")
    add_membership("alice", "prof", "admin")  # duplicate of auto-created
    memberships = load_memberships()
    alice_memberships = [m for m in memberships if m["account"] == "alice" and m["profile"] == "prof"]
    assert len(alice_memberships) == 1


def test_remove_membership():
    create_account("alice", "Alice", "", "pass")
    create_account("bob", "Bob", "", "pass")
    create_profile("shared", "Shared", "alice")
    add_membership("bob", "shared", "member")
    assert has_access("bob", "shared")
    remove_membership("bob", "shared")
    assert not has_access("bob", "shared")


def test_get_memberships_for_account():
    create_account("alice", "Alice", "", "pass")
    create_profile("prof1", "One", "alice")
    create_profile("prof2", "Two", "alice")
    memberships = get_memberships_for_account("alice")
    assert len(memberships) == 2
    assert {m["profile_id"] for m in memberships} == {"prof1", "prof2"}
    assert all(m["role"] == "admin" for m in memberships)


def test_get_memberships_for_profile():
    create_account("alice", "Alice", "", "pass")
    create_account("bob", "Bob", "", "pass")
    create_profile("family", "Family", "alice")
    add_membership("bob", "family", "member")
    members = get_memberships_for_profile("family")
    assert len(members) == 2
    roles = {m["account_id"]: m["role"] for m in members}
    assert roles["alice"] == "admin"
    assert roles["bob"] == "member"


def test_has_access():
    create_account("alice", "Alice", "", "pass")
    create_account("bob", "Bob", "", "pass")
    create_profile("private", "Private", "alice")
    assert has_access("alice", "private")
    assert not has_access("bob", "private")


def test_get_role():
    create_account("alice", "Alice", "", "pass")
    create_profile("prof", "Prof", "alice")
    assert get_role("alice", "prof") == "admin"
    assert get_role("nobody", "prof") is None


# === Path helpers ===

def test_vault_path_for_profile():
    p = vault_path_for_profile("myprof")
    assert str(p).endswith("vault/myprof/PRIORITIES.md")


def test_data_dir_for_profile():
    d = data_dir_for_profile("myprof")
    assert str(d).endswith("data/profiles/myprof")


def test_user_context_path_for_profile():
    p = user_context_path_for_profile("myprof")
    assert str(p).endswith("vault/myprof/About Me.md")


def test_projects_dir_for_profile():
    p = projects_dir_for_profile("myprof")
    assert str(p).endswith("vault/myprof/Projects")


# === Thread-local vault path ===

def test_thread_local_vault_path():
    from pancake.priorities import set_active_profile, vault_path, get_active_profile
    # Default: uses env var
    set_active_profile(None)
    default_path = vault_path()
    assert "test" in str(default_path) or "PRIORITIES.md" in str(default_path)
    # With profile: uses profile path
    set_active_profile("myprof")
    profile_path = vault_path()
    assert "myprof" in str(profile_path)
    assert str(profile_path).endswith("PRIORITIES.md")
    # Cleanup
    set_active_profile(None)


def test_profile_scoped_load_save():
    """Loading and saving works per-profile."""
    from pancake.priorities import set_active_profile, load, save, Priorities, Task
    create_account("alice", "Alice", "", "pass")
    create_profile("p1", "Profile 1", "alice")
    create_profile("p2", "Profile 2", "alice")

    # Save different data to each profile
    set_active_profile("p1")
    save(Priorities(active=[Task(text="task in p1")]))

    set_active_profile("p2")
    save(Priorities(active=[Task(text="task in p2")]))

    # Load and verify isolation
    set_active_profile("p1")
    p1 = load()
    assert len(p1.active) == 1
    assert p1.active[0].text == "task in p1"

    set_active_profile("p2")
    p2 = load()
    assert len(p2.active) == 1
    assert p2.active[0].text == "task in p2"

    set_active_profile(None)


# === Ensure initialized ===

def test_ensure_initialized_creates_default():
    ensure_initialized("testpass")
    accounts = load_accounts()
    assert len(accounts) == 1
    assert accounts[0]["id"] == "rachel"
    profiles = load_profiles()
    assert len(profiles) == 1
    assert profiles[0]["id"] == "personal"
    assert has_access("rachel", "personal")


def test_ensure_initialized_idempotent():
    ensure_initialized("testpass")
    ensure_initialized("testpass")
    assert len(load_accounts()) == 1


def test_ensure_initialized_skips_without_password():
    os.environ.pop("PANCAKE_PASSWORD", None)
    ensure_initialized()
    assert len(load_accounts()) == 0


# === Family sharing scenario ===

def test_family_sharing_scenario():
    """End-to-end: Rachel creates Family profile, invites Dan."""
    from pancake.priorities import set_active_profile, load, save, Priorities, Task
    create_account("rachel", "Rachel", "", "rpass")
    create_account("dan", "Dan", "", "dpass")
    create_profile("personal", "Personal", "rachel")
    create_profile("family", "Family", "rachel")
    create_profile("dan-board", "Dan's Board", "dan")
    add_membership("dan", "family", "member")

    # Rachel's memberships
    r_memberships = get_memberships_for_account("rachel")
    assert len(r_memberships) == 2
    assert {m["profile_id"] for m in r_memberships} == {"personal", "family"}

    # Dan's memberships
    d_memberships = get_memberships_for_account("dan")
    assert len(d_memberships) == 2
    assert {m["profile_id"] for m in d_memberships} == {"dan-board", "family"}

    # Rachel writes to Family
    set_active_profile("family")
    save(Priorities(active=[Task(text="grocery shopping")]))

    # Dan reads Family — same data
    set_active_profile("family")
    p = load()
    assert len(p.active) == 1
    assert p.active[0].text == "grocery shopping"

    # Dan's personal board is isolated
    set_active_profile("dan-board")
    p = load()
    assert len(p.active) == 0

    # Rachel's personal board is isolated
    set_active_profile("personal")
    p = load()
    assert len(p.active) == 0

    set_active_profile(None)


# === Permissions ===

def test_admin_vs_member_access():
    create_account("rachel", "Rachel", "", "pass")
    create_account("dan", "Dan", "", "pass")
    create_profile("family", "Family", "rachel")
    add_membership("dan", "family", "member")
    assert get_role("rachel", "family") == "admin"
    assert get_role("dan", "family") == "member"
    # Both have access
    assert has_access("rachel", "family")
    assert has_access("dan", "family")
    # Outsider has no access
    create_account("stranger", "Stranger", "", "pass")
    assert not has_access("stranger", "family")
