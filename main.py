import asyncio
import os
import re
from dotenv import load_dotenv
import google.generativeai as genai
import time
import logging

# Use ADK Event objects for messages
from google.adk.events import Event
from google.genai import types as genai_types
from adk_config import runner, agent
from google.adk.sessions import Session


class LocalMessage:
    """Lightweight message object with `role` and `content` attributes
    to mimic the ADK Message shape expected by Runner.run_async.
    """
    def __init__(self, *, content, role: str = "user"):
        self.content = content
        self.role = role
        # Normalize parts so Runner can access `new_message.parts`
        # If content is a genai.types.Content with parts, use them.
        if hasattr(content, 'parts') and content.parts is not None:
            self.parts = list(content.parts)
        else:
            # If content has a text attribute, use it; otherwise stringify
            text_val = None
            if hasattr(content, 'text') and content.text:
                text_val = content.text
            elif isinstance(content, str):
                text_val = content
            elif content is None:
                text_val = ""
            else:
                try:
                    text_val = str(content)
                except Exception:
                    text_val = ""

            # Wrap into a single Part
            try:
                self.parts = [genai_types.Part(text=text_val)]
            except Exception:
                # Fallback: simple dict-like part
                class _P: pass
                p = _P()
                p.text = text_val
                self.parts = [p]

FILE_PATTERN = re.compile(r"\[file:\s*(.*?)\s*\]")


def find_file_by_basename(basename: str) -> str | None:
    """Search the workspace (cwd) for a file with the given basename and
    return the first matching absolute path, or None if not found.
    """
    start = os.getcwd()
    for root, dirs, files in os.walk(start):
        if basename in files:
            return os.path.join(root, basename)
    return None

async def main():
    # Load .env from project root so environment variables (GITHUB_USERNAME,
    # GEMINI_API_KEY, etc.) are available without needing to set them via CLI.
    repo_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(repo_root, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # Fallback to default behavior (look in cwd / environment)
        load_dotenv()
    # Configure logging optionally via DEBUG env
    if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    except KeyError:
        return
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return

    user_id = "doc_user_1"
    session_id = "doc_chat_session" 

    print("--- Starting Document Agent ---")
    print(f"Using chat session: {session_id}")
    print("Agent will consult the user's GitHub (if available) when crafting emails/cover letters.")
    print("Agent: Hello! I am ready.")
    print("\nTry these commands:")
    print("1. 'Process my resumes' (to load static knowledge)")
    print("2. 'Write a cover letter for this job [file: user_uploads/job_posting.jpg]'")
    print("(Type 'quit' to exit)\n")
    
    while True:
        try:
            user_message = input("You: ")
            if user_message.lower().strip() == 'quit':
                print("Agent: Goodbye! Your session is saved.")
                break

            text_part = user_message
            temp_file_to_delete = None
            
            # --- This logic is correct ---
            message_content_parts = []

            # 1. Check for file paths
            match = FILE_PATTERN.search(user_message)
            
            if match:
                file_path_str = match.group(1).strip()
                text_part = FILE_PATTERN.sub("", user_message).strip()
                
                # If the provided path doesn't exist, try searching by basename
                resolved_path = None
                if os.path.exists(file_path_str):
                    resolved_path = file_path_str
                else:
                    basename = os.path.basename(file_path_str)
                    found = find_file_by_basename(basename)
                    if found:
                        resolved_path = found
                        print(f"Found file by basename: using {resolved_path}")
                    else:
                        print(f"\nWarning: File not found at {file_path_str}. Sending text only.\n")

                if resolved_path:
                    print(f"Uploading {resolved_path} as dynamic context...")
                    # Upload the file using genai
                    uploaded_file = genai.upload_file(path=resolved_path)
                    # Add the file object to our parts list
                    message_content_parts.append(uploaded_file)
                    temp_file_to_delete = uploaded_file
            
            # 2. Add the text part (as a simple string)
            message_content_parts.append(text_part)
            
            # 3. Create an ADK Event object. Combine text and any uploaded file
            # references into a single content string so the session/event
            # serializers can persist it.
            # Build a google.genai.types.Content with Parts for text and files
            parts = []
            for part in message_content_parts:
                if hasattr(part, "name"):
                    # If uploaded_file has a name/filename, attach as FileData
                    try:
                        filedata = genai_types.FileData(name=part.name)
                        parts.append(genai_types.Part(file_data=filedata))
                    except Exception:
                        # Fallback: include a simple text reference
                        parts.append(genai_types.Part(text=f"[uploaded_file:{getattr(part,'name',str(part))}]"))
                else:
                    parts.append(genai_types.Part(text=str(part)))

            content_obj = genai_types.Content(parts=parts)

            # Construct a lightweight message object with .role and .content
            # Runner.run_async expects new_message.role to exist, so use
            # LocalMessage to satisfy that contract.
            final_message_to_send = LocalMessage(content=content_obj, role="user")
            # --- End of logic ---

            agent_response_text = ""
            print("Agent: ...", end="", flush=True) 

            # Ensure the session exists before running the agent
            try:
                existing_session = await runner.session_service.get_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
            except Exception:
                existing_session = None

            if not existing_session:
                await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)

            # Pass the 'Message' object. This will have the '.role' attribute.
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=final_message_to_send 
            ):
                if event.author == agent.name:
                    # Extract text from event.content which may be a genai.types.Content
                    content = getattr(event, 'content', None)
                    text_parts = []
                    if content is None:
                        agent_response_text = ""
                    else:
                        # If it's a simple string
                        if isinstance(content, str):
                            agent_response_text = content
                        else:
                            # If it has 'text' attribute, prefer it
                            if hasattr(content, 'text') and content.text:
                                agent_response_text = content.text
                            else:
                                # Try to assemble from .parts
                                parts = getattr(content, 'parts', None)
                                if parts:
                                    for p in parts:
                                        if getattr(p, 'text', None):
                                            text_parts.append(p.text)
                                    agent_response_text = "\n".join(text_parts).strip()
            
            if agent_response_text:
                print(f"\rAgent: {agent_response_text}  ") 
            else:
                print("\rAgent: (Action completed)   ")

        except Exception as e:
            import traceback
            print(f"\nAn error occurred: {e}")
            traceback.print_exc()
        
        finally:
            if temp_file_to_delete:
                print(f"Cleaning up {temp_file_to_delete.name}...")
                genai.delete_file(temp_file_to_delete.name)

if __name__ == "__main__":
    asyncio.run(main())