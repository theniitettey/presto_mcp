"""Simple JSON-based session storage for persistence"""
import json
import os
from typing import Dict, Any
import threading

class SessionStore:
    def __init__(self, file_path: str = 'data/sessions.json'):
        self.file_path = file_path
        self.lock = threading.Lock()
        self.sessions = self._load()
    
    def _load(self) -> Dict:
        """Load sessions from JSON file"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Error loading sessions: {e}")
                return {}
        return {}
    
    def _save(self):
        """Save sessions to JSON file"""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.sessions, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving sessions: {e}")
    
    def get(self, session_id: str) -> Any:
        """Get session data"""
        with self.lock:
            return self.sessions.get(session_id)
    
    def set(self, session_id: str, data: Any):
        """Set session data and persist"""
        with self.lock:
            self.sessions[session_id] = data
            self._save()
    
    def delete(self, session_id: str):
        """Delete session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                self._save()
    
    def all(self) -> Dict:
        """Get all sessions"""
        with self.lock:
            return self.sessions.copy()

# Global instance
session_store = SessionStore()
