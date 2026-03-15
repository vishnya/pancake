"""lc think -- print context for Claude conversation about priorities."""

from pancake.priorities import load


def run():
    p = load()

    print("CURRENT STATE:")
    print()

    if p.active:
        print("Active:")
        for t in p.active:
            tag = f"[{t.project}] " if t.project else ""
            print(f"  [ ] {tag}{t.text}")
        print()

    if p.up_next:
        print("Up Next:")
        for t in p.up_next:
            tag = f"[{t.project}] " if t.project else ""
            print(f"  [ ] {tag}{t.text}")
        print()

    if p.projects:
        print("Projects:")
        for proj in p.projects:
            desc = f" -- {proj.description}" if proj.description else ""
            print(f"  {proj.name}{desc}")
        print()

    if p.notes:
        print("Recent notes:")
        for n in p.notes[-5:]:
            print(f"  - {n}")
        print()

    if p.done:
        print(f"Done: {len(p.done)} items")
        print()

    print("Talk to Claude about what to prioritize next.")
    print("Claude can edit PRIORITIES.md directly when you agree on changes.")
