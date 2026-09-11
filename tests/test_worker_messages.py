"""Tests for sequential JSON messages using in-memory streams."""

import json
from io import StringIO
from unittest.mock import Mock

import pytest

from json_worker import WorkerProtocolError, _receive_message, _send_message


def test_send_preserves_text_in_one_line_and_flushes():
    # Mock delegates to StringIO and records whether flush was called.
    stream = Mock(wraps=StringIO())
    message = {"type": "output", "text": "primera línea\nsegunda línea"}

    _send_message(stream, message)

    text = stream.getvalue()
    assert text.endswith("\n")
    assert text.count("\n") == 1
    assert json.loads(text) == message
    stream.flush.assert_called_once()


def test_consecutive_messages_are_received_in_order():
    stream = StringIO()
    first = {"type": "execute", "code": "x = 1\nprint(x)"}
    second = {"type": "done", "final_answer": "", "error": None}

    _send_message(stream, first)
    _send_message(stream, second)
    stream.seek(0)

    assert _receive_message(stream) == first
    assert _receive_message(stream) == second
    assert _receive_message(stream) is None


def test_empty_input_returns_none():
    assert _receive_message(StringIO("")) is None


@pytest.mark.parametrize(
    "text",
    [
        "\n",
        "not json\n",
        "[]\n",
        "null\n",
        "{}\n",
        '{"type": 42}\n',
    ],
    ids=["blank-line", "invalid-json", "list", "null", "missing-type", "bad-type"],
)
def test_invalid_messages_raise_protocol_error(text):
    with pytest.raises(WorkerProtocolError):
        _receive_message(StringIO(text))


def test_non_serializable_message_raises_protocol_error():
    stream = StringIO()

    with pytest.raises(WorkerProtocolError) as caught:
        _send_message(stream, {"type": "output", "text": object()})

    assert isinstance(caught.value.__cause__, TypeError)
    assert stream.getvalue() == ""


@pytest.mark.parametrize("operation", ["write", "flush"])
def test_send_io_errors_raise_protocol_error(operation):
    stream = Mock(spec=StringIO)
    error = OSError("Test stream failure.")
    getattr(stream, operation).side_effect = error

    with pytest.raises(WorkerProtocolError) as caught:
        _send_message(stream, {"type": "ready"})

    assert caught.value.__cause__ is error


def test_receive_io_error_raises_protocol_error():
    stream = Mock(spec=StringIO)
    error = OSError("Test read failure.")
    stream.readline.side_effect = error

    with pytest.raises(WorkerProtocolError) as caught:
        _receive_message(stream)

    assert caught.value.__cause__ is error
