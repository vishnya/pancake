"""Pancake CLI entrypoint."""

import argparse
import sys

from pancake.commands import status, focus, note, drop, priority, morning, think, session


def main():
    parser = argparse.ArgumentParser(prog="lc", description="Pancake -- your second brain")
    sub = parser.add_subparsers(dest="command")

    # lc status
    sub.add_parser("status", help="Show current priorities")

    # lc morning
    sub.add_parser("morning", help="Morning review context")

    # lc think
    sub.add_parser("think", help="Load priorities context for Claude")

    # lc active N
    p_active = sub.add_parser("active", help="Move task N to Active")
    p_active.add_argument("n", type=int, help="Task number")

    # lc done [N]
    p_done = sub.add_parser("done", help="Mark task done (default: first active)")
    p_done.add_argument("n", nargs="?", type=int, help="Task number")

    # lc bump N [TO]
    p_bump = sub.add_parser("bump", help="Move task N to position TO (default: top of Up Next)")
    p_bump.add_argument("n", type=int, help="Task number to move")
    p_bump.add_argument("to", nargs="?", type=int, help="Target position")

    # lc park N
    p_park = sub.add_parser("park", help="Move active task N back to Up Next")
    p_park.add_argument("n", type=int, help="Active task number")

    # lc progress
    p_prog = sub.add_parser("progress", help="Log progress on active task")
    p_prog.add_argument("text", nargs="+", help="Progress note")

    # lc note
    p_note = sub.add_parser("note", help="Quick note")
    p_note.add_argument("text", nargs="+", help="Note text")

    # lc drop
    p_drop = sub.add_parser("drop", help="Drop a link (clipboard if no arg)")
    p_drop.add_argument("url", nargs="?", help="URL to drop")

    # lc add
    p_add = sub.add_parser("add", help="Add a task to Up Next")
    p_add.add_argument("text", nargs="+", help="Task description")
    p_add.add_argument("--level", choices=["!!", "!", "normal"], default="normal")
    p_add.add_argument("--project", "-p", help="Project name")

    # lc project add
    p_proj = sub.add_parser("project", help="Manage projects")
    proj_sub = p_proj.add_subparsers(dest="project_command")
    p_proj_add = proj_sub.add_parser("add", help="Create a new project")
    p_proj_add.add_argument("name", nargs="+", help="Project name")
    p_proj_add.add_argument("--desc", "-d", default="", help="Short description")

    # lc session
    p_sess = sub.add_parser("session", help="Cross-device session status")
    p_sess.add_argument("--pull", action="store_true")
    p_sess.add_argument("--push", action="store_true")
    p_sess.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args()

    if args.command is None:
        status.run()
    elif args.command == "status":
        status.run()
    elif args.command == "morning":
        morning.run()
    elif args.command == "think":
        think.run()
    elif args.command == "active":
        focus.activate(args.n)
    elif args.command == "done":
        focus.mark_done(args.n)
    elif args.command == "bump":
        focus.bump(args.n, args.to)
    elif args.command == "park":
        focus.park(args.n)
    elif args.command == "progress":
        focus.log_progress(" ".join(args.text))
    elif args.command == "note":
        note.run(" ".join(args.text))
    elif args.command == "drop":
        drop.run(args.url)
    elif args.command == "add":
        level = "" if args.level == "normal" else args.level
        priority.add(" ".join(args.text), level, project=args.project)
    elif args.command == "project":
        if args.project_command == "add":
            priority.add_project(" ".join(args.name), desc=args.desc)
        else:
            print("Usage: lc project add \"Name\" --desc \"description\"")
            sys.exit(1)
    elif args.command == "session":
        session.run(pull=args.pull, push=args.push, as_json=args.as_json)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
