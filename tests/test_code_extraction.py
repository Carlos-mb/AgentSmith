from agent_smith.code_extraction import extract_python_code


def test_extract_python_fenced_block():
    llm_output = """
I will call the tool.

```python
result = run_tests(code="solution", test_imports=[], test_list=[])
print(result)
```
"""

    code, feedback = extract_python_code(llm_output)

    expected_code = (
        'result = run_tests(code="solution", test_imports=[], test_list=[])\n'
        "print(result)"
    )

    assert code == expected_code
    assert feedback == ""



# def test_extract_py_fenced_block():
#     llm_output = """
# ```py
# print("hello")
# ```
# """

#     code, feedback = extract_python_code(llm_output)

#     assert code == 'print("hello")'
#     assert feedback == ""


# def test_extract_unlabelled_fenced_block():
#     llm_output = """
# Here is the code:

# ```
# value = 42
# print(value)
# ```
# """

#     code, feedback = extract_python_code(llm_output)

#     expected_code = "value = 42\nprint(value)"

#     assert code == expected_code
#     assert feedback == ""


# def test_extract_raw_python():
#     llm_output = """
# result = run_tests(code="solution", test_imports=[], test_list=[])
# print(result)
# """

#     code, feedback = extract_python_code(llm_output)

#     expected_code = (
#         'result = run_tests(code="solution", test_imports=[], test_list=[])\n'
#         "print(result)"
#     )

#     assert code == expected_code
#     assert feedback == ""


# def test_extract_unclosed_python_block():
#     llm_output = """
# I will call the tool.

# ```python
# print("hello")
# """

#     code, feedback = extract_python_code(llm_output)

#     assert code == 'print("hello")'
#     assert feedback == (
#         "Malformed Python code block was interpreted without a closing fence."
#     )


# def test_reject_response_without_python():
#     llm_output = "I think we should inspect the tests first."

#     code, feedback = extract_python_code(llm_output)

#     assert code == ""
#     assert feedback == (
#         "No valid Python code was found in the model response."
#     )

def test_closed_block_with_syntax_error_is_rejected():
    code, feedback = extract_python_code("```python\ndef broken(\n```")

    assert code == ""
    assert feedback.startswith("Python syntax error on line 1:")
    assert "closing fence" not in feedback


def test_empty_response_has_specific_feedback():
    for response in ("", " \n\t"):
        assert extract_python_code(response) == ("", "Model response was empty.")


def test_response_without_code_is_rejected():
    assert extract_python_code("I will inspect the tests.") == (
        "", "No valid Python code was found in the model response."
    )


def test_unclosed_block_is_rejected_without_recovery():
    code, feedback = extract_python_code("```python\nprint('hello')")

    assert code == ""
    assert feedback == "Python code block is missing its closing fence; not executed."


def test_py_block_and_optional_end_code_marker():
    for suffix in ("", "<end_code>"):
        assert extract_python_code("```py\nprint('hello')\n```" + suffix) == (
            "print('hello')", ""
        )
