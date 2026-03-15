"""lc add, lc project add -- manage tasks and projects."""

from pancake.priorities import load, save, Task, ProjectInfo


def add(text: str, level: str = "", project: str | None = None):
    """Add a task to Up Next."""
    p = load()

    proj_name = ""
    if project:
        proj = p.find_project(project)
        if proj:
            proj_name = proj.name
        else:
            print(f"No project matching \"{project}\". Projects: {', '.join(p.project_names())}")
            return

    prefix = f"{level} " if level else ""
    task = Task(text=f"{prefix}{text}", project=proj_name)

    # Insert by priority level
    if level == "!!":
        p.up_next.insert(0, task)
    elif level == "!":
        # After !! items
        insert_at = 0
        for i, t in enumerate(p.up_next):
            if not t.text.startswith("!! "):
                insert_at = i
                break
            insert_at = i + 1
        p.up_next.insert(insert_at, task)
    else:
        p.up_next.append(task)

    save(p)
    tag = f"[{proj_name}] " if proj_name else ""
    print(f"Added: {tag}{prefix}{text}")


def add_project(name: str, desc: str = ""):
    """Add a new project."""
    p = load()
    if p.get_project(name):
        print(f"Project \"{name}\" already exists.")
        return
    p.projects.append(ProjectInfo(name=name, description=desc))
    save(p)
    print(f"Created project: {name}")
