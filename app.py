import ast
import os
import subprocess
import sys
import tempfile

import streamlit as st
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.8-flash"

st.set_page_config(page_title="Code Reviewer Agent", page_icon="🐞")
st.title("🐞 Code Reviewer Agent")
st.caption("Paste Python code. I'll run it, find the bugs, fix them, and re-run to verify.")


# ---------- Settings ----------
def secret(name, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def require_password():
    pw = secret("APP_PASSWORD")
    if not pw or st.session_state.get("authed"):
        return
    entered = st.text_input("Password", type="password")
    if entered:
        if entered == pw:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()


require_password()

api_key = secret("GEMINI_API_KEY")
if not api_key:
    st.error("Missing GEMINI_API_KEY. Add it in the app's Secrets settings.")
    st.stop()

client = genai.Client(api_key=str(api_key).split()[0].strip())
MODEL = secret("GEMINI_MODEL", DEFAULT_MODEL)

SYSTEM = """You are a careful Python code reviewer.
Process:
1. Call check_syntax, then run_python on the ORIGINAL code.
2. If there are errors or bad behavior, explain the root cause in plain language.
3. Write a corrected version and call run_python on it to VERIFY it works. If it still fails, fix and re-run.
4. Final answer format: **Problems found**, **Fixed code** (in a python code block), **Verification** (actual output you observed).
Only claim something works if you actually ran it."""


# ---------- Tools ----------
def check_syntax(code: str) -> str:
    """Check Python code for syntax errors without running it."""
    try:
        ast.parse(code)
        return "Syntax OK."
    except SyntaxError as e:
        return f"SyntaxError on line {e.lineno}: {e.msg}"


def run_python(code: str) -> str:
    """Execute Python code and return its exit code, stdout and stderr."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "snippet.py")
        with open(path, "w") as f:
            f.write(code)
        try:
            p = subprocess.run(
                [sys.executable, path],
                capture_output=True, text=True, timeout=10, cwd=d,
                stdin=subprocess.DEVNULL,
                env={"PATH": os.environ.get("PATH", "")},  # hide API keys/secrets from user code
            )
            return f"EXIT CODE: {p.returncode}\nSTDOUT:\n{p.stdout[-2000:]}\nSTDERR:\n{p.stderr[-2000:]}"
        except subprocess.TimeoutExpired:
            return "ERROR: code timed out after 10 seconds (possible infinite loop)."


# ---------- Agent loop ----------
def run_agent(system, tools, contents, max_steps=12, on_tool=None):
    """Call LLM -> run requested tools -> repeat until the LLM gives a final answer."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    funcs = {f.__name__: f for f in tools}

    for _ in range(max_steps):
        resp = client.models.generate_content(model=MODEL, contents=contents, config=config)
        contents.append(resp.candidates[0].content)

        calls = resp.function_calls
        if not calls:
            return resp.text or ""

        parts = []
        for call in calls:
            args = dict(call.args)
            if on_tool:
                on_tool(call.name, args)
            try:
                output = funcs[call.name](**args)
            except Exception as e:
                output = f"Tool error: {e}"
            parts.append(types.Part.from_function_response(
                name=call.name, response={"result": str(output)}))
        contents.append(types.Content(role="user", parts=parts))

    return "Stopped: too many steps."


# ---------- UI ----------
EXAMPLE = '''def average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)

scores = [80, 90, "75", 100]
print("Average:", average(scores))
print("Average of empty list:", average([]))
'''

code = st.text_area("Python code to review", value=EXAMPLE, height=300)

if st.button("Review my code", type="primary"):
    if not code.strip():
        st.warning("Paste some code first.")
    elif len(code) > 5000:
        st.error("Please keep the code under 5000 characters.")
    else:
        logs = []
        prompt = f"Please review this code:\n\n```python\n{code}\n```"
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        with st.spinner("Agent is checking and running your code..."):
            try:
                reply = run_agent(SYSTEM, [check_syntax, run_python], contents,
                                  on_tool=lambda n, a: logs.append(f"{n}({str(a)[:150]}...)"))
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.stop()
        st.markdown(reply)
        with st.expander("🔧 Agent steps"):
            for line in logs:
                st.code(line)
