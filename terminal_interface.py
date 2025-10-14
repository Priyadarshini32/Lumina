from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.columns import Columns
from rich.rule import Rule
import json
import tempfile
import subprocess
import os
import language_tool_python
import threading


class TerminalInterface:
    def __init__(self, llm_integration):
        self.console = Console()
        self.llm_integration = llm_integration
        self._input_lock = threading.Lock()

    def display_message(self, message, style="green", title=None):
        if "```" in message:
            parts = message.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    code_lines = part.split('\n')
                    lang = 'text'
                    if (code_lines and
                            code_lines[0].strip() in ['python', 'json', 'bash', 'diff']):
                        lang = code_lines[0].strip()
                        code = '\n'.join(code_lines[1:]).strip()
                    else:
                        code = part.strip()

                    syntax = Syntax(code, lang, theme="monokai",
                                    line_numbers=False)
                    self.console.print(
                        Panel(syntax, title=title if title else "Code",
                              border_style="yellow")
                    )
                else:
                    if part.strip():
                        # Always wrap agent text/markdown in a Panel
                        self.console.print(
                            Panel(Markdown(part.strip(), style=style),
                                  title=title, border_style="green")
                        )
        else:
            # Always wrap agent text/markdown in a Panel
            self.console.print(
                Panel(Markdown(message, style=style),
                      title=title, border_style="green")
            )

    def get_user_input(self, prompt="You: "):
        with self._input_lock:
            return self.console.input(f"[bold blue]{prompt}[/bold blue]")

    def display_agent_thought(self, thought):
        self.console.print(Panel(Text(f"{thought}", style="italic grey"),
                                  title="Agent Thinking", border_style="grey"))

    def display_tool_call(self, tool_call_json):
        tool_name = tool_call_json.get('function', {}).get(
            'name', 'unknown_tool'
        )
        tool_args = tool_call_json.get('function', {}).get('arguments', {})

        tool_text = Text()
        tool_text.append("Agent Calling Tool: ", style="bold magenta")
        tool_text.append(f"{tool_name}\n", style="magenta")

        if tool_args:
            tool_text.append("Arguments:\n", style="bold magenta")
            tool_text.append(json.dumps(tool_args, indent=2),
                             style="dim magenta")

        self.console.print(
            Panel(tool_text, title="Agent Action", border_style="magenta"))

    def display_tool_output(self, output):
        tool_name = output.get('tool_name', 'unknown_tool')
        if isinstance(output, dict) and output.get("status") == "success":
            content_to_display = output.get('content', '')
            if content_to_display:
                self.console.print(
                    Panel(
                        Text(
                            f"Tool Execution Successful! [{tool_name}]\n"
                            f"Content:\n{content_to_display}",
                            style="green"
                        ),
                        title="Tool Output",
                        border_style="green"
                    )
                )
            else:
                self.console.print(
                    Panel(Text(f"Tool Execution Successful! [{tool_name}]",
                               style="green"), title="Tool Output",
                          border_style="green")
                )
        elif isinstance(output, dict) and output.get("status") == "error":
            self.console.print(
                Panel(Text(f"Error in [{tool_name}]: {output['message']}",
                           style="bold red"), title="Tool Output",
                      border_style="red")
            )
        else:
            self.console.print(
                Panel(Text(f"Tool Output [{tool_name}]: {output}",
                           style="cyan"), title="Tool Output",
                      border_style="cyan")
            )

    def confirm_action(self, action_description, preview_content=None,
                       language=None):
        self.console.print(Rule(style="blue"))
        self.console.print(
            Panel(Text(action_description, style="bold blue"),
                  title="Action Required", border_style="blue")
        )

        if preview_content:
            self.console.print(
                Panel(Text("Preview of change:", style="italic blue"),
                      title="Preview", border_style="yellow")
            )
            if language:
                syntax = Syntax(preview_content, language, theme="monokai",
                                line_numbers=True)
                self.console.print(
                    Panel(syntax, title="Code Preview", border_style="yellow")
                )
            else:
                self.console.print(
                    Panel(Text(preview_content), title="Content Preview",
                          border_style="yellow")
                )

        response = self.console.input(
            "[bold yellow]Do you approve this action? (yes/no)[/bold yellow] "
        ).lower().strip()
        self.console.print(Rule(style="blue"))
        return response == 'yes'

    def _render_error_report(self, file_path, preview_content, errors,
                             allow_apply=False):
        applied = False
        new_content = None
        chosen_suggestion = None
        header = Panel(
            Text(f"Detected issues in manually changed file:\n{file_path}",
                 style="bold red"),
            title="Auto-Check Report",
            border_style="red"
        )
        self.console.print(header)

        # Separate plain errors and python suggestions
        plain_errors = []
        suggestion_code_blocks = []
        for err in errors:
            marker = "Python Correction Suggestion (from LLM):\n```python\n"
            if err.startswith(marker) and err.endswith("\n```"):
                code = err[len(marker):-4].strip()
                if code:
                    suggestion_code_blocks.append(code)
            else:
                plain_errors.append(err)

        # Grouped error list
        if plain_errors:
            error_list = "\n".join([f"{idx}. {e}"
                                    for idx, e in enumerate(plain_errors,
                                                            start=1)])
            self.console.print(
                Panel(Text(error_list, style="red"), title="Issues",
                      border_style="red")
            )

        # Side-by-side Original vs Suggested (first suggestion)
        chosen_suggestion = None
        if suggestion_code_blocks:
            chosen_suggestion = suggestion_code_blocks[0]
            try:
                original_syntax = Syntax(preview_content, "python",
                                         theme="monokai", line_numbers=True)
                suggested_syntax = Syntax(chosen_suggestion, "python",
                                          theme="monokai", line_numbers=True)
                left = Panel(original_syntax, title="Original",
                             border_style="red")
                right = Panel(suggested_syntax, title="Suggested Fix",
                              border_style="green")
                self.console.print(Columns([left, right]))
            except Exception:
                syntax = Syntax(chosen_suggestion, "python", theme="monokai",
                                line_numbers=True)
                self.console.print(
                    Panel(syntax, title="Suggested Fix",
                          border_style="green")
                )
        else:
            # If not Python suggestion, but we have grammar errors,
            # show a concise yellow suggestion list
            if any(err.startswith("Grammar Error") for err in errors):
                top = []
                for err in errors:
                    if err.startswith("Grammar Error"):
                        # Extract readable part before the long suggestions
                        parts = err.split('(Suggestions:')
                        top.append(parts[0].strip())
                        if len(top) >= 5:
                            break
                if top:
                    self.console.print(
                        Panel(Text("\n".join(top), style="yellow"),
                              title="Grammar Suggestions",
                              border_style="yellow")
                    )

        # Offer to apply the suggestion when allowed and we have a full path
        if (allow_apply and chosen_suggestion and isinstance(file_path, str)
                and os.path.isabs(file_path)):
            # The user's 'fix' or 'correct' command implies approval,
            # so automatically apply the fix
            try:
                normalized = chosen_suggestion.replace('\r\n', '\n')
                # Atomic write: write to temp in same dir, then replace
                dir_name = os.path.dirname(file_path)
                base_name = os.path.basename(file_path)
                import tempfile
                fd, temp_path = tempfile.mkstemp(prefix=base_name + '.',
                                                 suffix='.tmp', dir=dir_name,
                                                 text=True)
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8',
                                   newline='\n') as tf:
                        tf.write(normalized)
                        tf.flush()
                        os.fsync(tf.fileno())
                    os.replace(temp_path, file_path)
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                try:
                    os.utime(file_path, None)
                except Exception:
                    pass
                applied = True
                new_content = normalized
                self.console.print(
                    Panel(Text("Automatically applied suggested fix"
                               " successfully.", style="bold green"),
                          border_style="green")
                )
            except Exception as e:
                self.console.print(
                    Panel(Text(f"Failed to apply fix automatically: {e}",
                               style="bold red"), border_style="red")
                )

        self.console.print(Rule(style="red"))
        return applied, new_content, chosen_suggestion

    def _check_content_for_errors(self, filename, content,
                                  language_tool_instance=None):
        errors = []
        file_extension = os.path.splitext(filename)[1].lower()

        if not content.strip():  # If content is empty or only whitespace
            return errors  # No errors for empty content

        if file_extension == '.py':
            # Python linting with flake8
            with tempfile.NamedTemporaryFile(mode='w+', delete=False,
                                             suffix='.py') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            try:
                result = subprocess.run(
                    ['flake8', '--stdin-display-name', filename,
                     temp_file_path],
                    capture_output=True, text=True, check=False
                )
                if result.stdout:
                    # Parse flake8 output.
                    # Example: 'filename:line:col: E error-code message'
                    for line in result.stdout.splitlines():
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            # Extract relevant parts for display
                            # file_part = parts[0] # F841: file_part unused
                            line_num = parts[1]
                            col_num = parts[2]
                            error_message = parts[3].strip()
                            errors.append(
                                f"Python Linting Error "
                                f"[Code {error_message.split()[0]} "
                                f"| Line {line_num}, Col {col_num}]: "
                                f"{' '.join(error_message.split()[1:])}"
                            )
                        else:
                            errors.append(
                                f"Python Linting Error: {line.strip()}")
            except FileNotFoundError:
                errors.append(
                    "Python Linting Error: flake8 not found. "
                    "Please install it (`pip install flake8`)."
                )
            finally:
                os.remove(temp_file_path)

            # Generate a suggestion from LLM if there are Python errors
            if errors and self.llm_integration:
                lint_blob = os.linesep.join(errors)
                try:
                    llm_suggestion = (
                        self.llm_integration.suggest_python_fix(content,
                                                                lint_blob)
                    )
                    if llm_suggestion:
                        errors.append(
                            f"Python Correction Suggestion (from LLM):\n"
                            f"```python\n{llm_suggestion}\n```")
                except Exception:
                    errors.append("Python Correction Suggestion: "
                                  "unavailable (LLM error)")

        else:
            # General grammar checking with language_tool_python
            try:
                if language_tool_instance is None:
                    # Fallback if not provided, though it should be by now
                    tool = language_tool_python.LanguageTool('en-US')
                else:
                    tool = language_tool_instance
                matches = tool.check(content)
                for match in matches:
                    # Format for easier reading
                    message = match.message
                    line = content.count('\n', 0, match.offset) + 1
                    col = (match.offset
                           - content.rfind('\n', 0, match.offset)
                           if '\n' in content[:match.offset]
                           else match.offset)
                    errors.append(
                        f"Grammar Error [Line {line}, Col {col}]: {message} "
                        f"(Suggestions: {', '.join(match.replacements)})\n")
            except Exception as e:
                errors.append(f"Grammar Check Error: {e}")

        return errors

    def display_status(self, status_data):
        """Displays the agent's status in a readable, formatted manner."""
        status_text = (
            f"""
# Agent Status

- **Current Task State:** {status_data.get('task_state', 'N/A')}
- **Conversation Length:** {status_data.get('conversation_length', 'N/A')}

---

## Working Memory Summary

- **Session Duration:** {status_data['memory_summary']['session'].get('session_duration', 'N/A'):.2f} seconds
- **Cached Files:** {status_data['memory_summary']['session'].get('cached_files', 'N/A')}
- **Active Files:** {', '.join(status_data['memory_summary']['session'].get('active_files', []))}
- **Total Changes:** {status_data['memory_summary']['session'].get('total_changes', 'N/A')}
- **Recent Commands:** {status_data['memory_summary']['session'].get('recent_commands', 'N/A')}

---

## Persistent Memory Summary

"""
            f"- **Project Patterns:** {status_data['memory_summary']['persistent']['project_patterns'].get('total_patterns', 'N/A')} patterns "
            f"({', '.join(status_data['memory_summary']['persistent']['project_patterns'].get('pattern_types', []))})\n"
            f"- **User Preferences:** {status_data['memory_summary']['persistent']['user_preferences'].get('total_preferences', 'N/A')} preferences "
            f"({', '.join(status_data['memory_summary']['persistent']['user_preferences'].get('preference_types', []))})\n"
            f"- **Success Patterns:** {status_data['memory_summary']['persistent']['success_patterns'].get('total_patterns', 'N/A')} patterns "
            f"({', '.join(status_data['memory_summary']['persistent']['success_patterns'].get('pattern_types', []))})\n"
            f"- **Tool Effectiveness:** {status_data['memory_summary']['persistent']['tool_effectiveness'].get('total_tools', 'N/A')} tools "
            f"({', '.join(status_data['memory_summary']['persistent']['tool_effectiveness'].get('tools', []))})\n"
            f"- **File Access History:** {status_data['memory_summary']['persistent']['file_access_history'].get('total_files', 'N/A')} files accessed "
            f"({status_data['memory_summary']['persistent']['file_access_history'].get('total_accesses', 'N/A')} total accesses)\n"
            f"- **Code Snippets:** {status_data['memory_summary']['persistent']['code_snippets'].get('total_snippets', 'N/A')} snippets\n"
            f"""
---

## Session Details

- **Session ID:** {status_data['memory_summary'].get('session_id', 'N/A')}
"""
        )

        self.console.print(Panel(Markdown(status_text), title="Agent Status"))

    def display_history(self, history):
        """Displays the conversation history in a readable, formatted manner
        with clear visual separation."""
        if not history:
            self.console.print(
                Panel(Text("No conversation history available.",
                           style="italic"), title="Conversation History")
            )
            return

        self.console.print("\n")
        self.console.print(Rule(title="[bold blue]CONVERSATION HISTORY"
                                "[/bold blue]", style="blue"))

        exchange_number = 0
        current_exchange = {}

        for i, message in enumerate(history):
            role = message['role']
            content = message['content']

            if role == 'user':
                # Start of a new exchange
                if current_exchange:
                    self._display_exchange(exchange_number, current_exchange)
                    current_exchange = {}

                exchange_number += 1
                current_exchange['user'] = content

            elif role == 'model':
                if content.startswith("TOOL_CALL: "):
                    tool_call_data = json.loads(content.replace(
                        "TOOL_CALL: ", ""))
                    if 'tool_calls' not in current_exchange:
                        current_exchange['tool_calls'] = []
                    current_exchange['tool_calls'].append(tool_call_data)
                else:
                    current_exchange['agent_response'] = content

            elif role == 'tool_output':
                if 'tool_outputs' not in current_exchange:
                    current_exchange['tool_outputs'] = []
                current_exchange['tool_outputs'].append(json.loads(content))

            elif role == 'user_action':
                current_exchange['user_action'] = content

        # Display the last exchange
        if current_exchange:
            self._display_exchange(exchange_number, current_exchange)

        self.console.print(Rule(style="blue"))
        self.console.print("[dim]Total exchanges: {}[/dim]".format(
            exchange_number))

    def _display_exchange(self, number, exchange):
        """Display a single conversation exchange with proper formatting."""
        self.console.print(f"\n[bold cyan]Exchange {number}[/bold cyan]")
        self.console.print("-" * 60)

        # User input
        if 'user' in exchange:
            user_panel = Panel(
                Text(exchange['user'], style="white"),
                title="USR You",
                title_align="left",
                border_style="blue",
                padding=(0, 1)
            )
            self.console.print(user_panel)

        # Tool calls and outputs
        if 'tool_calls' in exchange:
            for i, tool_call in enumerate(exchange['tool_calls']):
                tool_name = tool_call.get('function', {}).get('name',
                                                               'unknown')
                tool_args = tool_call.get('function', {}).get('arguments', {})

                # Format tool call display
                tool_text = Text()
                tool_text.append("T Function: ", style="bold magenta")
                tool_text.append(f"{tool_name}\n", style="magenta")

                if tool_args:
                    tool_text.append("ARGS Arguments:\n", style="bold magenta")
                    tool_text.append(json.dumps(tool_args, indent=2),
                                     style="dim magenta")

                tool_panel = Panel(
                    tool_text,
                    title="AGT Tool Call",
                    title_align="left",
                    border_style="magenta",
                    padding=(0, 1)
                )
                self.console.print(tool_panel)

                # Corresponding tool output
                if ('tool_outputs' in exchange and
                        i < len(exchange['tool_outputs'])):
                    output = exchange['tool_outputs'][i]

                    output_text = Text()
                    status = output.get('status', 'unknown')

                    if status == 'success':
                        output_text.append("SUCCESS\n", style="bold green")
                    elif status == 'error':
                        output_text.append("ERROR\n", style="bold red")
                        output_text.append(f"Message: "
                                           f"{output.get('message', 'N/A')}\n",
                                           style="red")

                    if output.get('content'):
                        content = str(output['content'])
                        # Truncate very long content
                        if len(content) > 500:
                            content = (content[:500]
                                       + "\n... [content truncated]")
                        output_text.append(f"Content:\n{content}",
                                           style="cyan")

                    output_panel = Panel(
                        output_text,
                        title="TOOL Output",
                        title_align="left",
                        border_style="cyan" if status == 'success' else "red",
                        padding=(0, 1)
                    )
                    self.console.print(output_panel)

        # Agent response
        if 'agent_response' in exchange:
            # Check if response contains markdown or code
            response = exchange['agent_response']

            if "```" in response or response.startswith("#") or \
                    "**" in response:
                # Use markdown rendering for formatted responses
                agent_panel = Panel(
                    Markdown(response),
                    title="AGT Agent Response",
                    title_align="left",
                    border_style="green",
                    padding=(0, 1)
                )
            else:
                # Use plain text for simple responses
                agent_panel = Panel(
                    Text(response, style="white"),
                    title="AGT Agent Response",
                    title_align="left",
                    border_style="green",
                    padding=(0, 1)
                )
            self.console.print(agent_panel)

        # User action (if any)
        if 'user_action' in exchange:
            action_panel = Panel(
                Text(exchange['user_action'], style="yellow"),
                title="USR User Action",
                title_align="left",
                border_style="yellow",
                padding=(0, 1)
            )
            self.console.print(action_panel)

        self.console.print()  # Add spacing between exchanges