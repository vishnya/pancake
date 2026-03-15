"""lc active, lc done, lc progress, lc bump, lc park -- task management."""

from pancake.priorities import load, save, Task, now_str, time_str
from pancake.session_status import SessionStatus

_status = SessionStatus()


def activate(n: int):
    """Move task N from Up Next to Active."""
    p = load()
    all_tasks = p.active + p.up_next
    if n < 1 or n > len(all_tasks):
        print(f"No task #{n}. You have {len(all_tasks)} tasks.")
        return
    idx = n - 1
    if idx < len(p.active):
        print(f"Task #{n} is already active.")
        return
    up_next_idx = idx - len(p.active)
    task = p.up_next.pop(up_next_idx)
    p.active.append(task)
    save(p)
    tag = f"[{task.project}] " if task.project else ""
    _status.write({"phase": "active", "status": "running", "detail": f"{tag}{task.text}"})
    print(f"Activated: {tag}{task.text}")


def mark_done(n: int | None = None):
    """Mark a task done. No arg = first active task. N = specific task."""
    p = load()
    all_tasks = p.active + p.up_next

    if n is not None:
        if n < 1 or n > len(all_tasks):
            print(f"No task #{n}. You have {len(all_tasks)} tasks.")
            return
        idx = n - 1
        if idx < len(p.active):
            task = p.active.pop(idx)
        else:
            task = p.up_next.pop(idx - len(p.active))
    else:
        if not p.active:
            print("No active tasks. Use `lc active N` to start one.")
            return
        task = p.active.pop(0)

    task.done = True
    p.done.insert(0, task)
    save(p)
    _status.write({"phase": "done", "status": "done", "summary": task.text})
    print(f"Done: {task.text}")
    if p.active:
        tag = f"[{p.active[0].project}] " if p.active[0].project else ""
        print(f"Still active: {tag}{p.active[0].text}")


def bump(n: int, to: int | None = None):
    """Move task N to position `to` (default: top of Up Next, or top of Active if already active)."""
    p = load()
    all_tasks = p.active + p.up_next
    if n < 1 or n > len(all_tasks):
        print(f"No task #{n}. You have {len(all_tasks)} tasks.")
        return

    idx = n - 1
    if idx < len(p.active):
        task = p.active.pop(idx)
    else:
        task = p.up_next.pop(idx - len(p.active))

    if to is not None:
        # Insert at specific position
        to_idx = to - 1
        if to_idx < len(p.active):
            p.active.insert(to_idx, task)
        else:
            p.up_next.insert(to_idx - len(p.active), task)
    else:
        # Default: move to top of up_next (position right after active)
        p.up_next.insert(0, task)

    save(p)
    tag = f"[{task.project}] " if task.project else ""
    dest = f"position {to}" if to else "top of Up Next"
    print(f"Bumped: {tag}{task.text} -> {dest}")


def park(n: int):
    """Move task N from Active back to top of Up Next."""
    p = load()
    if n < 1 or n > len(p.active):
        print(f"No active task #{n}. You have {len(p.active)} active tasks.")
        return
    task = p.active.pop(n - 1)
    p.up_next.insert(0, task)
    save(p)
    tag = f"[{task.project}] " if task.project else ""
    print(f"Parked: {tag}{task.text}")


def log_progress(text: str):
    p = load()
    if not p.active:
        print("No active tasks. Use `lc active N` first.")
        return
    tag = f"[{p.active[0].project}]" if p.active[0].project else ""
    p.notes.append(f"[{now_str()}] {tag} {text}")
    save(p)
    print(f"Logged: {text}")
