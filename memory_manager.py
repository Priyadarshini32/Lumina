"""
Memory Manager - Unified interface for working and persistent memory
"""
import time
import hashlib
from typing import Dict, List, Any, Optional
from working_memory import WorkingMemory
from persistent_memory import PersistentMemory


class MemoryManager:
    """Unified memory management system combining working and persistent memory."""
    
    def __init__(self, project_root: str = None):
        """Initialize both working and persistent memory systems."""
        self.working_memory = WorkingMemory()
        self.persistent_memory = PersistentMemory(project_root)
        
        # Integration layer
        self.session_id = self._generate_session_id()
        self.memory_sync_interval = 60  # seconds
        self.last_sync_time = time.time()
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = str(int(time.time()))
        random_component = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"session_{timestamp}_{random_component}"
    
    # File content and access management
    def cache_file_content(self, filepath: str, content: str, operation: str = "read") -> bool:
        """Cache file content in working memory and record access in persistent memory."""
        # Cache in working memory
        content_changed = self.working_memory.cache_file_content(filepath, content)
        
        # Record access in persistent memory
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        file_size = len(content.encode('utf-8'))
        
        self.persistent_memory.record_file_access(
            filepath=filepath,
            operation=operation,
            success=True,
            content_hash=content_hash,
            file_size=file_size
        )
        
        return content_changed
    
    def get_file_content(self, filepath: str) -> Optional[str]:
        """Get file content from working memory cache."""
        return self.working_memory.get_file_content(filepath)
    
    def record_file_operation(self, filepath: str, operation: str, success: bool, 
                            details: Dict = None, error_message: str = None):
        """Record file operation in both memory systems."""
        # Record in working memory
        self.working_memory.record_file_operation(
            filepath, operation, success, details, error_message
        )
        
        # Record in persistent memory
        content_hash = None
        file_size = None
        
        if success and operation in ["read", "write"]:
            cached_content = self.working_memory.get_file_content(filepath)
            if cached_content:
                content_hash = hashlib.md5(cached_content.encode('utf-8')).hexdigest()
                file_size = len(cached_content.encode('utf-8'))
        
        self.persistent_memory.record_file_access(
            filepath=filepath,
            operation=operation,
            success=success,
            content_hash=content_hash,
            file_size=file_size
        )
    
    # Tool usage tracking
    def record_tool_usage(self, tool_name: str, success: bool, execution_time: float = None,
                         error_message: str = None, context: Dict = None):
        """Record tool usage in persistent memory."""
        self.persistent_memory.record_tool_usage(
            tool_name, success, execution_time, error_message, context
        )
    
    def record_command(self, command: str, success: bool, output: str = None, 
                      execution_time: float = None):
        """Record command execution in working memory."""
        self.working_memory.record_command(command, success, output, execution_time)
        
        # Also record as tool usage if it's a shell command
        if command.strip():
            self.persistent_memory.record_tool_usage(
                "run_command", success, execution_time, 
                error_message=None if success else output,
                context={"command": command}
            )
    
    # Pattern and preference recording
    def record_success_pattern(self, pattern_type: str, pattern_data: Dict, 
                             success_rate: float, context: Dict = None):
        """Record successful patterns in persistent memory."""
        self.persistent_memory.record_success_pattern(
            pattern_type, pattern_data, success_rate, context
        )
    
    def record_user_preference(self, preference_type: str, preference_data: Dict):
        """Record user preferences in persistent memory."""
        self.persistent_memory.record_user_preference(preference_type, preference_data)
    
    def record_project_pattern(self, pattern_type: str, pattern_data: Dict, 
                             filepath: str = None, context: Dict = None):
        """Record project patterns in persistent memory."""
        self.persistent_memory.record_project_pattern(
            pattern_type, pattern_data, filepath, context
        )
    
    def store_code_snippet(self, snippet: str, snippet_type: str, context: Dict = None,
                          tags: List[str] = None, filepath: str = None):
        """Store code snippet in persistent memory."""
        self.persistent_memory.store_code_snippet(
            snippet, snippet_type, context, tags, filepath
        )
    
    # Context and pattern retrieval
    def get_current_context(self) -> Dict:
        """Get comprehensive current context combining both memory systems."""
        working_context = self.working_memory.get_current_context()
        persistent_context = {
            "frequently_accessed_files": self.persistent_memory.get_frequently_accessed_files(5),
            "tool_effectiveness": self.persistent_memory.get_tool_effectiveness(),
            "user_preferences": self.persistent_memory.get_user_preferences(),
            "session_id": self.session_id
        }
        
        return {**working_context, **persistent_context}
    
    def get_relevant_patterns(self, context: Dict, pattern_type: str = None) -> List[Dict]:
        """Get relevant patterns from persistent memory."""
        return self.persistent_memory.get_relevant_patterns(context, pattern_type)
    
    def get_user_preferences(self, preference_type: str = None) -> Dict:
        """Get user preferences from persistent memory."""
        return self.persistent_memory.get_user_preferences(preference_type)
    
    def get_tool_effectiveness(self, tool_name: str = None) -> Dict:
        """Get tool effectiveness from persistent memory."""
        return self.persistent_memory.get_tool_effectiveness(tool_name)
    
    def get_frequently_accessed_files(self, limit: int = 10) -> List[Dict]:
        """Get frequently accessed files from persistent memory."""
        return self.persistent_memory.get_frequently_accessed_files(limit)
    
    def search_code_snippets(self, query: str = None, snippet_type: str = None, 
                           tags: List[str] = None) -> List[Dict]:
        """Search code snippets in persistent memory."""
        return self.persistent_memory.search_code_snippets(query, snippet_type, tags)
    
    # Working memory specific operations
    def get_recent_changes(self, filepath: str = None, limit: int = 10) -> List[Dict]:
        """Get recent changes from working memory."""
        return self.working_memory.get_recent_changes(filepath, limit)
    
    def get_file_change_summary(self, filepath: str) -> Dict:
        """Get file change summary from working memory."""
        return self.working_memory.get_file_change_summary(filepath)
    
    def get_session_summary(self) -> Dict:
        """Get session summary from working memory."""
        return self.working_memory.get_session_summary()
    
    def clear_file_cache(self, filepath: str = None):
        """Clear file cache in working memory."""
        self.working_memory.clear_file_cache(filepath)
    
    def refresh_file_cache(self, filepath: str) -> bool:
        """Refresh file cache in working memory."""
        return self.working_memory.refresh_file_cache(filepath)
    
    def get_files_needing_refresh(self) -> List[str]:
        """Get files needing refresh from working memory."""
        return self.working_memory.get_files_needing_refresh()
    
    # Memory synchronization and maintenance
    def sync_memory(self, force: bool = False):
        """Synchronize memory systems if needed."""
        current_time = time.time()
        
        if force or (current_time - self.last_sync_time) > self.memory_sync_interval:
            # Refresh files that need updating
            files_needing_refresh = self.working_memory.get_files_needing_refresh()
            for filepath in files_needing_refresh:
                self.working_memory.refresh_file_cache(filepath)
            
            # Clean up old persistent memory
            self.persistent_memory.cleanup_old_memory()
            
            self.last_sync_time = current_time
    
    def get_memory_summary(self) -> Dict:
        """Get comprehensive memory summary."""
        working_summary = self.working_memory.get_session_summary()
        persistent_summary = self.persistent_memory.get_memory_summary()
        
        return {
            "session": working_summary,
            "persistent": persistent_summary,
            "session_id": self.session_id,
            "last_sync": self.last_sync_time
        }
    
    # Learning and pattern extraction
    def learn_from_session(self):
        """Extract learning patterns from current session."""
        session_summary = self.working_memory.get_session_summary()
        recent_changes = self.working_memory.get_recent_changes(limit=20)
        
        # Learn file access patterns
        for filepath in session_summary["active_files"]:
            file_changes = self.working_memory.get_file_change_summary(filepath)
            if file_changes["total_changes"] > 0:
                self.persistent_memory.record_project_pattern(
                    "file_modification_pattern",
                    {
                        "file_type": self._get_file_extension(filepath),
                        "change_count": file_changes["total_changes"],
                        "change_types": file_changes["change_types"]
                    },
                    filepath=filepath,
                    context={"session_id": self.session_id}
                )
        
        # Learn command patterns
        recent_commands = list(self.working_memory.recent_commands)
        if recent_commands:
            command_patterns = {}
            for cmd_record in recent_commands:
                cmd = cmd_record["command"]
                cmd_type = self._categorize_command(cmd)
                if cmd_type not in command_patterns:
                    command_patterns[cmd_type] = {"count": 0, "success_rate": 0, "commands": []}
                
                command_patterns[cmd_type]["count"] += 1
                command_patterns[cmd_type]["commands"].append(cmd)
                if cmd_record["success"]:
                    command_patterns[cmd_type]["success_rate"] += 1
            
            # Calculate success rates
            for cmd_type, pattern in command_patterns.items():
                pattern["success_rate"] /= pattern["count"]
                
                self.persistent_memory.record_user_preference(
                    "command_patterns",
                    {
                        "command_type": cmd_type,
                        "frequency": pattern["count"],
                        "success_rate": pattern["success_rate"],
                        "example_commands": pattern["commands"][:3]  # Keep first 3 examples
                    }
                )
    
    def _get_file_extension(self, filepath: str) -> str:
        """Get file extension from filepath."""
        import os
        _, ext = os.path.splitext(filepath)
        return ext.lower() if ext else "no_extension"
    
    def _categorize_command(self, command: str) -> str:
        """Categorize command type."""
        command_lower = command.lower().strip()
        
        if command_lower.startswith("git "):
            return "git_operation"
        elif command_lower.startswith("python ") or command_lower.startswith("python3 "):
            return "python_execution"
        elif command_lower.startswith("pip "):
            return "package_management"
        elif command_lower.startswith("ls ") or command_lower.startswith("dir "):
            return "file_listing"
        elif command_lower.startswith("cd "):
            return "directory_navigation"
        elif "test" in command_lower or "pytest" in command_lower:
            return "testing"
        elif "lint" in command_lower or "pylint" in command_lower:
            return "code_analysis"
        else:
            return "general_command"
    
    # Memory export/import for session persistence
    def export_session_data(self) -> Dict:
        """Export session data for persistence."""
        return {
            "session_id": self.session_id,
            "working_memory": self.working_memory.export_session_data(),
            "last_sync_time": self.last_sync_time
        }
    
    def import_session_data(self, data: Dict):
        """Import session data from previous session."""
        if "session_id" in data:
            self.session_id = data["session_id"]
        
        if "working_memory" in data:
            self.working_memory.import_session_data(data["working_memory"])
        
        if "last_sync_time" in data:
            self.last_sync_time = data["last_sync_time"]
