import json
import time
import logging
from typing import Optional, List, Dict, Any
from tinydb import TinyDB, Query

from google.adk.sessions import BaseSessionService, Session
from google.adk.events import Event

# --- Helper Functions (Unchanged) ---
def event_to_dict(event: Event) -> Dict[str, Any]:
    """Simplified serialization for the demo."""
    content_data = {}
    # If the event.content is a mapping/dict-like, store it directly so
    # structured content survives round-trip.
    if isinstance(event.content, dict):
        content_data = event.content
    elif hasattr(event.content, 'model_dump'):
        content_data = event.content.model_dump()
    elif hasattr(event.content, 'text'):
        content_data = {"text": event.content.text}
    else:
        content_data = {"text": str(event.content)}

    return {
        "id": event.id,
        "author": event.author,
        "content": content_data,
        "timestamp": event.timestamp
    }

def dict_to_event(data: Dict[str, Any]) -> Event:
    """Simplified deserialization."""
    raw_content = data.get("content")
    # If we stored a dict, use it directly; if we stored a string under 'text',
    # reconstruct a simple dict with 'text'.
    if isinstance(raw_content, dict):
        content_val = raw_content
    else:
        # raw_content may be a primitive/string
        try:
            # If it's a dict-like JSON stored as string, leave as string
            content_val = {"text": str(raw_content)}
        except Exception:
            content_val = {"text": str(raw_content)}

    return Event(
        id=data["id"],
        author=data["author"],
        content=content_val,
        timestamp=data["timestamp"]
    )


logger = logging.getLogger(__name__)


class TinyDBSessionService(BaseSessionService):
    """
    Manages chat session history using TinyDB.
    """
    def __init__(self, db_path: str = "chat_history_db.json"):
        super().__init__()
        self.db = TinyDB(db_path)
        self.sessions_table = self.db.table("sessions")
        self.SessionQuery = Query()
        logger.debug("Chat Session Service connected to '%s'", db_path)

    async def create_session(self, app_name: str, user_id: str, session_id: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> Session:
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        new_session = Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[]
        )
        
        self.sessions_table.upsert(
            {
                "id": session_id, 
                "app_name": app_name, 
                "user_id": user_id, 
                "state": new_session.state,
                "events": []
            }, 
            self.SessionQuery.id == session_id
        )
        return new_session

    async def get_session(self, app_name: str, user_id: str, session_id: str) -> Optional[Session]:
        result = self.sessions_table.search(
            (self.SessionQuery.app_name == app_name) & 
            (self.SessionQuery.user_id == user_id) & 
            (self.SessionQuery.id == session_id)
        )
        
        if not result:
            return None 

        data = result[0]
        rehydrated_events = [dict_to_event(evt) for evt in data.get("events", [])]
        
        session = Session(
            id=data["id"],
            app_name=data["app_name"],
            user_id=data["user_id"],
            state=data["state"],
            events=rehydrated_events
        )
        logger.debug("Loaded chat session %s with %d events.", session.id, len(session.events))
        return session

    async def append_event(self, session: Session, event: Event):
        session.events.append(event)
        event_data = event_to_dict(event)
        
        current_record = self.sessions_table.get(self.SessionQuery.id == session.id)
        if current_record:
            current_events = current_record.get("events", [])
            current_events.append(event_data)
            
            self.sessions_table.update(
                {"events": current_events, "state": session.state},
                self.SessionQuery.id == session.id
            )

    
    async def delete_session(self, app_name: str, user_id: str, session_id: str):
        """Deletes a session from the TinyDB."""
        logger.debug("Deleting session %s...", session_id)
        self.sessions_table.remove(
            (self.SessionQuery.app_name == app_name) &
            (self.SessionQuery.user_id == user_id) &
            (self.SessionQuery.id == session_id)
        )

    async def list_sessions(self, app_name: str, user_id: str) -> List[Session]:
        """Lists all sessions for a user from the TinyDB."""
        logger.debug("Listing sessions for user %s...", user_id)
        results = self.sessions_table.search(
            (self.SessionQuery.app_name == app_name) & 
            (self.SessionQuery.user_id == user_id)
        )
        
        # Just return basic session info, not all events
        sessions = [
            Session(
                id=data["id"],
                app_name=data["app_name"],
                user_id=data["user_id"],
                state=data["state"],
                events=[] # Don't re-hydrate events for a simple list
            ) for data in results
        ]
        return sessions