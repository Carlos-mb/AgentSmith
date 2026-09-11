"""Exercise blocks of known test code without starting a worker process."""

import json
import sys
from io import StringIO
from unittest.mock import Mock

import pytest

from agent_smith.models import SandboxConfig
from agent_smith.sandbox import _make_safe_builtins, final_answer
from json_worker import WorkerProtocolError, execute_block


@pytest.fixture
def namespace():
    config = SandboxConfig(authorized_imports=[], allowed_directories=[])
    return {
        "__builtins__": _make_safe_builtins(config),
        "__name__": "__sandbox__",
        "final_answer": final_answer,
    }


def test_blocks_share_variables_and_function_globals(namespace):
    stream = StringIO()

    execute_block("x = 1\ndef get_x():\n    return x", namespace, stream)
    execute_block("x += 1\nresult = get_x()", namespace, stream)

    assert namespace["x"] == 2
    assert namespace["result"] == 2
    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert messages == [
        {
            "type": "done", "final_answer": None, "error": None,
            "truncated": False, "omitted": 0,
        },
        {
            "type": "done", "final_answer": None, "error": None,
            "truncated": False, "omitted": 0,
        },
    ]


def test_stdout_and_stderr_keep_order_and_are_restored(namespace):
    stream = StringIO()
    original_streams = (sys.stdout, sys.stderr)
    # Expose sys only to this fixed test code to exercise stderr redirection.
    namespace["sys"] = sys

    execute_block(
        "print('first', end='')\n"
        "print('second', end='', file=sys.stderr)\n"
        "print('third', end='')",
        namespace,
        stream,
    )

    assert (sys.stdout, sys.stderr) == original_streams
    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert messages[:-1] == [
        {"type": "output", "text": "first"},
        {"type": "output", "text": "second"},
        {"type": "output", "text": "third"},
    ]
    assert messages[-1]["type"] == "done"
    assert messages[-1]["error"] is None


def test_error_keeps_output_and_variables_for_next_block(namespace):
    stream = StringIO()
    original_streams = (sys.stdout, sys.stderr)

    execute_block(
        "x = 7\nprint('before', end='')\nraise ValueError('bad value')",
        namespace,
        stream,
    )

    assert (sys.stdout, sys.stderr) == original_streams
    assert namespace["x"] == 7
    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert messages == [
        {"type": "output", "text": "before"},
        {
            "type": "done", "final_answer": None,
            "error": "ValueError: bad value", "truncated": False, "omitted": 0,
        },
    ]

    next_stream = StringIO()
    execute_block("x += 1", namespace, next_stream)
    assert namespace["x"] == 8
    assert json.loads(next_stream.getvalue())["error"] is None


def test_syntax_error_is_reported(namespace):
    stream = StringIO()
    original_streams = (sys.stdout, sys.stderr)

    execute_block("if :", namespace, stream)

    assert (sys.stdout, sys.stderr) == original_streams
    message = json.loads(stream.getvalue())
    assert message["type"] == "done"
    assert message["error"].startswith("SyntaxError:")
    assert message["final_answer"] is None


@pytest.mark.parametrize("answer", ["complete answer", ""])
def test_final_answer_stops_the_block(namespace, answer):
    stream = StringIO()
    namespace["answer"] = answer
    original_streams = (sys.stdout, sys.stderr)

    execute_block("final_answer(answer)\nfinished = True", namespace, stream)

    assert (sys.stdout, sys.stderr) == original_streams
    assert "finished" not in namespace
    assert json.loads(stream.getvalue()) == {
        "type": "done", "final_answer": answer, "error": None,
        "truncated": False, "omitted": 0,
    }


def test_log_limit_keeps_final_answer_complete_and_resets_next_block(namespace):
    stream = StringIO()
    answer = "patch\n" * 4_000
    namespace["answer"] = answer

    execute_block(
        "print('x' * 12_005, end='')\nfinal_answer(answer)",
        namespace,
        stream,
    )

    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert messages == [
        {"type": "output", "text": "x" * 12_000},
        {"type": "truncated"},
        {
            "type": "done", "final_answer": answer, "error": None,
            "truncated": True, "omitted": 5,
        },
    ]

    next_stream = StringIO()
    execute_block("print('ok', end='')", namespace, next_stream)
    messages = [json.loads(line) for line in next_stream.getvalue().splitlines()]
    assert messages == [
        {"type": "output", "text": "ok"},
        {
            "type": "done", "final_answer": None, "error": None,
            "truncated": False, "omitted": 0,
        },
    ]


@pytest.mark.parametrize(
    "expression, exception_type, code",
    [
        ("KeyboardInterrupt()", KeyboardInterrupt, None),
        ("SystemExit()", SystemExit, None),
        ("SystemExit(3)", SystemExit, 3),
        ("SystemExit('bye')", SystemExit, "bye"),
    ],
)
def test_control_exit_is_reported_and_propagated(
    namespace, expression, exception_type, code,
):
    stream = StringIO()
    original_streams = (sys.stdout, sys.stderr)

    with pytest.raises(exception_type) as caught:
        execute_block(
            f"print('before', end='')\nraise {expression}\nfinished = True",
            namespace,
            stream,
        )

    assert (sys.stdout, sys.stderr) == original_streams
    assert "finished" not in namespace
    assert getattr(caught.value, "code", None) == code
    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert messages == [
        {"type": "output", "text": "before"},
        {"type": "control_exit", "exception": exception_type.__name__, "code": code},
    ]


def test_protocol_failure_propagates_without_sending_done(namespace):
    stream = Mock(spec=StringIO)
    error = OSError("Test channel failure.")
    stream.write.side_effect = error
    original_streams = (sys.stdout, sys.stderr)

    with pytest.raises(WorkerProtocolError) as caught:
        execute_block("print('hello')", namespace, stream)

    assert (sys.stdout, sys.stderr) == original_streams
    assert caught.value.__cause__ is error
    stream.write.assert_called_once()
    sent_message = json.loads(stream.write.call_args.args[0])
    assert sent_message["type"] == "output"
