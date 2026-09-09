"""Trusted test worker. This is not a sandbox and never executes received code."""

import json
import os
import sys


CANDIDATES = {
    "bad": "def add(a, b):\n    return 0\n",
    "good": "def add(a, b):\n    return a + b\n",
}


def read_message() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    message = json.loads(line)
    if not isinstance(message, dict):
        raise ValueError("Expected a JSON object.")
    return message


def send_message(message: dict) -> None:
    message["pid"] = os.getpid()
    print(json.dumps(message), flush=True)


def main() -> None:
    while True:
        message = read_message()
        if message is None:
            return

        kind = message.get("type")
        if kind == "ping":
            if not isinstance(message.get("value"), str):
                raise ValueError("A ping needs a text value.")
            send_message({"type": "pong", "value": message["value"]})

        elif kind == "wait":
            # The supervisor must continue running to release this worker.
            send_message({"type": "waiting"})
            reply = read_message()
            if reply != {"type": "release"}:
                raise ValueError("Expected release.")
            send_message({"type": "released"})

        elif kind == "test_candidate":
            candidate = message.get("candidate")
            if candidate not in CANDIDATES:
                raise ValueError("Only the two fixed candidates are allowed.")
            send_message({
                "type": "tool_call",
                "name": "run_tests",
                "arguments": {
                    "code": CANDIDATES[candidate],
                    "test_imports": [],
                    "test_list": ["assert add(2, 3) == 5"],
                    "timeout_seconds": 10,
                },
            })
            reply = read_message()
            if reply is None or reply.get("type") != "tool_result":
                raise ValueError("Expected a tool result.")
            if not isinstance(reply.get("result"), dict):
                raise ValueError("Expected a result dictionary.")
            send_message({"type": "done", "result": reply["result"]})

        elif kind == "fail":
            raise ValueError("Controlled worker failure.")

        else:
            raise ValueError("Unknown test command.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
