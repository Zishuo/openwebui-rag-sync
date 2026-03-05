import requests
import time
import pathlib
import json
import datetime
from config import Config

# Suppress insecure request warnings if SSL verification is disabled
import urllib3
if not Config.VERIFY_SSL():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OpenWebUIClient:
    def __init__(self):
        url = Config.BASE_URL().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        self.base_url = url
        self.headers = {
            "Authorization": f"Bearer {Config.API_KEY()}"
        }
        self.verify = Config.VERIFY_SSL()

    def upload_file(self, file_path):
        """Uploads a file and returns the file ID."""
        url = f"{self.base_url}/api/v1/files/"
        path = pathlib.Path(file_path).expanduser()
        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            response = requests.post(url, headers=self.headers, files=files, verify=self.verify)
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
            "access_control": None 
        }
        response = requests.post(url, headers=self.headers, json=payload, verify=self.verify)
        response.raise_for_status()
        return response.json().get("id")

    def get_file_status(self, file_id):
        """Returns the processing status of a file."""
        url = f"{self.base_url}/api/v1/files/{file_id}/process/status"
        response = requests.get(url, headers=self.headers, verify=self.verify)
        response.raise_for_status()
        return response.json()

    def get_content(self, file_id):
        """Retrieves the parsed Markdown content of a file."""
        url = f"{self.base_url}/api/v1/files/{file_id}"
        response = requests.get(url, headers=self.headers, verify=self.verify)
        try:
            response.raise_for_status()
            data = response.json()
            content = data.get("data", {}).get("content")
            if content:
                return content
        except Exception:
            pass

        try:
            url = f"{self.base_url}/api/v1/files/{file_id}/content"
            response = requests.get(url, headers=self.headers, verify=self.verify)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError:
            url = f"{self.base_url}/api/v1/files/{file_id}"
            response = requests.get(url, headers=self.headers, verify=self.verify)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"Content retrieval failed: {response.status_code} - {response.text}")
                raise e
            data = response.json()
            return data.get("meta", {}).get("content", "")

    def list_all_files(self):
        """Returns a list of all files uploaded to the system."""
        url = f"{self.base_url}/api/v1/files/"
        response = requests.get(url, headers=self.headers, verify=self.verify)
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

    def list_knowledge_bases(self):
        """Returns a list of all knowledge bases."""
        url = f"{self.base_url}/api/v1/knowledge/"
        response = requests.get(url, headers=self.headers, verify=self.verify)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["data", "knowledge", "collections", "items"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            if "id" in data and "name" in data:
                return [data]
        return []

    def get_kb_id_by_name(self, name):
        """Resolves a knowledge base name to its ID."""
        kbs = self.list_knowledge_bases()
        for kb in kbs:
            if isinstance(kb, dict):
                if kb.get("name") == name:
                    return kb.get("id")
        return None

    def delete_kb(self, kb_id):
        """Deletes a knowledge base."""
        url = f"{self.base_url}/api/v1/knowledge/{kb_id}/delete"
        response = requests.delete(url, headers=self.headers, verify=self.verify)
        response.raise_for_status()
        return response.json()

    def add_to_kb(self, file_id, kb_id):
        """Links a file to a specific Knowledge Base."""
        url = f"{self.base_url}/api/v1/knowledge/{kb_id}/file/add"
        payload = {"file_id": file_id}
        response = requests.post(url, headers=self.headers, json=payload, verify=self.verify)
        
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
        response = requests.get(url, headers=self.headers, verify=self.verify)
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
