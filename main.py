import os
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import language_tool_python
from rich.text import Text
from rich.rule import Rule
from dotenv import load_dotenv
from agent import Agent
from llm_integration import LLMIntegration
from tools import ToolExecutionSystem
from terminal_interface import TerminalInterface
from action_history import ActionHistory
from memory_manager import MemoryManager

# Reduce noisy gRPC/absl logs
os.environ.setdefault('GRPC_VERBOSITY', 'ERROR')
os.environ.setdefault('GRPC_CPP_LOG_LEVEL', 'ERROR')
os.environ.setdefault('ABSL_LOG_SEVERITY', 'fatal')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

# Initialize LanguageTool globally for efficiency
_global_language_tool = language_tool_python.LanguageTool('en-US')

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, terminal_interface, project_root):
        super().__init__()
        self.terminal_interface = terminal_interface
        self.project_root = project_root
        self._last_seen = {}
        self._last_hash = {}
        self._last_mtime = {}
        self._debounce_seconds = 0.05

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file_change(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._process_file_change(event.src_path)

    def _process_file_change(self, filepath):
        # Ensure it's a file within the project root and not a temporary file or hidden file
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.project_root, filepath)

        path_lower = filepath.lower()
        if (
            not os.path.exists(filepath)
            or os.path.isdir(filepath)
            or os.path.basename(filepath).startswith('.')
            or "___jb_tmp___" in path_lower
            or os.path.sep + 'venv' + os.path.sep in path_lower
            or os.path.sep + 'site-packages' + os.path.sep in path_lower
            or os.path.sep + '__pycache__' + os.path.sep in path_lower
            or os.path.sep + '.ai_agent_memory' + os.path.sep in path_lower
            or path_lower.endswith('.pyc')
            or path_lower.endswith('.pyo')
            or '.dist-info' in path_lower
            or '.egg-info' in path_lower
        ):
            return

        # Only check certain file types
        if not (path_lower.endswith('.py') or path_lower.endswith('.txt') or path_lower.endswith('.md')):
            return

        # Debounce duplicate rapid events
        now = time.time()
        last = self._last_seen.get(filepath, 0)
        if (now - last) < self._debounce_seconds:
            return
        self._last_seen[filepath] = now

        try:
            # Give the editor a moment to finish writing the file
            time.sleep(0.05)

            stat = os.stat(filepath)
            mtime_ns = stat.st_mtime_ns

            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Skip if mtime and hash unchanged
            import hashlib
            h = hashlib.sha256(content.encode('utf-8', errors='ignore')).hexdigest()
            if self._last_mtime.get(filepath) == mtime_ns and self._last_hash.get(filepath) == h:
                return
            self._last_mtime[filepath] = mtime_ns
            self._last_hash[filepath] = h

            filename = os.path.basename(filepath)
            errors = self.terminal_interface._check_content_for_errors(filename, content, _global_language_tool)
            if not errors:
                return  # fast path: no issues, no output

            # Use unified renderer for readability and allow applying fix here
            applied, new_content, chosen = self.terminal_interface._render_error_report(filepath, content, errors, allow_apply=True)

            # If apply reported not applied but we have a suggestion, try tool-based apply as fallback
            if (not applied) and chosen:
                try:
                    from tools import apply_code_change
                    result = apply_code_change(filepath, content, chosen)
                    if isinstance(result, dict) and result.get('status') == 'success':
                        applied = True
                        new_content = chosen
                        self.terminal_interface.display_message("Applied suggested fix via tool.", title="Auto-Check", style="green")
                except Exception:
                    pass

            # If applied, update mtime/hash and re-check once to confirm clean state
            if applied and isinstance(new_content, str):
                nh = hashlib.sha256(new_content.encode('utf-8', errors='ignore')).hexdigest()
                try:
                    os.utime(filepath, None)
                except Exception:
                    pass
                self._last_hash[filepath] = nh
                self._last_mtime[filepath] = os.stat(filepath).st_mtime_ns
                new_errors = self.terminal_interface._check_content_for_errors(filename, new_content, _global_language_tool)
                if not new_errors:
                    self.terminal_interface.display_message("Fix applied successfully. No remaining issues.", title="Auto-Check", style="green")
                else:
                    self.terminal_interface.display_message(f"Remaining issues after applying fix: {len(new_errors)}", title="Auto-Check", style="bold yellow")
        except Exception as e:
            self.terminal_interface.display_message(
                f"Error processing file {filepath}: {e}",
                title="Auto-Check Error", style="bold yellow"
            )

def main(llm_integration, terminal_interface, action_history, memory_manager, tool_execution_system, agent, project_root):
    terminal_interface.display_message("Welcome to the AI Coding Agent! Type 'exit' to quit.")
    terminal_interface.display_message("""I can:
- Read, write, delete, and clear content of files.
- Search for text within files.
- List directory contents.
- Perform various Git operations (e.g., status, diff, commit, branch, log).
- Run arbitrary shell commands.
- Perform code analysis (linting, testing), and attempt to automatically fix failing tests.
- Answer general coding and project-related questions.

You can also use these special commands:
- **--help**: Show the list of available functions and capabilities.
- **--status**: Get a summary of the agent's current memory and task state.
- **--history**: View the full conversation history.
- **undo**: Undo the last destructive action performed by the agent.""", title="What I can do:")

    while True:
        user_input = terminal_interface.get_user_input()
        if user_input.lower() == 'exit':
            terminal_interface.display_message("Exiting agent. Goodbye!")
            break
        elif user_input.lower() == '--help':
            tool_schemas = agent.get_tool_schemas()
            help_message = "# Agent Capabilities & Functions\n\n"
            for tool in tool_schemas:
                function = tool['function']
                name = function['name']
                description = function['description']
                parameters = function.get('parameters', {}).get('properties', {})
                required_params = function.get('parameters', {}).get('required', [])

                help_message += f"## `{name}`\n"
                help_message += f"**Description:** {description}\n\n"
                if parameters:
                    help_message += "**Parameters:**\n"
                    for param, details in parameters.items():
                        param_type = details.get('type')
                        param_desc = details.get('description')
                        is_required = "(Required)" if param in required_params else "(Optional)"
                        help_message += f"- `{param}`: {param_type} - {param_desc} {is_required}\n"
                else:
                    help_message += "**Parameters:** None\n"
                help_message += "\n"
            terminal_interface.display_message(help_message, title="Help & Capabilities")
            continue
        elif user_input.lower() == '--status':
            agent_status = agent.get_status()
            terminal_interface.display_status(agent_status)
            continue
        elif user_input.lower() == '--history':
            history = agent.get_conversation_history()
            terminal_interface.display_history(history)
            continue
        elif user_input.lower() == 'undo':
            terminal_interface.display_message("Undoing last action...", title="User Command")
            observation = tool_execution_system.execute_tool_from_dict({"function": {"name": "undo_last_action", "arguments": {}}})
            terminal_interface.display_tool_output(observation)
            agent.learn(observation)
            terminal_interface.display_message("The last action has been undone. The agent is now idle.", style="green")
            continue

        agent.run(user_input)

if __name__ == "__main__":
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not google_api_key:
        print("Error: GOOGLE_API_KEY or GEMINI_API_KEY environment variable not set.")
        exit(1) # Exit the program if no API key

    llm_integration = LLMIntegration(api_key=google_api_key)
    terminal_interface = TerminalInterface(llm_integration)
    action_history = ActionHistory()
    project_root = os.getcwd()
    memory_manager = MemoryManager(project_root)
    tool_execution_system = ToolExecutionSystem(action_history, memory_manager)
    agent = Agent(llm_integration, tool_execution_system, terminal_interface, project_root)

    # Setup and start watchdog observer
    event_handler = FileChangeHandler(terminal_interface, project_root)
    observer = Observer()
    observer.schedule(event_handler, project_root, recursive=True)
    observer.start()

    try:
        main(llm_integration, terminal_interface, action_history, memory_manager, tool_execution_system, agent, project_root)
    except KeyboardInterrupt:
        print("\nAgent interrupted. Shutting down...")
    finally:
        observer.stop()
        observer.join()
