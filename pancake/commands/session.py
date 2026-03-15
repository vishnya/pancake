"""lc session -- check or push cross-device session status."""

from pancake.session_status import SessionStatus


def run(pull: bool = False, push: bool = False, as_json: bool = False):
    import json
    status = SessionStatus()

    if pull:
        status.pull()

    if push:
        status.push()
        print("Status pushed to remote.")
        return

    if as_json:
        data = status.read()
        print(json.dumps(data, indent=2) if data else "{}")
    else:
        print(status.format())
