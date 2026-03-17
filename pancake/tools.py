"""Tool definitions and executor for Claude chat tool use."""

from pancake.priorities import load, save, Task, ProjectInfo, user_context_path, vault_path

# Optional callback set by the server for undo support
_snapshot_before_save = None


def _save(p):
    """Save with optional undo snapshot."""
    if _snapshot_before_save:
        _snapshot_before_save()
    save(p)


TOOLS = [
    {
        "name": "add_task",
        "description": "Add a task. If the user specifies a section (active, up_next), put it there. If no section is specified and the task has no project, put it in inbox. If a project is mentioned, use add_project_task instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The task text",
                },
                "project": {
                    "type": "string",
                    "description": "Optional project tag for the task",
                },
                "section": {
                    "type": "string",
                    "enum": ["active", "up_next", "inbox"],
                    "description": "Which section to add to. Defaults to inbox for unassigned tasks.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "add_project",
        "description": "Create a new project. Use this when the user wants to start tracking a new project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name",
                },
                "description": {
                    "type": "string",
                    "description": "Optional one-line project description",
                },
                "first_task": {
                    "type": "string",
                    "description": "Optional first task to add to the project",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "add_project_task",
        "description": "Add a task to a specific project's backlog. Use this when the user wants to add a task to a particular project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name (fuzzy matched)",
                },
                "text": {
                    "type": "string",
                    "description": "The task text",
                },
            },
            "required": ["project", "text"],
        },
    },
    {
        "name": "save_user_context",
        "description": "Save or update what you know about the user -- their role, goals, working style, constraints, preferences. Call this whenever the user shares meaningful context about themselves. Replaces the previous saved context entirely, so include everything relevant. Use Obsidian [[wikilinks]] when referencing projects (e.g. [[Anki Fox]], [[Pancake]]).",
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "The full user context to save as markdown. Write in third person, factual. Include all known details. Use [[wikilinks]] for project references.",
                },
            },
            "required": ["context"],
        },
    },
    {
        "name": "update_project",
        "description": "Update a project's description. Use this when the user shares context about a project -- its purpose, direction, or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name (fuzzy matched)",
                },
                "description": {
                    "type": "string",
                    "description": "New project description",
                },
            },
            "required": ["project", "description"],
        },
    },
    {
        "name": "reorder_up_next",
        "description": "Reorder the Up Next task list. Provide the task texts in the desired order. Tasks not mentioned are appended at the end in their original order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task texts in the desired priority order (first = highest priority). Fuzzy matched.",
                },
            },
            "required": ["task_texts"],
        },
    },
    {
        "name": "mark_done",
        "description": "Mark a task as done by fuzzy-matching its text. Searches active tasks, up next, and project backlogs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to fuzzy-match against existing tasks",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "set_priority",
        "description": "Set the priority level of a task. Use this when stack-ranking tasks or when the user indicates something is high priority. 0 = normal (default), 1 = important (!), 2 = critical (!!). Searches active tasks, up next, and project backlogs by fuzzy match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to fuzzy-match against existing tasks",
                },
                "priority": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "description": "Priority level: 0=normal, 1=important (!), 2=critical (!!)",
                },
            },
            "required": ["text", "priority"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> str:
    """Execute a tool call and return a result string."""
    p = load()

    if name == "add_task":
        task = Task(text=tool_input["text"], project=tool_input.get("project", ""))
        section = tool_input.get("section", "inbox")
        if section == "active":
            p.active.append(task)
        elif section == "up_next":
            p.up_next.insert(0, task)
        else:
            p.inbox.append(task)
        _save(p)
        tag = f" [{task.project}]" if task.project else ""
        return f"Added{tag} \"{task.text}\" to {section.replace('_', ' ')}"

    elif name == "add_project":
        proj_name = tool_input["name"]
        if p.get_project(proj_name):
            return f"Project \"{proj_name}\" already exists"
        proj = ProjectInfo(name=proj_name, description=tool_input.get("description", ""))
        p.projects.append(proj)
        first_task = tool_input.get("first_task")
        if first_task:
            proj.tasks.append(Task(text=first_task, project=proj_name))
        _save(p)
        result = f"Created project \"{proj_name}\""
        if first_task:
            result += f" with task \"{first_task}\""
        return result

    elif name == "add_project_task":
        proj = p.find_project(tool_input["project"])
        if not proj:
            return f"No project matching \"{tool_input['project']}\" found"
        task = Task(text=tool_input["text"], project=proj.name)
        proj.tasks.append(task)
        _save(p)
        return f"Added \"{tool_input['text']}\" to {proj.name}"

    elif name == "save_user_context":
        path = user_context_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tool_input["context"])
        return "User context saved"

    elif name == "update_project":
        proj = p.find_project(tool_input["project"])
        if not proj:
            return f"No project matching \"{tool_input['project']}\" found"
        proj.description = tool_input["description"]
        _save(p)
        return f"Updated {proj.name} description"

    elif name == "reorder_up_next":
        ordered = []
        remaining = list(p.up_next)
        for text in tool_input["task_texts"]:
            best_task = None
            best_score = 0
            for task in remaining:
                score = _fuzzy_score(text.lower(), task.text.lower())
                if score > best_score:
                    best_score = score
                    best_task = task
            if best_task and best_score >= 0.3:
                ordered.append(best_task)
                remaining.remove(best_task)
        ordered.extend(remaining)
        p.up_next = ordered
        _save(p)
        return f"Reordered Up Next ({len(ordered)} tasks)"

    elif name == "mark_done":
        query = tool_input["text"].lower()
        best_task = None
        best_score = 0
        best_location = ""

        # Search active, up_next, inbox, and project backlogs
        for section_name, tasks in [("active", p.active), ("up_next", p.up_next), ("inbox", p.inbox)]:
            for task in tasks:
                score = _fuzzy_score(query, task.text.lower())
                if score > best_score:
                    best_score = score
                    best_task = task
                    best_location = section_name

        for proj in p.projects:
            for task in proj.tasks:
                score = _fuzzy_score(query, task.text.lower())
                if score > best_score:
                    best_score = score
                    best_task = task
                    best_location = f"project:{proj.name}"

        if not best_task or best_score < 0.3:
            return f"No task matching \"{tool_input['text']}\" found"

        # Remove from source and add to done
        if best_location == "active":
            p.active.remove(best_task)
        elif best_location == "up_next":
            p.up_next.remove(best_task)
        elif best_location == "inbox":
            p.inbox.remove(best_task)
        elif best_location.startswith("project:"):
            proj_name = best_location[8:]
            proj = p.get_project(proj_name)
            if proj:
                proj.tasks.remove(best_task)

        best_task.done = True
        p.done.insert(0, best_task)
        _save(p)
        return f"Marked \"{best_task.text}\" as done"

    elif name == "set_priority":
        query = tool_input["text"].lower()
        priority = tool_input["priority"]
        best_task, best_score = _find_task(p, query)
        if not best_task or best_score < 0.3:
            return f"No task matching \"{tool_input['text']}\" found"
        labels = {0: "normal", 1: "important (!)", 2: "critical (!!)"}
        best_task.priority = priority
        _save(p)
        return f"Set \"{best_task.text}\" to {labels[priority]} priority"

    return f"Unknown tool: {name}"


def _find_task(p, query):
    """Find best fuzzy-matching task across all sections. Returns (task, score)."""
    best_task = None
    best_score = 0
    for tasks in [p.active, p.up_next, p.inbox]:
        for task in tasks:
            score = _fuzzy_score(query, task.text.lower())
            if score > best_score:
                best_score = score
                best_task = task
    for proj in p.projects:
        for task in proj.tasks:
            score = _fuzzy_score(query, task.text.lower())
            if score > best_score:
                best_score = score
                best_task = task
    return best_task, best_score


def _fuzzy_score(query: str, text: str) -> float:
    """Simple fuzzy match score between 0 and 1."""
    if query == text:
        return 1.0
    if query in text:
        return 0.8 + (len(query) / len(text)) * 0.2
    # Word overlap
    query_words = set(query.split())
    text_words = set(text.split())
    if not query_words:
        return 0.0
    overlap = len(query_words & text_words)
    return overlap / len(query_words) * 0.7
