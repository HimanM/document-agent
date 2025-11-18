import tinydb

class KnowledgeService:
    """
    Manages a persistent TinyDB knowledge base for file summaries.
    This is separate from the chat session history.
    """
    def __init__(self, db_path: str = "knowledge_db.json"):
        self.db = tinydb.TinyDB(db_path)
        self.table = self.db.table("knowledge")
        print(f"Knowledge Service connected to '{db_path}'")

    def save_summary(self, file_name: str, summary: str, source_type: str):
        """Saves or updates a summary for a specific file."""
        KnowledgeQuery = tinydb.Query()
        self.table.upsert(
            {"file_name": file_name, "summary": summary, "type": source_type},
            KnowledgeQuery.file_name == file_name
        )
        print(f"Knowledge Service: Saved summary for: {file_name}")

    def has_summary(self, file_name: str) -> bool:
        """Return True if a summary for the given file_name already exists."""
        KnowledgeQuery = tinydb.Query()
        res = self.table.search(KnowledgeQuery.file_name == file_name)
        return len(res) > 0

    def get_summary(self, file_name: str):
        """Return the stored summary document for a given file_name, or None."""
        KnowledgeQuery = tinydb.Query()
        res = self.table.get(KnowledgeQuery.file_name == file_name)
        return res

    def get_all_summaries(self) -> str:
        """Retrieves all stored summaries as a single string for the LLM."""
        all_docs = self.table.all()
        if not all_docs:
            return "No knowledge has been stored yet. Please run the processing tool."
        
        knowledge_string = "Here is the current knowledge base:\n\n"
        for doc in all_docs:
            knowledge_string += f"--- START OF DOC: {doc['file_name']} ---\n"
            knowledge_string += f"TYPE: {doc['type']}\n"
            knowledge_string += f"SUMMARY: {doc['summary']}\n"
            knowledge_string += f"--- END OF DOC: {doc['file_name']} ---\n\n"
        
        return knowledge_string