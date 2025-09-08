import os
import json
import subprocess
import shutil
import datetime
from action_history import ActionHistory
from memory_manager import MemoryManager


def _create_backup(filepath):
    """Creates a timestamped backup of the given file."""
    if os.path.exists(filepath):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.bak.{timestamp}"
        try:
            shutil.copy2(filepath, backup_path)
            return {"status": "success", "message": f"Backup created at {backup_path}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to create backup of {filepath}: {str(e)}"}
    return {"status": "success", "message": f"No file at {filepath} to backup."}

def read_file(filepath):
    """Reads the content of a specified file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        return {"status": "success", "content": content}
    except FileNotFoundError:
        # Try resolving common Python extension if missing
        base, ext = os.path.splitext(filepath)
        if ext == "":
            candidate = f"{filepath}.py"
            if os.path.exists(candidate):
                try:
                    with open(candidate, 'r') as f:
                        content = f.read()
                    return {"status": "success", "content": content}
                except Exception as e:
                    return {"status": "error", "message": str(e)}
        return {"status": "error", "message": f"File not found: {filepath}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def write_file(filepath, content):
    """Writes content to a specified file. Creates the file if it doesn't exist, overwrites if it does."""
    backup_result = _create_backup(filepath)
    if backup_result["status"] == "error":
        return backup_result

    try:
        with open(filepath, 'w') as f:
            f.write(content)
        return {"status": "success", "message": f"File {filepath} written successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def delete_file(filepath):
    """Deletes a specified file physically from the filesystem."""
    backup_result = _create_backup(filepath)
    if backup_result["status"] == "error":
        return backup_result

    try:
        os.remove(filepath)
        return {"status": "success", "message": f"File {filepath} deleted successfully."}
    except FileNotFoundError:
        return {"status": "error", "message": f"File not found: {filepath}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def clear_file_content(filepath):
    """Removes all content from a specified file, leaving an empty file."""
    backup_result = _create_backup(filepath)
    if backup_result["status"] == "error":
        return backup_result

    try:
        with open(filepath, 'w') as f:
            f.truncate(0)
        return {"status": "success", "message": f"Content of {filepath} cleared successfully."}
    except FileNotFoundError:
        return {"status": "error", "message": f"File not found: {filepath}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_git_command(command):
    """Runs any git command and returns its output."""
    try:
        import shlex
        cmd_parts = shlex.split(command)
        
        full_command = ['git'] + cmd_parts
        
        result = subprocess.run(full_command, capture_output=True, text=True, check=True, shell=True)
        return {"status": "success", "content": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Git command failed: {e.stderr.strip()}"}
    except FileNotFoundError:
        return {"status": "error", "message": "Git is not installed or not in PATH."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_command(command, env=None):
    """Runs any shell command and returns its standard output and standard error."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True, env=env, check=False)
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        if output and error:
            return {"status": "success", "content": f"Exit Code: {result.returncode}\nSTDOUT:\n{output}\nSTDERR:\n{error}"}
        elif output:
            return {"status": "success", "content": f"Exit Code: {result.returncode}\nSTDOUT:\n{output}"}
        elif error:
            return {"status": "success", "content": f"Exit Code: {result.returncode}\nSTDERR:\n{error}"}
        else:
            return {"status": "success", "content": f"Command executed successfully with no output. Exit Code: {result.returncode}"}

    except FileNotFoundError:
        return {"status": "error", "message": f"Command not found: '{command.split()[0]}'. Make sure it is installed and in your PATH."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_directory_contents():
    """Lists the contents (files and directories) of the current working directory."""
    try:
        items = os.listdir('.')
        filtered_items = [item for item in items if not (item.startswith('venv') or item.startswith('.'))]
        return {"status": "success", "content": "\n".join(filtered_items)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_files(query, filepath=None, directory_path=None):
    """Searches for a query string within files. Can search a specific file, a directory, or the current directory."""
    matching_lines = []
    if filepath:
        read_result = read_file(filepath)
        if read_result["status"] == "success":
            for line_num, line in enumerate(read_result["content"].splitlines()):
                if query in line:
                    matching_lines.append(f"{filepath}:{line_num + 1}: {line}")
        else:
            return read_result
    elif directory_path:
        for root, _, files in os.walk(directory_path):
            for file in files:
                full_path = os.path.join(root, file)
                read_result = read_file(full_path)
                if read_result["status"] == "success":
                    for line_num, line in enumerate(read_result["content"].splitlines()):
                        if query in line:
                            matching_lines.append(f"{full_path}:{line_num + 1}: {line}")
    else:
        for item in os.listdir('.'):
            if os.path.isfile(item):
                read_result = read_file(item)
                if read_result["status"] == "success":
                    for line_num, line in enumerate(read_result["content"].splitlines()):
                        if query in line:
                            matching_lines.append(f"{item}:{line_num + 1}: {line}")
    
    if matching_lines:
        return {"status": "success", "content": "\n".join(matching_lines)}
    else:
        return {"status": "success", "content": f"No lines found matching '{query}'."}

def run_linter(filepath=None, directory_path=None):
    """Runs a Python linter (pylint) on a specified file or directory, or the current directory if none specified."""
    command_parts = ["pylint"]
    if filepath:
        command_parts.append(filepath)
    elif directory_path:
        command_parts.append(directory_path)
    else:
        command_parts.append(".")
    
    command_str = " ".join(command_parts)
    
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()

    return run_command(command_str, env=env)

def run_tests(directory_path=None):
    """Runs Python tests (pytest) in a specified directory, or the current directory if none specified."""
    command = "pytest"
    if directory_path:
        command += f" {directory_path}"
    
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()

    return run_command(command, env=env)

def apply_code_change(filepath, old_code, new_code):
    """Applies a precise code change to a file by replacing old_code with new_code."""
    backup_result = _create_backup(filepath)
    if backup_result["status"] == "error":
        return backup_result

    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        if old_code not in content:
            return {"status": "error", "message": f"Old code not found in {filepath}. No change applied."}

        new_content = content.replace(old_code, new_code, 1)
        
        with open(filepath, 'w') as f:
            f.write(new_content)
        
        return {"status": "success", "message": f"Code change applied successfully to {filepath}."}
    except FileNotFoundError:
        return {"status": "error", "message": f"File not found: {filepath}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def undo_last_action(action_history: ActionHistory):
    """Undoes the last destructive action performed by the agent."""
    last_action = action_history.pop_last_action()
    if not last_action:
        return {"status": "error", "message": "No actions to undo."}

    action_type = last_action['type']
    details = last_action['details']

    try:
        if action_type == 'write_file':
            filepath = details['filepath']
            original_content = details['original_content']
            if original_content is None:
                os.remove(filepath)
                return {"status": "success", "message": f"Removed newly created file: {filepath}"}
            else:
                with open(filepath, 'w') as f:
                    f.write(original_content)
                return {"status": "success", "message": f"Restored {filepath} to its previous content."}
        elif action_type == 'delete_file':
            filepath = details['filepath']
            original_content = details['original_content']
            if original_content is not None:
                with open(filepath, 'w') as f:
                    f.write(original_content)
                return {"status": "success", "message": f"Restored deleted file: {filepath}"}
            else:
                return {"status": "error", "message": f"Could not restore deleted file {filepath}: No original content found."}
        elif action_type == 'clear_file_content':
            filepath = details['filepath']
            original_content = details['original_content']
            with open(filepath, 'w') as f:
                f.write(original_content)
            return {"status": "success", "message": f"Restored content of {filepath}."}
        elif action_type == 'apply_code_change':
            filepath = details['filepath']
            current_content = read_file(filepath)['content']
            old_code_for_undo = details['new_code']
            new_code_for_undo = details['old_code']

            if old_code_for_undo not in current_content:
                return {"status": "error", "message": f"Could not undo code change in {filepath}: Current content does not match expected state for undo."}

            undone_content = current_content.replace(old_code_for_undo, new_code_for_undo, 1)
            with open(filepath, 'w') as f:
                f.write(undone_content)
            return {"status": "success", "message": f"Undid code change in {filepath}."}
        else:
            return {"status": "error", "message": f"Unsupported action type for undo: {action_type}"}
    except Exception as e:
        return {"status": "error", "message": f"Error undoing action {action_type} on {details.get('filepath', '')}: {str(e)}"}


def get_memory_status(memory_manager):
    """Get a summary of the agent's memory status."""
    try:
        memory_summary = memory_manager.get_memory_summary()
        return {"status": "success", "content": memory_summary}
    except Exception as e:
        return {"status": "error", "message": f"Error getting memory status: {str(e)}"}


def search_memory_patterns(memory_manager, pattern_type=None, query=None):
    """Search for patterns in the agent's memory."""
    try:
        if pattern_type == "tool_effectiveness":
            patterns = memory_manager.get_tool_effectiveness()
            return {"status": "success", "content": patterns}
        else:
            context = {"query": query} if query else {}
            patterns = memory_manager.get_relevant_patterns(context, pattern_type)
            return {"status": "success", "content": patterns}
    except Exception as e:
        return {"status": "error", "message": f"Error searching memory patterns: {str(e)}"}


class ToolExecutionSystem:
    def __init__(self, action_history: ActionHistory, memory_manager: MemoryManager):
        self.action_history = action_history
        self.memory_manager = memory_manager
        self.available_tools = {
            "read_file": read_file,
            "write_file": self._wrapped_write_file,
            "delete_file": self._wrapped_delete_file,
            "clear_file_content": self._wrapped_clear_file_content,
            "run_git_command": run_git_command,
            "run_command": run_command,
            "list_directory_contents": list_directory_contents,
            "search_files": search_files,
            "run_linter": run_linter,
            "run_tests": run_tests,
            "apply_code_change": self._wrapped_apply_code_change,
            "undo_last_action": undo_last_action,
            "get_memory_status": get_memory_status,
            "search_memory_patterns": search_memory_patterns,
        }
        self.tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Reads the content of a specified file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The path to the file to read."
                            }
                        },
                        "required": ["filepath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Writes content to a specified file. Creates the file if it doesn't exist, overwrites if it does.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The path to the file to write."
                            },
                            "content": {
                                "type": "string",
                                "description": "The content to write to the file."
                            }
                        },
                        "required": ["filepath", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "Deletes a specified file physically from the filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The path to the file to delete."
                            }
                        },
                        "required": ["filepath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clear_file_content",
                    "description": "Removes all content from a specified file, leaving an empty file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The path to the file to clear."
                            }
                        },
                        "required": ["filepath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_git_command",
                    "description": "Runs any specified Git command (e.g., \"status\", \"diff\", \"commit -m \'message\'\").",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The Git command and its arguments as a single string (e.g., \"status\", \"diff --cached\")."
                            }
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Runs any shell command and returns its standard output and standard error.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to run (e.g., \"ls -l\", \"npm install\")."
                            }
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory_contents",
                    "description": "Lists the contents (files and directories) of the current working directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Searches for a query string within files. Can search a specific file, a directory, or the current directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The string to search for."
                            },
                            "filepath": {
                                "type": "string",
                                "description": "Optional: The path to a specific file to search within."
                            },
                            "directory_path": {
                                "type": "string",
                                "description": "Optional: The path to a directory to search within. If neither filepath nor directory_path is provided, the current directory will be searched."
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_linter",
                    "description": "Runs a Python linter (pylint) on a specified file or directory, or the current directory if none specified.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "Optional: The path to a specific file to lint."
                            },
                            "directory_path": {
                                "type": "string",
                                "description": "Optional: The path to a directory to lint. If neither is provided, the current directory will be linted."
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Runs Python tests (pytest) in a specified directory, or the current directory if none specified.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory_path": {
                                "type": "string",
                                "description": "Optional: The path to a directory containing tests to run. If not provided, tests in the current directory will be run."
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_code_change",
                    "description": "Applies a precise code change to a file by replacing old_code with new_code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The path to the file to modify."
                            },
                            "old_code": {
                                "type": "string",
                                "description": "The exact string of code to be replaced."
                            },
                            "new_code": {
                                "type": "string",
                                "description": "The new string of code to replace the old_code."
                            }
                        },
                        "required": ["filepath", "old_code", "new_code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "undo_last_action",
                    "description": "Undoes the last destructive action performed by the agent (e.g., file write, delete, clear, or code change).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_memory_status",
                    "description": "Get a summary of the agent's memory status including working and persistent memory statistics.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_memory_patterns",
                    "description": "Search for patterns in the agent's memory based on type and query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern_type": {
                                "type": "string",
                                "description": "Optional: Type of pattern to search for (e.g., 'success_pattern', 'project_pattern', 'user_preference')."
                            },
                            "query": {
                                "type": "string",
                                "description": "Optional: Search query to filter patterns."
                            }
                        },
                        "required": [],
                    },
                },
            },
        ]

    def _wrapped_write_file(self, filepath, content):
        original_content = None
        if os.path.exists(filepath):
            original_content = read_file(filepath).get('content')
        result = write_file(filepath, content)
        if result['status'] == 'success':
            self.action_history.record_action('write_file', {'filepath': filepath, 'original_content': original_content})
        return result

    def _wrapped_delete_file(self, filepath):
        original_content = None
        if os.path.exists(filepath):
            original_content = read_file(filepath).get('content')
        result = delete_file(filepath)
        if result['status'] == 'success':
            self.action_history.record_action('delete_file', {'filepath': filepath, 'original_content': original_content})
        return result

    def _wrapped_clear_file_content(self, filepath):
        original_content = None
        if os.path.exists(filepath):
            original_content = read_file(filepath).get('content')
        result = clear_file_content(filepath)
        if result['status'] == 'success':
            self.action_history.record_action('clear_file_content', {'filepath': filepath, 'original_content': original_content})
        return result

    def _wrapped_apply_code_change(self, filepath, old_code, new_code):
        result = apply_code_change(filepath, old_code, new_code)
        if result['status'] == 'success':
            self.action_history.record_action('apply_code_change', {'filepath': filepath, 'old_code': old_code, 'new_code': new_code})
        return result

    def execute_tool_from_dict(self, tool_call_dict):
        tool_name = tool_call_dict["function"]["name"]
        tool_args = tool_call_dict["function"]["arguments"]

        if tool_name in self.available_tools:
            tool_function = self.available_tools[tool_name]
            if tool_name == "undo_last_action":
                return tool_function(self.action_history)
            elif tool_name == "get_memory_status" and self.memory_manager:
                memory_summary = self.memory_manager.get_memory_summary()
                return {"status": "success", "content": json.dumps(memory_summary, indent=2)}
            elif tool_name == "search_memory_patterns" and self.memory_manager:
                pattern_type = tool_args.get("pattern_type")
                query = tool_args.get("query")
                result = search_memory_patterns(self.memory_manager, pattern_type, query)
                return {"status": result['status'], "content": json.dumps(result.get('content'), indent=2), "message": result.get('message')}
            else:
                return tool_function(**tool_args)
        else:
            return {"status": "error", "message": f"Tool {tool_name} not found."}