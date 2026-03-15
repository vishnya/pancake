"""lc morning -- print context for morning review with Claude."""

from pancake.priorities import load, vault_path


def run():
    p = load()
    path = vault_path()

    if not path.exists():
        print("No PRIORITIES.md found. Run `lc priority add` to get started.")
        return

    print("=" * 60)
    print("MORNING REVIEW")
    print("=" * 60)
    print()
    print(path.read_text())
    print("=" * 60)
    print()
    print("Review your priorities above.")
    print("Use Claude (/morning) to talk through them,")
    print("or update directly:")
    print("  lc priority add \"task\" [--level !!|!]")
    print("  lc focus \"task\"")
    print("  lc done N")
