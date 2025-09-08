from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.columns import Columns
from rich.rule import Rule
import json

class TerminalInterface:
    def __init__(self):
        self.console = Console()

    def display_message(self, message, style="green", title=None):
        if "```" in message:
            parts = message.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    code_lines = part.split('\n')
                    lang = 'text'
                    if code_lines and code_lines[0].strip() in ['python', 'json', 'bash', 'diff']:
                        lang = code_lines[0].strip()
                        code = '\n'.join(code_lines[1:]).strip()
                    else:
                        code = part.strip()
                    
                    syntax = Syntax(code, lang, theme="monokai", line_numbers=False)
                    self.console.print(Panel(syntax, title=title if title else "Code"))
                else:
                    if part.strip():
                        self.console.print(Panel(Markdown(part.strip()), title=title))
        else:
            self.console.print(Panel(Markdown(message), title=title))

    def get_user_input(self, prompt="You: "):
        return self.console.input(f"[bold blue]{prompt}[/bold blue]")

    def display_agent_thought(self, thought):
        self.console.print(Text(f"[italic grey]Agent thinking: {thought}[/italic grey]"))

    def display_tool_call(self, tool_call_json):
        tool_name = tool_call_json.get('function', {}).get('name', 'unknown_tool')
        tool_args = tool_call_json.get('function', {}).get('arguments', {})
        
        tool_text = Text()
        tool_text.append(f"Agent Calling Tool: ", style="bold magenta")
        tool_text.append(f"{tool_name}\n", style="magenta")
        
        if tool_args:
            tool_text.append("Arguments:\n", style="bold magenta")
            tool_text.append(json.dumps(tool_args, indent=2), style="dim magenta")
        
        self.console.print(Panel(tool_text, title="Agent Action"))

    def display_tool_output(self, output):
        tool_name = output.get('tool_name', 'unknown_tool')
        if isinstance(output, dict) and output.get("status") == "success":
            content_to_display = output.get('content', '')
            if content_to_display:
                self.console.print(Panel(Text(f"Tool Execution Successful! [{tool_name}]\nContent:\n{content_to_display}", style="green"), title="Tool Output"))
            else:
                self.console.print(Panel(Text(f"Tool Execution Successful! [{tool_name}]", style="green"), title="Tool Output"))
        elif isinstance(output, dict) and output.get("status") == "error":
            self.console.print(Panel(Text(f"Error in [{tool_name}]: {output['message']}", style="bold red"), title="Tool Output"))
        else:
            self.console.print(Panel(Text(f"Tool Output [{tool_name}]: {output}", style="cyan"), title="Tool Output"))

    def confirm_action(self, action_description, preview_content=None, language=None):
        
        if preview_content:
            self.console.print(Panel(Text("Preview of change:", style="italic blue"), title="Preview"))
            if language:
                syntax = Syntax(preview_content, language, theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title="Code Preview"))
            else:
                self.console.print(Panel(Text(preview_content), title="Content Preview"))
        
        response = self.console.input("[bold magenta]Do you approve this action? (yes/no)[/bold magenta] ").lower().strip()
        return response == 'yes'
    
    def display_status(self, status_data):
        """Displays the agent's status in a readable, formatted manner."""
        status_text = f"""
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

- **Project Patterns:** {status_data['memory_summary']['persistent']['project_patterns'].get('total_patterns', 'N/A')} patterns ({', '.join(status_data['memory_summary']['persistent']['project_patterns'].get('pattern_types', []))})
- **User Preferences:** {status_data['memory_summary']['persistent']['user_preferences'].get('total_preferences', 'N/A')} preferences ({', '.join(status_data['memory_summary']['persistent']['user_preferences'].get('preference_types', []))})
- **Success Patterns:** {status_data['memory_summary']['persistent']['success_patterns'].get('total_patterns', 'N/A')} patterns ({', '.join(status_data['memory_summary']['persistent']['success_patterns'].get('pattern_types', []))})
- **Tool Effectiveness:** {status_data['memory_summary']['persistent']['tool_effectiveness'].get('total_tools', 'N/A')} tools ({', '.join(status_data['memory_summary']['persistent']['tool_effectiveness'].get('tools', []))})
- **File Access History:** {status_data['memory_summary']['persistent']['file_access_history'].get('total_files', 'N/A')} files accessed ({status_data['memory_summary']['persistent']['file_access_history'].get('total_accesses', 'N/A')} total accesses)
- **Code Snippets:** {status_data['memory_summary']['persistent']['code_snippets'].get('total_snippets', 'N/A')} snippets

---

## Session Details

- **Session ID:** {status_data['memory_summary'].get('session_id', 'N/A')}
"""
        
        self.console.print(Panel(Markdown(status_text), title="Agent Status"))
        
    def display_history(self, history):
        """Displays the conversation history in a readable, formatted manner with clear visual separation."""
        if not history:
            self.console.print(Panel(Text("No conversation history available.", style="italic"), title="Conversation History"))
            return
            
        self.console.print("\n")
        self.console.print(Rule(title="[bold blue]CONVERSATION HISTORY[/bold blue]", style="blue"))
        
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
                    tool_call_data = json.loads(content.replace("TOOL_CALL: ", ""))
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
        self.console.print(f"[dim]Total exchanges: {exchange_number}[/dim]")

    def _display_exchange(self, number, exchange):
        """Display a single conversation exchange with proper formatting."""
        self.console.print(f"\n[bold cyan]Exchange {number}[/bold cyan]")
        self.console.print("─" * 60)
        
        # User input
        if 'user' in exchange:
            user_panel = Panel(
                Text(exchange['user'], style="white"),
                title="👤 You",
                title_align="left",
                border_style="blue",
                padding=(0, 1)
            )
            self.console.print(user_panel)
        
        # Tool calls and outputs
        if 'tool_calls' in exchange:
            for i, tool_call in enumerate(exchange['tool_calls']):
                tool_name = tool_call.get('function', {}).get('name', 'unknown')
                tool_args = tool_call.get('function', {}).get('arguments', {})
                
                # Format tool call display
                tool_text = Text()
                tool_text.append(f"🔧 Function: ", style="bold magenta")
                tool_text.append(f"{tool_name}\n", style="magenta")
                
                if tool_args:
                    tool_text.append("📋 Arguments:\n", style="bold magenta")
                    tool_text.append(json.dumps(tool_args, indent=2), style="dim magenta")
                
                tool_panel = Panel(
                    tool_text,
                    title="🤖 Tool Call",
                    title_align="left", 
                    border_style="magenta",
                    padding=(0, 1)
                )
                self.console.print(tool_panel)
                
                # Corresponding tool output
                if 'tool_outputs' in exchange and i < len(exchange['tool_outputs']):
                    output = exchange['tool_outputs'][i]
                    
                    output_text = Text()
                    status = output.get('status', 'unknown')
                    
                    if status == 'success':
                        output_text.append("✅ SUCCESS\n", style="bold green")
                    elif status == 'error':
                        output_text.append("❌ ERROR\n", style="bold red")
                        output_text.append(f"Message: {output.get('message', 'N/A')}\n", style="red")
                    
                    if output.get('content'):
                        content = str(output['content'])
                        # Truncate very long content
                        if len(content) > 500:
                            content = content[:500] + "\n... [content truncated]"
                        output_text.append(f"📄 Content:\n{content}", style="cyan")
                    
                    output_panel = Panel(
                        output_text,
                        title="⚙️ Tool Output",
                        title_align="left",
                        border_style="cyan" if status == 'success' else "red",
                        padding=(0, 1)
                    )
                    self.console.print(output_panel)
        
        # Agent response
        if 'agent_response' in exchange:
            # Check if response contains markdown or code
            response = exchange['agent_response']
            
            if "```" in response or response.startswith("#") or "**" in response:
                # Use markdown rendering for formatted responses
                agent_panel = Panel(
                    Markdown(response),
                    title="🤖 Agent Response",
                    title_align="left",
                    border_style="green",
                    padding=(0, 1)
                )
            else:
                # Use plain text for simple responses
                agent_panel = Panel(
                    Text(response, style="white"),
                    title="🤖 Agent Response", 
                    title_align="left",
                    border_style="green",
                    padding=(0, 1)
                )
            self.console.print(agent_panel)
        
        # User action (if any)
        if 'user_action' in exchange:
            action_panel = Panel(
                Text(exchange['user_action'], style="yellow"),
                title="👤 User Action",
                title_align="left", 
                border_style="yellow",
                padding=(0, 1)
            )
            self.console.print(action_panel)
            
        self.console.print()  # Add spacing between exchanges