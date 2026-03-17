#!/usr/bin/env python3
"""Migrate existing single-user Pancake to multi-account/multi-profile.

Moves vault data to a 'personal' profile and creates initial config.
Safe to run multiple times (idempotent).
"""
import os
import sys
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pancake.accounts import (
    create_account, create_profile, get_account, get_profile,
    _config_dir, _data_root,
)

DATA_ROOT = _data_root()
VAULT_DIR = DATA_ROOT / "vault"
DATA_DIR = DATA_ROOT / "data"
OLD_VAULT = VAULT_DIR / "PRIORITIES.md"
NEW_VAULT_DIR = VAULT_DIR / "personal"


def migrate():
    print(f"Data root: {DATA_ROOT}")
    print(f"Config dir: {_config_dir()}")

    # 1. Create config directory
    _config_dir().mkdir(parents=True, exist_ok=True)

    # 2. Create account if needed
    password = os.environ.get("PANCAKE_PASSWORD", "")
    if not get_account("rachel"):
        if not password:
            print("ERROR: Set PANCAKE_PASSWORD env var to create the account")
            sys.exit(1)
        create_account("rachel", "Rachel", password)
        print("Created account: rachel")
    else:
        print("Account 'rachel' already exists")

    # 3. Create personal profile if needed
    if not get_profile("personal"):
        create_profile("personal", "Personal", "rachel")
        print("Created profile: personal")
    else:
        print("Profile 'personal' already exists")

    # 4. Move vault data
    if OLD_VAULT.exists() and not NEW_VAULT_DIR.exists():
        NEW_VAULT_DIR.mkdir(parents=True, exist_ok=True)
        # Move PRIORITIES.md
        shutil.move(str(OLD_VAULT), str(NEW_VAULT_DIR / "PRIORITIES.md"))
        print(f"Moved {OLD_VAULT} -> {NEW_VAULT_DIR / 'PRIORITIES.md'}")
        # Move About Me.md if exists
        about_me = VAULT_DIR / "About Me.md"
        if about_me.exists():
            shutil.move(str(about_me), str(NEW_VAULT_DIR / "About Me.md"))
            print(f"Moved About Me.md")
        # Move Projects/ if exists
        projects_dir = VAULT_DIR / "Projects"
        if projects_dir.exists():
            shutil.move(str(projects_dir), str(NEW_VAULT_DIR / "Projects"))
            print(f"Moved Projects/")
    elif NEW_VAULT_DIR.exists():
        print(f"Profile vault already exists at {NEW_VAULT_DIR}")
    else:
        print(f"No existing vault at {OLD_VAULT}, nothing to migrate")

    # 5. Move data directory contents to profile-scoped location
    profile_data = DATA_DIR / "profiles" / "personal"
    if not profile_data.exists():
        profile_data.mkdir(parents=True, exist_ok=True)
        (profile_data / "chat_sessions").mkdir(exist_ok=True)
        # Move undo/redo stacks if they exist
        for fname in ["undo_stack.json", "redo_stack.json"]:
            old = DATA_DIR / fname
            if old.exists():
                shutil.move(str(old), str(profile_data / fname))
                print(f"Moved {fname}")
        # Move chat sessions
        old_chat = DATA_DIR / "chat_sessions"
        new_chat = profile_data / "chat_sessions"
        if old_chat.exists():
            for f in old_chat.iterdir():
                shutil.move(str(f), str(new_chat / f.name))
            print(f"Moved chat sessions")
    else:
        print(f"Profile data already exists at {profile_data}")

    print("\nMigration complete!")
    print(f"Update PANCAKE_VAULT to: {NEW_VAULT_DIR / 'PRIORITIES.md'}")


if __name__ == "__main__":
    migrate()
