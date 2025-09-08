"""
Core AI coding agent with Perceive -> Reason -> Act -> Learn loop.
Implements proper iterative approach for complex multi-step tasks.
"""
import json
import platform
import time
from terminal_interface import TerminalInterface
from llm_integration import LLMIntegration
from tools import ToolExecutionSystem
from memory_manager import MemoryManager


class Agent:
    """Core AI coding agent with proper iterative Perceive -> Reason -> Act -> Learn loop."""

    def __init__(self, llm_integration, tool_execution_system, terminal_interface, project_root=None):
        """Initializes the Agent with LLM integration, tool system, terminal interface, and memory manager."""
        self.llm_integration = llm_integration
        self.tool_execution_system = tool_execution_system
        self.terminal_interface = terminal_interface
        # Use memory manager from tool execution system if available, otherwise create new one
        self.memory_manager = getattr(tool_execution_system, 'memory_manager', None)
        if not self.memory_manager:
            self.memory_manager = MemoryManager(project_root)
        self.conversation_history = []
        self.current_task_state = "idle"  # Track current task state
        self.max_iterations = 10  # Prevent infinite loops

    def perceive(self, user_input, tool_output=None):
        """Gathers current state and adds input to conversation history."""
        if user_input:
            self.conversation_history.append({"role": "user", "content": user_input})
        
        if tool_output:
            self.conversation_history.append({"role": "tool_output", "content": json.dumps(tool_output)})
        
        # Sync memory and get current context
        self.memory_manager.sync_memory()
        current_context = self.memory_manager.get_current_context()
        
        os_info = platform.system()
        return {
            "user_input": user_input,
            "tool_output": tool_output,
            "current_context": current_context, 
            "os_info": os_info
        }

    def reason(self, perception, is_continuation=False):
        """Uses LLM to analyze situation and generate next action plan."""
        memory_context = perception.get("current_context", {})
        
        if is_continuation and perception.get("tool_output"):
            # This is a continuation after tool execution - analyze output and determine next step
            response_message = self.llm_integration.analyze_and_respond(
                perception["tool_output"],
                self.conversation_history, 
                self.tool_execution_system.tool_schemas,
                memory_context
            )
        else:
            # This is initial reasoning for a new request
            response_message = self.llm_integration.generate_plan(
                self.conversation_history, 
                self.tool_execution_system.tool_schemas,
                memory_context
            )
        
        return response_message

    def act(self, action):
        """Executes tools safely with user oversight or displays textual response."""
        tool_calls = []
        processed_action = action.strip()
        
        # Clean JSON formatting - handle both ```json and ``` formats
        if processed_action.startswith('```json'):
            processed_action = processed_action[len('```json'):].strip()
            if processed_action.endswith('```'):
                processed_action = processed_action[:-len('```')].strip()
        elif processed_action.startswith('```'):
            processed_action = processed_action[len('```'):].strip()
            if processed_action.endswith('```'):
                processed_action = processed_action[:-len('```')].strip()

        try:
            response_json = json.loads(processed_action)
            
            if "tool_calls" in response_json and response_json["tool_calls"]:
                tool_calls = response_json["tool_calls"]
            elif "text" in response_json:
                agent_response_content = response_json['text']
                self.terminal_interface.display_message(agent_response_content)
                self.conversation_history.append({"role": "model", "content": agent_response_content})
                return {"status": "success", "message": agent_response_content, "type": "text_response"}
            else:
                # Handle case where JSON is valid but doesn't have expected structure
                self.terminal_interface.display_message(processed_action)
                self.conversation_history.append({"role": "model", "content": processed_action})
                return {"status": "success", "message": processed_action, "type": "text_response"}

        except json.JSONDecodeError:
            # Treat as text response
            self.terminal_interface.display_message(processed_action)
            self.conversation_history.append({"role": "model", "content": processed_action})
            return {"status": "success", "message": processed_action, "type": "text_response"}

        if tool_calls:
            # Execute only the first tool call (iterative approach)
            tool_call = tool_calls[0]
            
            function_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            
            # Handle approval for destructive actions
            if function_name in ["write_file", "delete_file", "clear_file_content", "apply_code_change", "edit_file", "edit_notebook", "run_terminal_cmd"]:
                action_description = f"The agent wants to execute '{function_name}' on '{tool_args.get('filepath', '') or tool_args.get('target_file', '')}'. Args: {tool_args}"
                preview_content = None
                language = None

                if function_name == "write_file":
                    preview_content = tool_args.get('content', '')
                    language = "text"
                elif function_name == "edit_file":
                    preview_content = f"--- Instructions ---\n{tool_args.get('instructions', '')}\n--- Code Edit ---\n{tool_args.get('code_edit', '')}"
                    language = "diff"
                elif function_name == "edit_notebook":
                    preview_content = f"--- Old String ---\n{tool_args.get('old_string', '')}\n--- New String ---\n{tool_args.get('new_string', '')}"
                    language = tool_args.get('cell_language', 'text')
                elif function_name == "run_terminal_cmd":
                    preview_content = tool_args.get('command', '')
                    language = "bash"

                if not self.terminal_interface.confirm_action(action_description, preview_content, language):
                    self.terminal_interface.display_message("Action cancelled by user.", style="red")
                    self.conversation_history.append({"role": "user_action", "content": "User denied the action."})
                    return {"status": "cancelled", "message": "Action cancelled by user.", "type": "cancelled"}
            else: # For non-destructive tools, display the tool call
                self.terminal_interface.display_tool_call(tool_call)
                self.conversation_history.append({"role": "model", "content": f"TOOL_CALL: {json.dumps(tool_call)}"})
            
            # Execute the tool
            if function_name in self.tool_execution_system.available_tools:
                start_time = time.time()
                
                tool_output = self.tool_execution_system.execute_tool_from_dict(
                    {"function": {"name": function_name, "arguments": tool_args}}
                )
                
                execution_time = time.time() - start_time
                tool_output["execution_time"] = execution_time
                tool_output["tool_name"] = function_name
                tool_output["type"] = "tool_execution"
                
                success = tool_output.get("status") == "success"
                error_message = tool_output.get("message") if not success else None
                
                # Record tool usage in memory
                self.memory_manager.record_tool_usage(
                    function_name, success, execution_time, error_message,
                    context={"arguments": tool_args}
                )
                
                # Record file operations in memory
                if function_name in ["read_file", "write_file", "delete_file", "clear_file_content", "apply_code_change"]:
                    filepath = tool_args.get("filepath")
                    if filepath:
                        self.memory_manager.record_file_operation(
                            filepath, function_name, success, error_message=error_message
                        )
                
                # Cache file content for read operations
                if function_name == "read_file" and tool_output.get("status") == "success":
                    filepath = tool_args.get("filepath")
                    content = tool_output.get("content", "")
                    if filepath and content:
                        self.memory_manager.cache_file_content(filepath, content, "read")
                
                self.terminal_interface.display_tool_output(tool_output)
                return tool_output
            else:
                error_message = f"Tool {function_name} not found."
                self.terminal_interface.display_message(error_message, style="red")
                return {"status": "error", "message": error_message, "type": "tool_error"}
        
        return {"status": "error", "message": "No tool calls detected or text response from LLM.", "type": "parse_error"}

    def learn(self, observation):
        """Updates memory and context for future decisions."""
        if isinstance(observation, dict) and observation.get("type") == "tool_execution":
            tool_name = observation.get("tool_name", "unknown")
            success = observation.get("status") == "success"
            execution_time = observation.get("execution_time")
            error_message = observation.get("message") if not success else None
            
            self.memory_manager.record_tool_usage(
                tool_name, success, execution_time, error_message
            )
        
        # Trigger learning from session periodically
        if len(self.conversation_history) % 10 == 0:
            self.memory_manager.learn_from_session()

    def run(self, user_input):
        """
        Main execution loop implementing proper iterative approach.
        Handles multi-step tasks by breaking them down into individual actions.
        """
        iteration_count = 0
        self.current_task_state = "active"
        
        # Initial perception and reasoning
        perception = self.perceive(user_input)
        
        while iteration_count < self.max_iterations and self.current_task_state == "active":
            iteration_count += 1
            
            # Reason about next action
            is_continuation = iteration_count > 1
            action = self.reason(perception, is_continuation)
            
            # Act on the reasoning
            observation = self.act(action)
            
            # Learn from the observation
            if observation and observation.get("type") == "tool_execution":
                self.learn(observation)

            # Check if task is complete
            if observation and observation.get("type") == "text_response":
                # Agent provided final response - task is complete
                self.current_task_state = "idle"
                return observation
            
            elif observation and observation.get("status") == "cancelled":
                # User cancelled action - task is aborted
                self.current_task_state = "idle"
                return observation
            
            elif observation and observation.get("status") == "error":
                # Continue iteration to let LLM handle the error
                perception = self.perceive(None, observation)
                continue
            
            elif observation and observation.get("status") == "success":
                # Successful tool execution - continue iterating for next step
                perception = self.perceive(None, observation)
                
                # Special handling for test results
                if "pytest" in observation.get("content", "") and "failed" in observation.get("content", ""):
                    self.terminal_interface.display_message("Tests failed. Agent will attempt to analyze and fix.", style="yellow")
                elif "pytest" in observation.get("content", "") and "passed" in observation.get("content", ""):
                    self.terminal_interface.display_message("Tests passed successfully!", style="green")
                
                continue
            
            else:
                # Unexpected observation type - let LLM handle it
                perception = self.perceive(None, observation)
                continue
        
        # If we exit the loop due to max iterations
        if iteration_count >= self.max_iterations:
            self.terminal_interface.display_message(
                f"Maximum iterations ({self.max_iterations}) reached. Task may be incomplete.", 
                style="red"
            )
            self.current_task_state = "idle"
            return {"status": "error", "message": "Maximum iterations reached"}
        
        self.current_task_state = "idle"
        return {"status": "success", "message": "Task completed"}
    
    def get_conversation_history(self):
        """Returns the full conversation history."""
        return self.conversation_history
    
    def get_tool_schemas(self):
        """Returns the list of available tool schemas."""
        return self.tool_execution_system.tool_schemas

    def get_status(self):
        """Get current agent status and statistics."""
        return {
            "task_state": self.current_task_state,
            "conversation_length": len(self.conversation_history),
            "memory_summary": self.memory_manager.get_memory_summary() if self.memory_manager else None
        }
