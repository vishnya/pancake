"""lc note -- quick note, tagged to first active task's project if any."""

from pancake.priorities import load, save, now_str


def run(text: str):
    p = load()
    tag = ""
    if p.active and p.active[0].project:
        tag = f" [{p.active[0].project}]"
    p.notes.append(f"[{now_str()}]{tag} {text}")
    save(p)
    print(f"Noted: {text}")
