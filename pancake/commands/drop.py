"""lc drop -- drop a link, tagged to first active task's project if any."""

import subprocess
from pancake.priorities import load, save, now_str


def run(url: str | None = None):
    if url is None:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        url = result.stdout.strip()
        if not url:
            print("Clipboard is empty. Pass a URL: lc drop <url>")
            return

    p = load()
    tag = ""
    if p.active and p.active[0].project:
        tag = f" [{p.active[0].project}]"
    p.notes.append(f"[{now_str()}]{tag} [link]({url})")
    save(p)
    print(f"Dropped: {url}")
