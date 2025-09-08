import google.generativeai as genai
import json

class LLMIntegration:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate_response_feedback(self, user_request, agent_response, tool_output=None):
        """Generate feedback on the agent's response quality and effectiveness."""
        feedback_prompt = f"""
        You are evaluating an AI coding agent's response to assess its quality and effectiveness.
        
        **USER REQUEST:** {user_request}
        
        **AGENT RESPONSE:** {agent_response}
        
        **TOOL OUTPUT (if any):** {json.dumps(tool_output) if tool_output else "No tool execution"}
        
        Provide constructive feedback on the agent's response considering:
        1. **Accuracy**: Was the response factually correct and relevant?
        2. **Completeness**: Did it fully address the user's request?
        3. **Clarity**: Was the explanation clear and well-structured?
        4. **Usefulness**: How helpful was the response for the user?
        5. **Efficiency**: Was the approach taken optimal?
        
        Provide a brief evaluation (2-3 sentences) highlighting strengths and areas for improvement.
        Rate the response: Excellent/Good/Fair/Poor
        
        Format: "**Agent Feedback:** [Your evaluation] **Rating:** [Rating]"
        """
        
        try:
            feedback_response = self.model.generate_content(feedback_prompt)
            return feedback_response.text.strip()
        except Exception as e:
            return f"**Agent Feedback:** Unable to generate feedback due to error: {str(e)} **Rating:** N/A"

    def generate_plan(self, conversation_history, available_tools_schema, memory_context=None):
        tools_str = json.dumps(available_tools_schema)

        # Extract OS info from the last message in conversation_history if available
        os_info = "Unknown"
        if conversation_history and isinstance(conversation_history[-1], dict) and "os_info" in conversation_history[-1]:
            os_info = conversation_history[-1]["os_info"]

        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        
        # Add memory context to the prompt
        memory_context_text = ""
        if memory_context:
            memory_context_text = f"""
        Memory Context:
        - Frequently accessed files: {memory_context.get('frequently_accessed_files', [])}
        - Active files in session: {memory_context.get('active_files', [])}
        - Recent operations: {len(memory_context.get('recent_operations', []))} operations
        - Tool effectiveness: {list(memory_context.get('tool_effectiveness', {}).keys())}
        - User preferences: {list(memory_context.get('user_preferences', {}).keys())}
        """

        prompt = """
		You are an intelligent coding agent following a Perceive -> Reason -> Act -> Learn iterative loop. Your goal is to understand the user's request and determine the *single next action* to take.

		IMPORTANT: You must respond with EXACTLY ONE action at a time. After each action is executed, you will receive feedback and determine the next step.

		**ITERATIVE APPROACH RULES:**
		1. Break complex tasks into individual steps
		2. Execute ONE tool call at a time
		3. Wait for tool execution result before planning next step
		4. Adapt based on previous results and feedback
		5. Provide clear reasoning for each step

		**RESPONSE FORMATS:**
		For tool calls, respond with JSON:
		```json
		{"tool_calls": [{"function": {"name": "tool_name", "arguments": {"key": "value"}}}]}
		```
		Make sure to format the JSON with an indent of 2. All responses must be a single, complete JSON object. If a text response contains code, embed it within a markdown code block.

		For text responses/summaries, respond with JSON:
		{"text": "Your response here"}

		IMPORTANT INTENT RULES:
		- If the user asks to "give/provide/show code" (without saying write/create/save a file), respond with {"text": "..."} and include the code in a markdown code block. Do NOT call any tools.
		- Only use write_file when the user explicitly says to write/create/save/add a file. If the filename is missing, ask for it first instead of guessing.
		- If the user asks to write and also provides a filename, include the full code content in the write_file call.

		For multi-step requests like "read file1.py and file2.py":
		- Step 1: Read file1.py (wait for result)
		- Step 2: Read file2.py (after receiving file1 content)
		- Step 3: Provide analysis/summary of both files

		For Git-related operations, use the `run_git_command` tool with the full Git subcommand (e.g., "status", "diff", "commit -m 'message'").

		For directory listings, use `list_directory_contents` instead of `run_command` with `ls`.

		For file searches, use `search_files` with query, optional filepath, or directory_path.

		For Python linting, use `run_linter` with optional filepath or directory_path. Use this primarily when explicitly asked to "run linter" or if a deeper, formal code analysis is needed.

		For running tests, use `run_tests` with optional directory_path.

		For code fixes and modifications, ALWAYS use `edit_file` with `target_file`, `instructions`, and `code_edit`.
		The `code_edit` argument MUST be a plain string that precisely represents the changes using `// ... existing code ...` markers. It must NOT be a diff format, a code block, or include any surrounding markdown. This is a critical requirement for the tool to function correctly. Examples of incorrect `code_edit` formats include: ````python...````, `--- a/file`, `+++ b/file`, `@@ -x,y +a,b @@`.
		If `edit_file` is NOT present in the Available tools list, then use `write_file` to overwrite the entire file with the fully corrected content instead. In that case, the `content` should contain the complete, final file text.
		For example:
		```python
		# ... existing code ...
		def new_function():
			pass
		# ... existing code ...
		class MyClass:
			# ... existing code ...
			def new_method(self):
				pass
			# ... existing code ...
		```

		For creating new files or completely overwriting existing ones, use `write_file`. NEVER use `write_file` for partial code modifications; always use `edit_file` for that.

		For undoing actions, explicitly use the `undo_last_action` tool. If a user asks to undo, the next step should always be to call `undo_last_action`.

		**SAFETY:** Destructive operations (write_file, delete_file, clear_file_content, edit_file, edit_notebook, run_terminal_cmd) require user confirmation.
		""" + "\n\nCurrent Operating System: " + os_info + (memory_context_text or "") + "\n\n" + \
		"Conversation history:\n" + history_text + "\n\n" + \
		"Available tools: " + tools_str + "\n\n" + \
		"""
		**TASK:** Based on the conversation history, what is the SINGLE next action to take?
		1. If the user's request is a general knowledge question about a specific file (e.g., "what is package.json", "what is requirements.txt"), first list directory contents to show available files, then provide a comprehensive explanation.
		2. If the user's request is general knowledge without file context (e.g., "what is Python", "explain OOP"), provide a comprehensive text response directly.
		3. Always use `list_directory_contents` first when users asks about specific file types to show what files are actually available.
		4. If you just received tool output and the task is complete, provide a final summary.
		
		**ERROR HANDLING:** If a tool execution resulted in an error, analyze the error message and suggest a concrete next step to resolve it. Use tools like `list_directory_contents` to verify paths or `search_files` to locate files. If a tool execution resulted in a "tool not found" error, or an `edit_file` call failed, analyze the error. Specifically for `edit_file`, you *must* check if the `code_edit` argument was malformed (e.g., sent as a diff or markdown code block instead of a plain string with `// ... existing code ...` markers). If it was, clearly diagnose the formatting issue to the user (e.g., "The `edit_file` tool call failed because the `code_edit` argument was not a plain string. Please ensure it follows the specified format: no diffs, no markdown code blocks in the `code_edit` string itself.") and **do not retry the edit in the same turn or propose any other correction**. Halt and wait for user instruction. If it's a different tool, list available tools or suggest searching for the tool.

		Respond with either a single tool call JSON or a text response JSON as specified above.
		"""

        response = self.model.generate_content(prompt)
        return response.text

    def analyze_and_respond(self, tool_output, conversation_history, available_tools_schema, memory_context=None):
        """
        Analyze tool output and determine next action or provide final response.
        This supports the iterative approach by processing each step's result.
        """
        tools_str = json.dumps(available_tools_schema)
        
        # Determine available tool names to guide behavior (avoid loops when edit_file isn't available)
        available_tool_names = []
        try:
            if isinstance(available_tools_schema, list):
                for t in available_tools_schema:
                    if isinstance(t, dict):
                        name = t.get('name') or (t.get('function', {}) if isinstance(t.get('function', {}), dict) else {}).get('name')
                        if name:
                            available_tool_names.append(name)
        except Exception:
            available_tool_names = []
        has_edit_file = 'edit_file' in available_tool_names
        has_write_file = 'write_file' in available_tool_names
        
        # Get the last user request from conversation history
        last_user_message = ""
        for msg in reversed(conversation_history):
            if msg['role'] == 'user':
                last_user_message = msg['content']
                break
        
        # Add memory context to the prompt
        memory_context_text = ""
        if memory_context:
            memory_context_text = f"""
        Memory Context:
        - Frequently accessed files: {memory_context.get('frequently_accessed_files', [])}
        - Active files in session: {memory_context.get('active_files', [])}
        - Recent operations: {len(memory_context.get('recent_operations', []))} operations
        """
        
        # Enhanced handling - proactive approach for "what is" questions
        # Since we're now using list_directory_contents first, we don't need special file not found handling

        # Handle successful directory listing for "what is" questions
        if (tool_output.get('status') == 'success' and 
            tool_output.get('tool_name') == 'list_directory_contents' and
            any(phrase in last_user_message.lower() for phrase in ["what is", "what's", "explain"])):
            
            # Get the file type from the original user question
            file_type_mentioned = "unknown file"
            user_question_words = last_user_message.lower().split()
            for i, word in enumerate(user_question_words):
                if word in ["what", "what's"] and i + 1 < len(user_question_words) and user_question_words[i + 1] == "is":
                    if i + 2 < len(user_question_words):
                        file_type_mentioned = user_question_words[i + 2]
                        break
            
            directory_contents = tool_output.get('content', 'No files found')
            
            # Generate detailed explanation using LLM
            explanation_prompt = f"""
            A user asked "what is {file_type_mentioned}" and we've listed the current directory contents.
            
            Current directory contents:
            {directory_contents}
            
            The file "{file_type_mentioned}" is not present in this directory. Provide a comprehensive explanation that includes:
            1. A clear statement that the file was not found in the current directory
            2. Show the current directory contents in a readable format
            3. What the file type "{file_type_mentioned}" is and its typical purpose
            4. Why it might not be present in this project (analyze the directory contents to understand the project type)
            5. A realistic example of what this file typically looks like with proper code formatting
            6. Related alternatives that might be used instead based on the project type
            
            Format your response with proper markdown including code blocks where appropriate.
            Make it detailed and educational - much more than a brief explanation.
            Be specific about why this file type might not be relevant to the current project based on the visible files.
            """
            
            explanation_response = self.model.generate_content(explanation_prompt)
            
            final_response = f"""{explanation_response.text}"""
            
            return json.dumps({"text": final_response})

        # Priority 1: Handle successful write_file operations immediately if the intent was just to write.
        if tool_output.get('status') == 'success' and tool_output.get('tool_name') == 'write_file':
            if any(phrase in last_user_message.lower() for phrase in ["write code", "create a file", "make a file", "put this code"]):
                return json.dumps({"text": f"Successfully wrote content to {tool_output.get('filepath', 'the file')}. I'm ready for your next instruction."})
            # Also stop after a correction flow that used write_file
            if any(phrase in last_user_message.lower() for phrase in ["check", "correct", "fix"]):
                return json.dumps({"text": f"Updated {tool_output.get('filepath', 'the file')} with corrected content."})

        # Enhanced error handling based on tool output
        if tool_output.get('status') == 'error':
            error_message = tool_output.get('message', '').lower()
            tool_name = tool_output.get('tool_name', '')

            # Handle missing tools explicitly to avoid loops
            if "tool" in error_message and "not found" in error_message:
                missing = error_message.split("tool")[-1].strip()
                if "edit_file" in error_message and has_write_file:
                    return json.dumps({"text": "The 'edit_file' tool is not available. I can fall back to overwriting the full file using 'write_file' if you confirm. Please say 'yes' to proceed or 'no' to cancel."})
                return json.dumps({"text": f"A required tool is not available ({missing}). Please enable it or let me know if I should try an alternative approach."})

            if "file not found" in error_message or "no such file" in error_message:
                return json.dumps({"text": f"Error: The specified file was not found. Please ensure the file path and name are correct."})
            elif "command not found" in error_message or "not installed" in error_message:
                missing_command = error_message.split(':')[-1].strip().split('.')[0].replace("'", "")
                return json.dumps({"text": f"It seems the command '{missing_command}' is not found or not installed. Please install it or verify its presence in your PATH. If you would like me to try and find installation instructions, please let me know."})
            elif "permission denied" in error_message:
                return json.dumps({"text": "Permission denied. I cannot perform this action. Please ensure I have the necessary permissions."})
            elif "git command failed" in error_message:
                return json.dumps({"text": f"Git command failed with error: {error_message}. Please review the command and ensure your Git repository is in a valid state."})
            elif "no lines found matching" in error_message and tool_name == "search_files":
                return json.dumps({"text": f"No results found for your search query. Perhaps try a different query or specify a different file/directory."})
            elif tool_name == "run_linter" and tool_output.get("content"): # Linter ran and returned output
                linter_output = tool_output["content"]
                # Prompt the LLM to analyze linter output and suggest a fix
                analysis_prompt = f"""
                The user reported an error in their code or asked for code to be checked. I ran a linter and got the following output:
                
                Linter Output:
                """ + linter_output + """
                
                Original User Request: """ + last_user_message + """

                Analyze this linter output. If there are clear errors, point them out and suggest a precise fix using the `edit_file` tool.
                For `edit_file`, provide the `target_file`, an `instructions` string, and a `code_edit` string.
                The `code_edit` should be a plain string that uses `// ... existing code ...` to represent unchanged lines, and clearly shows new/changed lines. It should NOT be a diff format or a markdown code block. This is a critical requirement for the tool to function correctly. Examples of incorrect `code_edit` formats include: ````python...````, `--- a/file`, `+++ b/file`, `@@ -x,y +a,b @@`.
                Example:
                ```python
                # ... existing code ...
                def my_new_function():
                    pass
                # ... existing code ...
                class MyClass:
                    # ... existing code ...
                    def another_method(self):
                        print("Hello")
                    # ... existing code ...
                ```
                If the errors are ambiguous or multiple files are involved, ask clarifying questions or suggest a plan to debug.
                If there are no errors or only warnings, inform the user.

                Your response should be a SINGLE, complete JSON object. It can be either:
                ```json
                {"tool_calls": [{"function": {"name": "edit_file", "arguments": {"target_file": "path/to/file.py", "instructions": "I am fixing the code", "code_edit": "// ... existing code ...\nnew_line_of_code\n// ... existing code ..."}}}]}
                ```
                or
                ```json
                {"text": "Your explanation or question here, possibly including a markdown code block for revised code if not using edit_file."}
                ```
                Make sure to format the JSON with an indent of 2.
                """
                analysis_response = self.model.generate_content(analysis_prompt)
                return analysis_response.text
            elif tool_name == "edit_file" and ("tool edit_file not found" in error_message or "malformed arguments" in error_message or "invalid code_edit format" in error_message):
                return json.dumps({"text": "The `edit_file` tool call failed. This is likely due to the `code_edit` argument being incorrectly formatted (e.g., using diff syntax or markdown code blocks instead of a plain string with `// ... existing code ...` markers). Please ensure it follows the specified format: no diffs, no markdown code blocks in the `code_edit` string itself. I will not retry the edit in this turn. Please correct the prompt if you'd like me to try again."})
            # Add more specific error handling as needed
        elif tool_output.get('status') == 'success' and tool_output.get('tool_name') == 'read_file' and any(phrase in last_user_message.lower() for phrase in ["check", "correct", "fix"]):
            file_content = tool_output.get('content', '')
            filepath = tool_output.get('filepath', 'the file')
            if not file_content:
                return json.dumps({"text": f"The file {filepath} is empty, or no content was read. There's nothing to check or correct."})
            
            # If edit_file is not available, fallback to write_file with full corrected content to avoid loops
            if not has_edit_file and has_write_file:
                fallback_prompt = f"""
                The user asked to check and correct the code below. Since partial edits are not available, produce the FULL corrected file content only.

                Return JSON with a single tool call using write_file to this exact path:
                "{filepath}"

                The JSON MUST be exactly:
                {{
                  "tool_calls": [
                    {{
                      "function": {{
                        "name": "write_file",
                        "arguments": {{
                          "filepath": "{filepath}",
                          "content": "<FULL_CORRECTED_FILE_CONTENT>"
                        }}
                      }}
                    }}
                  ]
                }}

                Rules for content:
                - Provide the complete, final file as a plain string (no markdown fences, no diff syntax, no backticks).
                - Preserve Python formatting and newlines.

                Original file content:
                """ + file_content
                fb = self.model.generate_content(fallback_prompt)
                return fb.text
            
            # Prompt the LLM to analyze the read file content and suggest a fix if needed
            analysis_prompt = f"""
            The user asked to check and correct the code in {filepath}. I have read the file, and its content is as follows:
            
            File Content:
            """ + file_content + """
            
            Original User Request: """ + last_user_message + """

            Analyze this code. If there are clear logical, stylistic, or syntax errors, point them out and suggest a precise fix using the `edit_file` tool.
            For `edit_file`, provide the `target_file` (which is {filepath}), an `instructions` string, and a `code_edit` string.
            The `code_edit` argument MUST be a plain string that precisely represents the changes using `// ... existing code ...` markers. It must NOT be a diff format, a code block, or include any surrounding markdown. This is a critical requirement for the tool to function correctly. Examples of incorrect `code_edit` formats include: ````python...````, `--- a/file`, `+++ b/file`, `@@ -x,y +a,b @@`.
            If no changes are required, respond with a text JSON indicating no issues.

            Your response should be a SINGLE, complete JSON object.
            """
            analysis_response = self.model.generate_content(analysis_prompt)
            return analysis_response.text

        # Use string concatenation instead of f-string for complex formatting
        prompt = """
        You are continuing your iterative approach to completing the user's request.

        INTENT HANDLING:
        - If the user's latest request asks to "give/provide/show code" (and does not ask to write/create/save/add a file), then respond with a TEXT JSON only and include the code inside a markdown code block. Do NOT propose any tool calls.
        - Only propose a write_file tool call when the user's latest request explicitly asks to write/create/save/add a file. If a filename is not provided, ask for it instead of guessing.

        When the user asks to "check the code" or "correct the code" in a file, and you have just read the file (successful `read_file` tool output), you should directly analyze the content of the `read_file` output.
        If you identify any errors (logical, stylistic, or syntax) and the solution is clear, immediately propose a fix using the `edit_file` tool. Do not simply describe the problem or ask for more information.
        Ensure the `edit_file` call includes a clear `instructions` string and a `code_edit` string that is a plain string precisely representing the changes using `// ... existing code ...` markers. It should NOT be a diff format.

        If the code is already correct and requires no changes based on the user's request (e.g., no errors or logical flaws), provide a text response informing the user that the code is correct and no action is needed. Do not propose an `edit_file` action if the code is already correct.

        When the user asks to *write* code to a file (e.g., "write code to X", "create file Y"), perform the `write_file` operation. After a successful `write_file` operation, you should provide a confirmation message to the user and *wait for further instructions*. Do not automatically proceed to analyze or correct the newly written code unless explicitly asked to "check" or "correct" it in a *separate* subsequent request.

        **ORIGINAL USER REQUEST:** """ + last_user_message + """

        **LATEST TOOL OUTPUT:** """ + json.dumps(tool_output) + """

        **CONVERSATION HISTORY:**
        """ + "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]]) + """

        """ + memory_context_text + """

        **ANALYSIS REQUIRED:**
        1. Was the tool execution successful?
        2. Does this complete the user's request, or are more steps needed?
        3. If more steps needed, what is the NEXT logical action?
        4. If complete, provide a comprehensive summary/analysis.

        **RESPONSE FORMATS:**
        - For next tool action: {"tool_calls": [{"function": {"name": "tool_name", "arguments": {"key": "value"}}}]}
        - For final response: {"text": "Your comprehensive response here"}

        **SPECIAL CASES:**
        - If reading multiple files: Summarize each file's content and purpose
        - If tests failed: Analyze failure and suggest specific fixes
        - If errors occurred: Explain the error and suggest resolution steps
        - If the previous tool call was `undo_last_action` and it was successful, the task is complete.
        - If a file search or read for a file returns no results, provide a final summary explaining what the file is and why it might not be present, then list the contents of the current directory to be helpful.
        - If you have successfully listed the directory contents in a previous step to generate a `README.md`, the next logical step is to read the contents of all the relevant project files in the directory to gather information.
        - When the user asks to search for files of a specific type (e.g., "python files", "javascript files"), use the `grep` tool with the appropriate `type` argument (e.g., `type: "py"` for Python, `type: "js"` for JavaScript).
        - If a tool execution resulted in a "tool not found" error, analyze the context. If it's `edit_file`, check if the arguments were malformed (e.g., sending a diff instead of a plain string for `code_edit`). If so, suggest the correct usage. If it's a different tool, list available tools or suggest searching for the tool.

        Available tools: """ + tools_str + """

        Determine the next action or provide final response:
        """

        response = self.model.generate_content(prompt)
        return response.text