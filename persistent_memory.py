"""
Persistent Memory Management System for AI Coding Agent
Handles long-term learning, project patterns, and user preferences
"""
import json
import os
import hashlib
import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
import pickle


class PersistentMemory:
    """Manages persistent memory for the AI coding agent across sessions."""
    
    def __init__(self, project_root: str = None):
        """Initialize persistent memory with project-specific storage."""
        self.project_root = project_root or os.getcwd()
        self.memory_dir = os.path.join(self.project_root, ".ai_agent_memory")
        self._ensure_memory_dir()
        
        # Memory components
        self.project_patterns = self._load_memory("project_patterns.json", {})
        self.user_preferences = self._load_memory("user_preferences.json", {})
        self.success_patterns = self._load_memory("success_patterns.json", {})
        self.tool_effectiveness = self._load_memory("tool_effectiveness.json", {})
        self.file_access_history = self._load_memory("file_access_history.json", {})
        self.code_snippets = self._load_memory("code_snippets.json", {})
        
        # In-memory caches for performance
        self._tool_usage_cache = Counter()
        self._recent_files_cache = []
        self._session_patterns = defaultdict(list)
    
    def _ensure_memory_dir(self):
        """Ensure the memory directory exists."""
        if not os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir)
    
    def _load_memory(self, filename: str, default_value: Any) -> Any:
        """Load memory from file with error handling."""
        filepath = os.path.join(self.memory_dir, filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {filename}: {e}")
        return default_value
    
    def _save_memory(self, filename: str, data: Any):
        """Save memory to file with error handling."""
        filepath = os.path.join(self.memory_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save {filename}: {e}")
    
    def record_file_access(self, filepath: str, operation: str, success: bool, 
                          content_hash: str = None, file_size: int = None):
        """Record file access patterns for learning user preferences."""
        timestamp = datetime.datetime.now().isoformat()
        
        if filepath not in self.file_access_history:
            self.file_access_history[filepath] = {
                "access_count": 0,
                "operations": [],
                "last_accessed": None,
                "file_type": self._get_file_type(filepath),
                "content_hashes": []
            }
        
        record = {
            "timestamp": timestamp,
            "operation": operation,
            "success": success,
            "content_hash": content_hash,
            "file_size": file_size
        }
        
        self.file_access_history[filepath]["access_count"] += 1
        self.file_access_history[filepath]["operations"].append(record)
        self.file_access_history[filepath]["last_accessed"] = timestamp
        
        if content_hash:
            self.file_access_history[filepath]["content_hashes"].append(content_hash)
        
        # Keep only last 50 operations per file
        if len(self.file_access_history[filepath]["operations"]) > 50:
            self.file_access_history[filepath]["operations"] = \
                self.file_access_history[filepath]["operations"][-50:]
        
        self._save_memory("file_access_history.json", self.file_access_history)
    
    def record_tool_usage(self, tool_name: str, success: bool, execution_time: float = None,
                         error_message: str = None, context: Dict = None):
        """Record tool usage effectiveness for optimization."""
        timestamp = datetime.datetime.now().isoformat()
        
        if tool_name not in self.tool_effectiveness:
            self.tool_effectiveness[tool_name] = {
                "total_uses": 0,
                "successful_uses": 0,
                "failed_uses": 0,
                "avg_execution_time": 0,
                "common_errors": Counter(),
                "usage_contexts": [],
                "last_used": None
            }
        
        tool_stats = self.tool_effectiveness[tool_name]
        tool_stats["total_uses"] += 1
        tool_stats["last_used"] = timestamp
        
        if success:
            tool_stats["successful_uses"] += 1
        else:
            tool_stats["failed_uses"] += 1
            if error_message:
                # Use a cleaner version of the error message as a key
                clean_error_message = error_message.split(":")[0].strip()
                # Ensure common_errors is always a Counter (it may be a plain dict after JSON load)
                if not isinstance(tool_stats.get("common_errors"), Counter):
                    tool_stats["common_errors"] = Counter(tool_stats.get("common_errors", {}))
                tool_stats["common_errors"][clean_error_message] += 1
        
        if execution_time:
            # Update average execution time
            current_avg = tool_stats["avg_execution_time"]
            total_uses = tool_stats["total_uses"]
            tool_stats["avg_execution_time"] = (current_avg * (total_uses - 1) + execution_time) / total_uses
        
        if context:
            tool_stats["usage_contexts"].append({
                "timestamp": timestamp,
                "context": context
            })
            # Keep only last 20 contexts
            if len(tool_stats["usage_contexts"]) > 20:
                tool_stats["usage_contexts"] = tool_stats["usage_contexts"][-20:]
        
        self._save_memory("tool_effectiveness.json", self.tool_effectiveness)
    
    def record_success_pattern(self, pattern_type: str, pattern_data: Dict, 
                             success_rate: float, context: Dict = None):
        """Record successful patterns for future reference."""
        timestamp = datetime.datetime.now().isoformat()
        
        if pattern_type not in self.success_patterns:
            self.success_patterns[pattern_type] = []
        
        pattern_record = {
            "timestamp": timestamp,
            "pattern_data": pattern_data,
            "success_rate": success_rate,
            "context": context or {},
            "usage_count": 1
        }
        
        # Check if similar pattern exists
        for existing in self.success_patterns[pattern_type]:
            if self._patterns_similar(pattern_data, existing["pattern_data"]):
                existing["usage_count"] += 1
                existing["success_rate"] = (existing["success_rate"] + success_rate) / 2
                existing["last_used"] = timestamp
                break
        else:
            self.success_patterns[pattern_type].append(pattern_record)
        
        # Keep only top 20 patterns per type
        if len(self.success_patterns[pattern_type]) > 20:
            self.success_patterns[pattern_type].sort(
                key=lambda x: (x["success_rate"], x["usage_count"]), reverse=True
            )
            self.success_patterns[pattern_type] = self.success_patterns[pattern_type][:20]
        
        self._save_memory("success_patterns.json", self.success_patterns)
    
    def record_user_preference(self, preference_type: str, preference_data: Dict):
        """Record user preferences and coding style patterns."""
        timestamp = datetime.datetime.now().isoformat()
        
        if preference_type not in self.user_preferences:
            self.user_preferences[preference_type] = []
        
        preference_record = {
            "timestamp": timestamp,
            "data": preference_data,
            "confidence": 1.0
        }
        
        # Check for existing similar preferences
        for existing in self.user_preferences[preference_type]:
            if self._preferences_similar(preference_data, existing["data"]):
                existing["confidence"] = min(1.0, existing["confidence"] + 0.1)
                existing["last_updated"] = timestamp
                break
        else:
            self.user_preferences[preference_type].append(preference_record)
        
        self._save_memory("user_preferences.json", self.user_preferences)
    
    def record_project_pattern(self, pattern_type: str, pattern_data: Dict, 
                             filepath: str = None, context: Dict = None):
        """Record project-specific patterns and structures."""
        timestamp = datetime.datetime.now().isoformat()
        
        if pattern_type not in self.project_patterns:
            self.project_patterns[pattern_type] = []
        
        pattern_record = {
            "timestamp": timestamp,
            "pattern_data": pattern_data,
            "filepath": filepath,
            "context": context or {},
            "occurrence_count": 1
        }
        
        # Check for existing similar patterns
        for existing in self.project_patterns[pattern_type]:
            if self._patterns_similar(pattern_data, existing["pattern_data"]):
                existing["occurrence_count"] += 1
                existing["last_seen"] = timestamp
                break
        else:
            self.project_patterns[pattern_type].append(pattern_record)
        
        self._save_memory("project_patterns.json", self.project_patterns)
    
    def store_code_snippet(self, snippet: str, snippet_type: str, context: Dict = None,
                          tags: List[str] = None, filepath: str = None):
        """Store useful code snippets for future reference."""
        timestamp = datetime.datetime.now().isoformat()
        snippet_hash = hashlib.md5(snippet.encode()).hexdigest()
        
        snippet_record = {
            "timestamp": timestamp,
            "snippet": snippet,
            "snippet_type": snippet_type,
            "context": context or {},
            "tags": tags or [],
            "filepath": filepath,
            "usage_count": 0,
            "hash": snippet_hash
        }
        
        self.code_snippets[snippet_hash] = snippet_record
        self._save_memory("code_snippets.json", self.code_snippets)
    
    def get_relevant_patterns(self, context: Dict, pattern_type: str = None) -> List[Dict]:
        """Retrieve relevant patterns based on current context."""
        relevant_patterns = []
        
        # Search in success patterns
        if pattern_type and pattern_type in self.success_patterns:
            for pattern in self.success_patterns[pattern_type]:
                if self._context_matches(pattern["context"], context):
                    relevant_patterns.append({
                        "type": "success_pattern",
                        "pattern_type": pattern_type,
                        "data": pattern
                    })
        
        # Search in project patterns
        for ptype, patterns in self.project_patterns.items():
            if pattern_type and ptype != pattern_type:
                continue
            for pattern in patterns:
                if self._context_matches(pattern["context"], context):
                    relevant_patterns.append({
                        "type": "project_pattern",
                        "pattern_type": ptype,
                        "data": pattern
                    })
        
        return sorted(relevant_patterns, 
                     key=lambda x: x["data"].get("occurrence_count", 0) or x["data"].get("usage_count", 0),
                     reverse=True)
    
    def get_user_preferences(self, preference_type: str = None) -> Dict:
        """Get user preferences, optionally filtered by type."""
        if preference_type:
            return self.user_preferences.get(preference_type, [])
        return self.user_preferences
    
    def get_tool_effectiveness(self, tool_name: str = None) -> Dict:
        """Get tool effectiveness statistics."""
        if tool_name:
            return self.tool_effectiveness.get(tool_name, {})
        return self.tool_effectiveness
    
    def get_frequently_accessed_files(self, limit: int = 10) -> List[Dict]:
        """Get list of frequently accessed files."""
        files = []
        for filepath, data in self.file_access_history.items():
            files.append({
                "filepath": filepath,
                "access_count": data["access_count"],
                "last_accessed": data["last_accessed"],
                "file_type": data["file_type"]
            })
        
        return sorted(files, key=lambda x: x["access_count"], reverse=True)[:limit]
    
    def search_code_snippets(self, query: str = None, snippet_type: str = None, 
                           tags: List[str] = None) -> List[Dict]:
        """Search stored code snippets."""
        results = []
        
        for snippet_hash, snippet_data in self.code_snippets.items():
            # Filter by type
            if snippet_type and snippet_data["snippet_type"] != snippet_type:
                continue
            
            # Filter by tags
            if tags and not any(tag in snippet_data["tags"] for tag in tags):
                continue
            
            # Filter by query
            if query and query.lower() not in snippet_data["snippet"].lower():
                continue
            
            results.append(snippet_data)
        
        return sorted(results, key=lambda x: x["usage_count"], reverse=True)
    
    def _get_file_type(self, filepath: str) -> str:
        """Determine file type from extension."""
        _, ext = os.path.splitext(filepath)
        return ext.lower() if ext else "unknown"
    
    def _patterns_similar(self, pattern1: Dict, pattern2: Dict, threshold: float = 0.8) -> bool:
        """Check if two patterns are similar enough to be considered the same."""
        # Simple similarity check - can be enhanced with more sophisticated algorithms
        keys1 = set(pattern1.keys())
        keys2 = set(pattern2.keys())
        
        if not keys1 or not keys2:
            return False
        
        intersection = keys1.intersection(keys2)
        union = keys1.union(keys2)
        
        if not union:
            return False
        
        similarity = len(intersection) / len(union)
        return similarity >= threshold
    
    def _preferences_similar(self, pref1: Dict, pref2: Dict, threshold: float = 0.7) -> bool:
        """Check if two preferences are similar."""
        return self._patterns_similar(pref1, pref2, threshold)
    
    def _context_matches(self, pattern_context: Dict, current_context: Dict, 
                        threshold: float = 0.6) -> bool:
        """Check if current context matches a pattern context."""
        if not pattern_context or not current_context:
            return True  # Empty contexts match everything
        
        # Simple context matching - can be enhanced
        pattern_keys = set(pattern_context.keys())
        current_keys = set(current_context.keys())
        
        if not pattern_keys:
            return True
        
        intersection = pattern_keys.intersection(current_keys)
        if not intersection:
            return False
        
        # Check if values match for intersecting keys
        matches = 0
        for key in intersection:
            if pattern_context[key] == current_context[key]:
                matches += 1
        
        return matches / len(pattern_keys) >= threshold
    
    def get_memory_summary(self) -> Dict:
        """Get a summary of all memory components."""
        return {
            "project_patterns": {
                "total_patterns": sum(len(patterns) for patterns in self.project_patterns.values()),
                "pattern_types": list(self.project_patterns.keys())
            },
            "user_preferences": {
                "total_preferences": sum(len(prefs) for prefs in self.user_preferences.values()),
                "preference_types": list(self.user_preferences.keys())
            },
            "success_patterns": {
                "total_patterns": sum(len(patterns) for patterns in self.success_patterns.values()),
                "pattern_types": list(self.success_patterns.keys())
            },
            "tool_effectiveness": {
                "total_tools": len(self.tool_effectiveness),
                "tools": list(self.tool_effectiveness.keys())
            },
            "file_access_history": {
                "total_files": len(self.file_access_history),
                "total_accesses": sum(data["access_count"] for data in self.file_access_history.values())
            },
            "code_snippets": {
                "total_snippets": len(self.code_snippets)
            }
        }
    
    def cleanup_old_memory(self, days_old: int = 30):
        """Clean up old memory entries to prevent bloat."""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
        cutoff_iso = cutoff_date.isoformat()
        
        # Clean up old file access records
        for filepath, data in self.file_access_history.items():
            data["operations"] = [
                op for op in data["operations"] 
                if op["timestamp"] > cutoff_iso
            ]
        
        # Clean up old tool usage contexts
        for tool_name, data in self.tool_effectiveness.items():
            data["usage_contexts"] = [
                ctx for ctx in data["usage_contexts"]
                if ctx["timestamp"] > cutoff_iso
            ]
        
        # Save cleaned data
        self._save_memory("file_access_history.json", self.file_access_history)
        self._save_memory("tool_effectiveness.json", self.tool_effectiveness)