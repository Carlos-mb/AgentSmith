"""Tests for bounded worker output using in-memory streams."""

import json
from io import StringIO
from unittest.mock import Mock

import pytest

from json_worker import WorkerOutput, WorkerProtocolError


def test_write_sends_text_immediately():
    stream = Mock(wraps=StringIO())
    output = WorkerOutput(stream, max_characters=10)

    assert output.write("hola\n") == 5

    assert json.loads(stream.getvalue()) == {
        "type": "output", "text": "hola\n",
    }
    stream.flush.assert_called_once()
    assert output.sent == 5
    assert output.omitted == 0


def test_shared_limit_and_single_truncation_notice():
    stream = StringIO()
    output = WorkerOutput(stream, max_characters=5)

    assert output.write("ab") == 2
    assert output.write("cde") == 3

    expected = [
        {"type": "output", "text": "ab"},
        {"type": "output", "text": "cde"},
    ]
    assert [json.loads(line) for line in stream.getvalue().splitlines()] == expected
    assert output.sent == 5
    assert output.omitted == 0

    assert output.write("f") == 1
    expected.append({"type": "truncated"})
    assert [json.loads(line) for line in stream.getvalue().splitlines()] == expected
    assert output.omitted == 1

    assert output.write("gh") == 2
    assert [json.loads(line) for line in stream.getvalue().splitlines()] == expected
    assert output.sent == 5
    assert output.omitted == 3


def test_partial_write_sends_prefix_before_truncation_notice():
    stream = StringIO()
    output = WorkerOutput(stream, max_characters=4)

    assert output.write("abcdef") == 6

    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert messages == [
        {"type": "output", "text": "abcd"},
        {"type": "truncated"},
    ]
    assert output.sent == 4
    assert output.omitted == 2


@pytest.mark.parametrize("initial_text", ["", "abc", "abcd"])
def test_empty_write_changes_nothing(initial_text):
    stream = StringIO()
    output = WorkerOutput(stream, max_characters=3)
    output.write(initial_text)
    previous_messages = stream.getvalue()
    previous_sent = output.sent
    previous_omitted = output.omitted

    assert output.write("") == 0

    assert stream.getvalue() == previous_messages
    assert output.sent == previous_sent
    assert output.omitted == previous_omitted


def test_print_can_use_worker_output():
    stream = StringIO()
    output = WorkerOutput(stream, max_characters=10)

    print("hola", file=output, flush=True)

    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert all(message["type"] == "output" for message in messages)
    assert "".join(message["text"] for message in messages) == "hola\n"
    assert output.sent == 5
    assert output.omitted == 0


def test_flush_delegates_without_sending_messages():
    stream = Mock(wraps=StringIO())
    output = WorkerOutput(stream)

    output.flush()

    stream.flush.assert_called_once()
    assert stream.getvalue() == ""
    assert output.sent == 0
    assert output.omitted == 0


def test_flush_failure_raises_protocol_error():
    stream = Mock(spec=StringIO)
    error = OSError("Test flush failure.")
    stream.flush.side_effect = error
    output = WorkerOutput(stream)

    with pytest.raises(WorkerProtocolError) as caught:
        output.flush()

    assert caught.value.__cause__ is error
