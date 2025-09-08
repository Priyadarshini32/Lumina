"""
Working Memory Management System for AI Coding Agent
Handles current session state, file contents, and recent changes
"""
import os
import hashlib
import time
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict, deque
import json


class WorkingMemory:
    """Manages working memory for the current session."""
    
    def __init__(self, max_file_cache: int = 50, max_change_history: int = 100):
        """Initialize working memory with configurable limits."""
        self.max_file_cache = max_file_cache
        self.max_change_history = max_change_history
        
        # File content cache
        self.file_contents = {}  # filepath -> content
        self.file_hashes = {}    # filepath -> content hash
        self.file_sizes = {}     # filepath -> file size
        self.file_timestamps = {} # filepath -> last modified time
        
        # Recent changes tracking
        self.change_history = deque(maxlen=max_change_history)
        self.current_changes = defaultdict(list)  # filepath -> list of changes
        
        # Session state
        self.session_start_time = time.time()
        self.current_directory = os.getcwd()
        self.active_files = set()  # Currently open/accessed files
        self.recent_commands = deque(maxlen=50)
        self.error_states = defaultdict(list)  # filepath -> list of errors
        
        # Context tracking
        self.current_context = {
            "working_directory": self.current_directory,
            "active_files": [],
            "recent_operations": [],
            "error_context": {}
        }
    
    def cache_file_content(self, filepath: str, content: str, force_refresh: bool = False) -> bool:
        """Cache file content and track changes."""
        try:
            # Get current file stats
            if os.path.exists(filepath):
                stat = os.stat(filepath)
                current_size = stat.st_size
                current_mtime = stat.st_mtime
            else:
                current_size = 0
                current_mtime = 0
            
            # Calculate content hash
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            # Check if content has changed
            content_changed = (
                filepath not in self.file_hashes or
                self.file_hashes[filepath] != content_hash or
                force_refresh
            )
            
            if content_changed:
                # Store previous content for change tracking
                old_content = self.file_contents.get(filepath)
                old_hash = self.file_hashes.get(filepath)
                
                # Update cache
                self.file_contents[filepath] = content
                self.file_hashes[filepath] = content_hash
                self.file_sizes[filepath] = current_size
                self.file_timestamps[filepath] = current_mtime
                
                # Track change
                if old_content is not None:
                    change_record = {
                        "timestamp": time.time(),
                        "filepath": filepath,
                        "operation": "content_update",
                        "old_hash": old_hash,
                        "new_hash": content_hash,
                        "old_size": self.file_sizes.get(filepath, 0),
                        "new_size": current_size,
                        "change_type": self._determine_change_type(old_content, content)
                    }
                    self._record_change(change_record)
                
                # Manage cache size
                self._manage_cache_size()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error caching file content for {filepath}: {e}")
            return False
    
    def get_file_content(self, filepath: str) -> Optional[str]:
        """Get cached file content if available and current."""
        if filepath in self.file_contents:
            # Check if file has been modified since caching
            if os.path.exists(filepath):
                current_mtime = os.path.getmtime(filepath)
                if current_mtime <= self.file_timestamps.get(filepath, 0):
                    return self.file_contents[filepath]
        
        return None
    
    def get_file_hash(self, filepath: str) -> Optional[str]:
        """Get cached file hash if available."""
        return self.file_hashes.get(filepath)
    
    def record_file_operation(self, filepath: str, operation: str, success: bool, 
                            details: Dict = None, error_message: str = None):
        """Record a file operation for tracking."""
        timestamp = time.time()
        
        operation_record = {
            "timestamp": timestamp,
            "filepath": filepath,
            "operation": operation,
            "success": success,
            "details": details or {},
            "error_message": error_message
        }
        
        self._record_change(operation_record)
        
        # Track active files
        if success:
            self.active_files.add(filepath)
        else:
            # Record error state
            if error_message:
                self.error_states[filepath].append({
                    "timestamp": timestamp,
                    "operation": operation,
                    "error": error_message
                })
    
    def record_command(self, command: str, success: bool, output: str = None, 
                      execution_time: float = None):
        """Record a command execution."""
        command_record = {
            "timestamp": time.time(),
            "command": command,
            "success": success,
            "output": output,
            "execution_time": execution_time
        }
        
        self.recent_commands.append(command_record)
    
    def get_recent_changes(self, filepath: str = None, limit: int = 10) -> List[Dict]:
        """Get recent changes, optionally filtered by filepath."""
        if filepath:
            return [
                change for change in self.change_history
                if change.get("filepath") == filepath
            ][-limit:]
        else:
            return list(self.change_history)[-limit:]
    
    def get_file_change_summary(self, filepath: str) -> Dict:
        """Get a summary of changes for a specific file."""
        file_changes = [
            change for change in self.change_history
            if change.get("filepath") == filepath
        ]
        
        if not file_changes:
            return {"filepath": filepath, "changes": [], "total_changes": 0}
        
        return {
            "filepath": filepath,
            "changes": file_changes,
            "total_changes": len(file_changes),
            "last_change": file_changes[-1] if file_changes else None,
            "change_types": self._count_change_types(file_changes)
        }
    
    def get_session_summary(self) -> Dict:
        """Get a summary of the current session."""
        return {
            "session_duration": time.time() - self.session_start_time,
            "cached_files": len(self.file_contents),
            "active_files": list(self.active_files),
            "total_changes": len(self.change_history),
            "recent_commands": len(self.recent_commands),
            "files_with_errors": list(self.error_states.keys()),
            "current_directory": self.current_directory
        }
    
    def get_current_context(self) -> Dict:
        """Get current working context for the agent."""
        recent_operations = list(self.change_history)[-10:]  # Last 10 operations
        recent_commands = list(self.recent_commands)[-5:]    # Last 5 commands
        
        # Get error context
        error_context = {}
        for filepath, errors in self.error_states.items():
            if errors:
                error_context[filepath] = errors[-1]  # Most recent error
        
        return {
            "working_directory": self.current_directory,
            "active_files": list(self.active_files),
            "recent_operations": recent_operations,
            "recent_commands": recent_commands,
            "error_context": error_context,
            "cached_files_count": len(self.file_contents)
        }
    
    def clear_file_cache(self, filepath: str = None):
        """Clear file cache for specific file or all files."""
        if filepath:
            self.file_contents.pop(filepath, None)
            self.file_hashes.pop(filepath, None)
            self.file_sizes.pop(filepath, None)
            self.file_timestamps.pop(filepath, None)
        else:
            self.file_contents.clear()
            self.file_hashes.clear()
            self.file_sizes.clear()
            self.file_timestamps.clear()
    
    def refresh_file_cache(self, filepath: str) -> bool:
        """Force refresh of cached file content."""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                return self.cache_file_content(filepath, content, force_refresh=True)
            else:
                # File doesn't exist, remove from cache
                self.clear_file_cache(filepath)
                return False
        except Exception as e:
            print(f"Error refreshing file cache for {filepath}: {e}")
            return False
    
    def get_files_needing_refresh(self) -> List[str]:
        """Get list of files that need cache refresh."""
        files_needing_refresh = []
        
        for filepath in self.file_contents.keys():
            if os.path.exists(filepath):
                current_mtime = os.path.getmtime(filepath)
                cached_mtime = self.file_timestamps.get(filepath, 0)
                
                if current_mtime > cached_mtime:
                    files_needing_refresh.append(filepath)
            else:
                # File no longer exists
                files_needing_refresh.append(filepath)
        
        return files_needing_refresh
    
    def _record_change(self, change_record: Dict):
        """Record a change in the change history."""
        self.change_history.append(change_record)
        
        # Also record in current changes for the file
        filepath = change_record.get("filepath")
        if filepath:
            self.current_changes[filepath].append(change_record)
    
    def _manage_cache_size(self):
        """Manage file cache size by removing least recently used files."""
        if len(self.file_contents) <= self.max_file_cache:
            return
        
        # Remove least recently accessed files
        files_by_access = sorted(
            self.file_timestamps.items(),
            key=lambda x: x[1]
        )
        
        files_to_remove = files_by_access[:len(self.file_contents) - self.max_file_cache]
        
        for filepath, _ in files_to_remove:
            self.clear_file_cache(filepath)
    
    def _determine_change_type(self, old_content: str, new_content: str) -> str:
        """Determine the type of change between old and new content."""
        if not old_content and new_content:
            return "file_created"
        elif old_content and not new_content:
            return "file_cleared"
        elif len(new_content) > len(old_content):
            return "content_added"
        elif len(new_content) < len(old_content):
            return "content_removed"
        else:
            return "content_modified"
    
    def _count_change_types(self, changes: List[Dict]) -> Dict[str, int]:
        """Count the types of changes in a list."""
        type_counts = defaultdict(int)
        for change in changes:
            change_type = change.get("change_type", "unknown")
            type_counts[change_type] += 1
        return dict(type_counts)
    
    def export_session_data(self) -> Dict:
        """Export session data for persistence."""
        return {
            "session_start_time": self.session_start_time,
            "current_directory": self.current_directory,
            "active_files": list(self.active_files),
            "recent_commands": list(self.recent_commands),
            "error_states": dict(self.error_states),
            "change_history": list(self.change_history),
            "file_hashes": self.file_hashes,
            "file_sizes": self.file_sizes,
            "file_timestamps": self.file_timestamps
        }
    
    def import_session_data(self, data: Dict):
        """Import session data from previous session."""
        self.session_start_time = data.get("session_start_time", time.time())
        self.current_directory = data.get("current_directory", os.getcwd())
        self.active_files = set(data.get("active_files", []))
        
        # Import recent commands
        for cmd in data.get("recent_commands", []):
            self.recent_commands.append(cmd)
        
        # Import error states
        for filepath, errors in data.get("error_states", {}).items():
            self.error_states[filepath] = errors
        
        # Import change history
        for change in data.get("change_history", []):
            self.change_history.append(change)
        
        # Import file metadata (but not content to save memory)
        self.file_hashes.update(data.get("file_hashes", {}))
        self.file_sizes.update(data.get("file_sizes", {}))
        self.file_timestamps.update(data.get("file_timestamps", {}))
