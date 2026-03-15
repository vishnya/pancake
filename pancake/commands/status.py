"""lc status -- print current priorities."""

from pancake.priorities import load


def run():
    p = load()

    if p.active:
        print("ACTIVE:")
        for i, t in enumerate(p.active, 1):
            tag = f"[{t.project}] " if t.project else ""
            print(f"  {i}. {tag}{t.text}")
        print()

    if p.up_next:
        print("UP NEXT:")
        offset = len(p.active)
        for i, t in enumerate(p.up_next, offset + 1):
            tag = f"[{t.project}] " if t.project else ""
            print(f"  {i}. {tag}{t.text}")
        print()

    if p.done:
        print(f"DONE: {len(p.done)} items")
        print()

    if not p.active and not p.up_next:
        print("Nothing here yet. Start with:")
        print("  lc project add \"Project Name\" --desc \"short description\"")
        print("  lc add \"task\" --project \"Project Name\"")
