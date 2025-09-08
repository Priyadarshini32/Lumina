import os
from dotenv import load_dotenv
from agent import Agent
from llm_integration import LLMIntegration
from tools import ToolExecutionSystem
from terminal_interface import TerminalInterface
from action_history import ActionHistory
import json

def main():
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        return

    llm_integration = LLMIntegration(api_key=google_api_key)
    terminal_interface = TerminalInterface()
    action_history = ActionHistory()
    
    project_root = os.getcwd()
    
    from memory_manager import MemoryManager
    memory_manager = MemoryManager(project_root)
    
    tool_execution_system = ToolExecutionSystem(action_history, memory_manager)
    
    agent = Agent(llm_integration, tool_execution_system, terminal_interface, project_root)

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
    main()
