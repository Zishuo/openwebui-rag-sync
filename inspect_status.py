import requests
import json
from config import Config

def inspect_status(file_id):
    base_url = Config.BASE_URL().rstrip("/")
    headers = {
        "Authorization": f"Bearer {Config.API_KEY()}"
    }
    # 1. Check direct status
    url = f"{base_url}/api/v1/files/{file_id}/process/status"
    print(f"Fetching status from {url}...")
    response = requests.get(url, headers=headers, verify=Config.VERIFY_SSL())
    print(f"Status Code: {response.status_code}")
    try:
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
    except:
        print(f"Raw: {response.text}")

    # 2. Check full file info
    url = f"{base_url}/api/v1/files/{file_id}"
    print(f"\nFetching file info from {url}...")
    response = requests.get(url, headers=headers, verify=Config.VERIFY_SSL())
    try:
        print("File info JSON:")
        print(json.dumps(response.json(), indent=2))
    except:
        print(f"Raw: {response.text}")

if __name__ == "__main__":
    # Use one of the file IDs from the previous run
    inspect_status("f7a12906-9ee0-4a9e-b8f0-77b83cde0ca9")
