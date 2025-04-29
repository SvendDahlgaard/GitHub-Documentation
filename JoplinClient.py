import requests as req
import json
import os
from dotenv import load_dotenv, find_dotenv

class JoplinClient:
    def __init__(self, token = None, port = 41184):
        """"
                Initialize the Joplin client.
        
        Args:
            token: Joplin API token (if None, tries to read from environment)
            port: Port number for Joplin API (default: 41184)
        """

        if token is None:
            load_dotenv()
            token = os.getenv("JOPLIN_TOKEN")
        
        if token is None:
            EnvPath = find_dotenv()
            raise ValueError(f"No JOPLIN_TOKEN found in file {EnvPath}")
        
        self.token = token
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.NoteEndPoint = f"{self.base_url}/notes?token={self.token}"
        self.FolderEndPoint = f"{self.base_url}/folders?token={self.token}"



    def CreateNote(self, title, body, parent_id = None):
        """
        Create a new note in Joplin.
        
        Args:
            title: The note title
            body: The note body in Markdown
            parent_id: Optional ID of the notebook to place the note in
            
        Returns:
            The created note data if successful, None otherwise
        """

        data = {
            "title": title,
            "body": body
        }

        if parent_id:
            data["parent_id"] = parent_id
        
        response = req.post(self.NoteEndPoint, json=data)

        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Error creating Note: {response.status_code}. Message: {response.text}")
        
    def CreateFolder(self, title, parent_id = None):
        """
        Create a folder in Joplin
        
        Args:
            title: The notebook title
            parent_id: Optional ID of the parent notebook to create nested notebooks

        Returns:
            The created notebook data if successful, None otherwise
        """
        
        data = {
            "title": title
        }

        if parent_id:
            data["parent_id"] = parent_id

        response = req.post(self.FolderEndPoint, json=data)

        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Error creating Folder: {response.status_code}. Message: {response.text}")



    def GetNotebook(self):
        """Get all notebooks (folders)."""
        response = req.get(self.NoteEndPoint)

        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Error getting notebooks: {response.status_code}. Message: {response.text}")


    
if __name__ == "__main__":
    JoplinClient()
