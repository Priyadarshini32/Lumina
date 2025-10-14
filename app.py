from flask import Flask, render_template, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
from db_manager import get_all_conversations

app = Flask(__name__)
CORS(app)

@app.template_filter('format_timestamp')
def format_timestamp_filter(timestamp):
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return timestamp

@app.template_filter('format_date_display')
def format_date_display_filter(date_str):
    # Assumes date_str is in 'YYYY-MM-DD' format
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%A, %B %d, %Y')

@app.template_filter('format_time_display')
def format_time_display_filter(timestamp_str):
    # Assumes timestamp_str is in ISO format like 'YYYY-MM-DDTHH:MM:SS.ffffff'
    return datetime.fromisoformat(timestamp_str).strftime('%H:%M:%S')

@app.template_filter('tojson')
def to_json_filter(value):
    return json.dumps(value, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history/<string:selected_date>')
def daily_history(selected_date):
    all_conversations = get_all_conversations()
    filtered_conversations = [conv for conv in all_conversations 
                              if datetime.fromisoformat(conv["timestamp"]).strftime('%Y-%m-%d') == selected_date]
    return render_template('daily_history.html', conversations=filtered_conversations, selected_date=selected_date)

@app.route('/memory/<int:conversation_id>')
def memory_detail(conversation_id):
    conversations = get_all_conversations()
    conversation = next((conv for conv in conversations if conv["id"] == conversation_id), None)
    if conversation:
        return render_template('memory_detail.html', conversation=conversation)
    return "Conversation not found", 404

@app.route('/api/history')
def get_history():
    conversations = get_all_conversations()
    return jsonify(conversations)

@app.route('/api/memory')
def get_memory():
    conversations = get_all_conversations()
    memory_snapshots = []
    for conv in conversations:
        memory_snapshots.append({
            "conversation_id": conv["id"],
            "timestamp": conv["timestamp"],
            "memory_summary": conv["memory_summary"]
        })
    return jsonify(memory_snapshots)

@app.route('/api/insights')
def get_insights():
    conversations = get_all_conversations()
    total_conversations = len(conversations)
    total_tools_used = 0
    tool_usage_counts = {}
    recent_files = set()
    total_changes = 0
    total_files_accessed = 0

    for conv in conversations:
        if conv["tools_used"]:
            total_tools_used += len(conv["tools_used"])
            for tool in conv["tools_used"]:
                tool_usage_counts[tool] = tool_usage_counts.get(tool, 0) + 1

        if conv["memory_summary"] and conv["memory_summary"].get("session"):
            session_mem = conv["memory_summary"]["session"]
            if session_mem.get("active_files"):
                for file_path in session_mem["active_files"]:
                    recent_files.add(file_path)
            total_changes += session_mem.get("total_changes", 0)
        
        if conv["memory_summary"] and conv["memory_summary"].get("persistent") and conv["memory_summary"]["persistent"].get("file_access_history"):
            total_files_accessed += conv["memory_summary"]["persistent"]["file_access_history"].get("total_files", 0)

    most_used_tools = sorted(tool_usage_counts.items(), key=lambda item: item[1], reverse=True)[:5] # Top 5

    insights = {
        "total_conversations": total_conversations,
        "total_tools_executed": total_tools_used,
        "unique_files_accessed": len(recent_files),
        "total_changes_made": total_changes,
        "most_used_tools": [{ "tool": tool, "count": count } for tool, count in most_used_tools]
    }
    return jsonify(insights)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)