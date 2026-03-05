import requests
import time
import pathlib
from config import Config

class OpenWebUIClient:
    def __init__(self):
        self.base_url = Config.BASE_URL().rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {Config.API_KEY()}"
        }

    def upload_file(self, file_path):
        """Uploads a file and returns the file ID."""
        url = f"{self.base_url}/api/v1/files/"
        path = pathlib.Path(file_path).expanduser()
        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            response = requests.post(url, headers=self.headers, files=files)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"Upload failed: {response.status_code} - {response.text}")
                raise e
            return response.json().get("id")

    def create_kb(self, name, description=""):
        """Creates a new knowledge base."""
        url = f"{self.base_url}/api/v1/knowledge/create"
        payload = {
            "name": name,
            "description": description,
            "access_control": None # Default to private/inherited
        }
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json().get("id")

    def get_file_status(self, file_id):
        """Returns the processing status of a file."""
        url = f"{self.base_url}/api/v1/files/{file_id}/process/status"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def list_all_files(self):
        """Returns a list of all files uploaded to the system."""
        url = f"{self.base_url}/api/v1/files/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        return data.get("items", []) if isinstance(data, dict) else data

    def get_kb_files(self, kb_id):
        """Retrieves all files associated with a specific Knowledge Base."""
        all_files = self.list_all_files()
        kb_files = []
        for f in all_files:
            meta = f.get("meta", {}) or {}
            if meta.get("collection_name") == kb_id:
                kb_files.append(f)
        return kb_files

    def get_content(self, file_id):
        """Retrieves the parsed Markdown content of a file."""
        # Check if we already have the file data with content (optional optimization)
        # But for robustness, we'll fetch the latest file details
        url = f"{self.base_url}/api/v1/files/{file_id}"
        response = requests.get(url, headers=self.headers)
        try:
            response.raise_for_status()
            data = response.json()
            # In many versions, content is directly in data['data']['content']
            content = data.get("data", {}).get("content")
            if content:
                return content
        except Exception:
            pass

        # Fallback to specific content endpoint
        try:
            url = f"{self.base_url}/api/v1/files/{file_id}/content"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError:
            # Final fallback to meta
            url = f"{self.base_url}/api/v1/files/{file_id}"
            response = requests.get(url, headers=self.headers)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"Content retrieval failed: {response.status_code} - {response.text}")
                raise e
            data = response.json()
            return data.get("meta", {}).get("content", "")

    def list_knowledge_bases(self):
        """Returns a list of all knowledge bases."""
        url = f"{self.base_url}/api/v1/knowledge/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Try common keys
            for key in ["data", "knowledge", "collections", "items"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # If it's a dict but no list key found, return the dict in a list if it looks like a KB
            if "id" in data and "name" in data:
                return [data]
        
        print(f"Warning: Unexpected KB list format: {type(data)}")
        return []

    def get_kb_id_by_name(self, name):
        """Resolves a knowledge base name to its ID."""
        kbs = self.list_knowledge_bases()
        for kb in kbs:
            # Ensure kb is a dictionary before calling .get()
            if isinstance(kb, dict):
                if kb.get("name") == name:
                    return kb.get("id")
            elif isinstance(kb, str) and kb == name:
                # Fallback if list is just names (unlikely but safe)
                print(f"Warning: Found string '{kb}' in KB list instead of object.")
        return None

    def delete_kb(self, kb_id):
        """Deletes a knowledge base."""
        url = f"{self.base_url}/api/v1/knowledge/{kb_id}/delete"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def add_to_kb(self, file_id, kb_id):
        """Links a file to a specific Knowledge Base."""
        url = f"{self.base_url}/api/v1/knowledge/{kb_id}/file/add"
        payload = {"file_id": file_id}
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code == 400 and "Duplicate content" in response.text:
            return {"status": "duplicate", "message": "Content already exists in Knowledge Base."}
            
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Adding to KB failed: {response.status_code} - {response.text}")
            raise e
        return response.json()

    def get_kb_details(self, kb_id):
        """Returns details of a knowledge base including file list."""
        url = f"{self.base_url}/api/v1/knowledge/{kb_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def wait_for_processing(self, file_id, timeout=120, interval=5):
        """Polls the file status until it's processed or times out."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_info = self.get_file_status(file_id)
            status = status_info.get("status")
            if status == "completed":
                return True
            if status == "failed":
                error = status_info.get("error", "Unknown error")
                raise RuntimeError(f"File processing failed: {error}")
            time.sleep(interval)
        raise TimeoutError(f"File {file_id} processing timed out.")
