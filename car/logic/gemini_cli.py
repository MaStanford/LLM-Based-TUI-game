"""
Generic CLI LLM interface.
Supports any command-line LLM tool that accepts a prompt via a flag and returns
output on stdout. Pre-configured for Gemini CLI and Claude CLI, but any tool
can be used via the "custom" preset or by editing settings.json.
"""

import subprocess
import logging
import json
import shutil

# Pre-configured CLI tool presets.
# Each preset defines the command and argument pattern.
# The prompt is always passed as the last argument.
CLI_PRESETS = {
    "gemini": {
        "command": "gemini",
        "args": ["--approval-mode=yolo", "-o", "text"],
        "description": "Google Gemini CLI",
    },
    "claude": {
        "command": "claude",
        "args": ["-p", "--output-format", "text"],
        "description": "Anthropic Claude CLI",
    },
}


def is_cli_tool_installed(tool_command: str) -> bool:
    """Checks if a CLI tool is installed and in the system's PATH."""
    return shutil.which(tool_command) is not None


def check_cli_auth(cli_preset: str = "gemini", custom_command: str = None) -> bool:
    """
    Checks if the configured CLI tool is installed and available.
    Only verifies the binary exists in PATH — actual invocation errors
    are handled at generation time with user-visible fallback warnings.
    """
    if cli_preset == "custom":
        command = custom_command or ""
        return is_cli_tool_installed(command.split()[0]) if command else False

    preset = CLI_PRESETS.get(cli_preset)
    if not preset:
        return False

    return is_cli_tool_installed(preset["command"])


def _build_command(prompt: str, cli_preset: str = "gemini",
                   custom_command: str = None, custom_args: str = None) -> list:
    """Build the subprocess command list for the configured CLI tool."""
    if cli_preset == "custom":
        # Custom command: user provides the full command name and args template
        # e.g. command="ollama", args="run llama3 -p"
        cmd_parts = [custom_command or "echo"]
        if custom_args:
            cmd_parts.extend(custom_args.split())
        cmd_parts.append(prompt)
        return cmd_parts

    preset = CLI_PRESETS.get(cli_preset)
    if not preset:
        raise ValueError(f"Unknown CLI preset: {cli_preset}")

    return [preset["command"]] + preset["args"] + [prompt]


def generate_with_cli(prompt: str, parse_json: bool = True, timeout: int = 120,
                      cli_preset: str = "gemini", custom_command: str = None,
                      custom_args: str = None) -> dict | str:
    """
    Calls the configured CLI LLM tool with the given prompt.
    If parse_json is True, returns the parsed JSON output.
    Otherwise, returns the raw string output.
    """
    # Check if the tool is installed
    if cli_preset == "custom":
        tool_name = custom_command or "unknown"
        if not custom_command or not is_cli_tool_installed(custom_command.split()[0]):
            logging.error(f"CLI tool '{tool_name}' not found.")
            return {"error": f"CLI tool '{tool_name}' not found."}
    else:
        preset = CLI_PRESETS.get(cli_preset)
        if not preset:
            return {"error": f"Unknown CLI preset: {cli_preset}"}
        tool_name = preset["description"]
        if not is_cli_tool_installed(preset["command"]):
            logging.error(f"{tool_name} not found. Please install it to use this feature.")
            return {"error": f"{tool_name} not found."}

    command = _build_command(prompt, cli_preset, custom_command, custom_args)

    try:
        logging.info(f"Calling {tool_name} (timeout={timeout}s)...")
        # stdin=DEVNULL prevents the subprocess from reading the terminal, which
        # would hang inside a Textual TUI where the terminal is in raw mode.
        result = subprocess.run(command, capture_output=True, text=True, check=True,
                                timeout=timeout, stdin=subprocess.DEVNULL)

        raw_output = result.stdout
        logging.info(f"--- RAW CLI LLM RESPONSE ---\n{raw_output}\n-----------------------------")

        if not parse_json:
            return raw_output

        cleaned_json = raw_output.strip().replace("```json", "").replace("```", "")
        try:
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            # Try to extract JSON object/array from surrounding text
            # (Claude may wrap JSON with explanatory text)
            import re
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned_json)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            logging.error(f"Failed to parse JSON from {tool_name} output. Raw: {raw_output[:500]}")
            return raw_output

    except subprocess.TimeoutExpired:
        logging.error(f"{tool_name} call timed out after {timeout} seconds.")
        return {"error": "Timeout", "details": f"{tool_name} timed out after {timeout} seconds."}
    except subprocess.CalledProcessError as e:
        logging.error(f"{tool_name} call failed with exit code {e.returncode}.")
        logging.error(f"Stderr: {e.stderr}")
        return {"error": f"{tool_name} call failed.", "details": e.stderr}
    except Exception as e:
        logging.error(f"An unexpected error occurred with {tool_name}: {e}", exc_info=True)
        return {"error": "An unexpected error occurred.", "details": str(e)}


# --- Backward compatibility ---
# These functions wrap the new generic interface to maintain the existing API
# used by gemini_cli.py callers.

def is_gemini_installed():
    """Checks if the Gemini CLI is installed."""
    return is_cli_tool_installed("gemini")

def check_gemini_auth() -> bool:
    """Checks if the Gemini CLI is authenticated."""
    return check_cli_auth("gemini")

def generate_with_gemini_cli(prompt: str, parse_json: bool = True, timeout: int = 120) -> dict | str:
    """Backward-compatible wrapper for Gemini CLI generation."""
    return generate_with_cli(prompt, parse_json=parse_json, timeout=timeout, cli_preset="gemini")
