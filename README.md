# Lumina - AI CODING AGENT

This project implements an AI coding agent that interacts with the user through a terminal interface.  The agent uses the Gemini-1.5-flash model from Google's Generative AI API to understand and respond to user requests.  It can perform a variety of actions, including reading, writing, deleting, and modifying files; executing Git commands; running shell commands; linting and testing Python code; and answering coding-related questions.

**Key Features:**
* **Iterative Approach:** The agent operates using a Perceive-Reason-Act-Learn loop, breaking down complex tasks into smaller steps.
* **Tool Integration:**  The agent integrates several tools for file manipulation, Git operations, shell commands, code analysis, and more.
* **Memory Management:** The agent maintains memory of its actions and the project's state.
* **User Interface:** The `TerminalInterface` provides a simple text-based interaction.
* **Undo Functionality:**  Provides `undo_last_action` capability for recovering from destructive actions.
* **Help Functionality:** Users can type 'help' to get information about the agent's capabilities.
* **Status and History:** Users can check the agent's status and see the conversation history using 'status' and 'history' commands.

**File Summaries:**
* **main.py:** The main entry point of the application. It initializes the agent and the terminal interface, handles user input, and manages the agent's lifecycle.
* **llm_integration.py:** Contains the `LLMIntegration` class, which handles the interaction with Google's Generative AI API and the planning of actions.

This README provides a high-level overview.  For detailed information on specific functionalities, refer to the individual source code files.
