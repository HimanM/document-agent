import os
import google.generativeai as genai
from services.knowledge_service import KnowledgeService

# This model is for the *tool itself* to use for summarization
summarization_model = genai.GenerativeModel("gemini-2.0-flash")

# --- THIS IS THE STATIC KNOWLEDGE FOLDER ---
STATIC_KNOWLEDGE_FOLDER = "./resumes/"

def create_document_tools(knowledge_service: KnowledgeService):
    """
    Factory function to create tool closures with access to the 
    knowledge service.
    """

    async def process_static_resumes_tool() -> str:
        """
        Processes all PDF and image files in the hardcoded 'resumes'
        folder. It uploads each file to be summarized, then saves the
        summary to the TinyDB knowledge base.
        """
        print(f"Tool called: process_static_resumes_tool on '{STATIC_KNOWLEDGE_FOLDER}'")
        try:
            # Check if directory exists
            if not os.path.isdir(STATIC_KNOWLEDGE_FOLDER):
                return f"Error: The directory '{STATIC_KNOWLEDGE_FOLDER}' does not exist."
                
            files = os.listdir(STATIC_KNOWLEDGE_FOLDER)
            if not files:
                return f"No files found in '{STATIC_KNOWLEDGE_FOLDER}' to process."
                
            processed_count = 0
            
            for file_name in files:
                file_path = os.path.join(STATIC_KNOWLEDGE_FOLDER, file_name)
                
                # Determine file type and prompt
                prompt = ""
                source_type = "unknown"
                if file_name.lower().endswith(".pdf"):
                    prompt = "Summarize this resume. Extract key skills, all work experience (company, role, dates), and education."
                    source_type = "Resume (PDF)"
                elif file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                    prompt = "Describe this image in detail."
                    source_type = "Image"
                else:
                    continue # Skip unsupported files

                print(f"Tool: Processing {file_name}...")
                
                # 1. Upload file as a "Prompt Artifact"
                uploaded_file = genai.upload_file(path=file_path)
                
                
                # 2. Call the model to get the summary
                response = await summarization_model.generate_content_async(
                    [uploaded_file, prompt],
                    stream=False  # <-- Make sure this is here
                )
                
                # 3. Save summary to our knowledge DB
                knowledge_service.save_summary(
                    file_name=file_name,
                    summary=response.text,
                    source_type=source_type
                )
                
                # 4. Clean up the uploaded file
                genai.delete_file(uploaded_file.name)
                processed_count += 1
                
            if processed_count == 0:
                return "No new supported files (PDF/Image) found in the 'resumes' folder."

            return f"Successfully processed and saved summaries for {processed_count} files."
        
        except FileNotFoundError:
            return f"Error: The folder '{STATIC_KNOWLEDGE_FOLDER}' was not found."
        except Exception as e:
            print(f"Error in tool: {e}") 
            return f"An error occurred: {str(e)}"

    async def query_knowledge_base_tool() -> str:
        """
        Retrieves all file summaries (resumes, etc.) from the 
        TinyDB knowledge base. The agent can then use this 
        information to answer questions.
        """
        print("Tool called: query_knowledge_base_tool")
        return knowledge_service.get_all_summaries()

    # Return the list of raw functions
    return [process_static_resumes_tool, query_knowledge_base_tool]