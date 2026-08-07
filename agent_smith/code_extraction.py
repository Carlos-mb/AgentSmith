import ast

def extract_python_code(llm_output: str) -> tuple[str, str]:

    code: str = ""
    feedback: str = ""
    if (llm_output == ""):
        feedback = "Model response was empty."
        return code, feedback

    feedback = "No valid Python code was found in the model response."

    code_starts = llm_output.find("```python")
    if (code_starts == -1):
        code_starts = llm_output.find("```py")
        if (code_starts != -1):
            code_starts = code_starts + 5
    else:
        code_starts = code_starts + 9

    if code_starts != -1:
        code_ends = llm_output.find("```", code_starts)
        if (code_ends != -1):
            code = llm_output[code_starts:code_ends].strip()

    if code != "":
        try:
            ast.parse(code)
            print(code_starts, code_ends, code)
            feedback = ""
        except SyntaxError:
            feedback = (
                "Malformed Python code block was interpreted without "
                "a closing fence."
            )

    print(f"Checking: {llm_output}")
    print(code, feedback)
    return code, feedback
