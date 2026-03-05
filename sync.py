import argparse
import pathlib
import subprocess
import os
import datetime
import json
from config import Config
from discovery import discover_files
from versioning import get_changed_files, ensure_git_repo
from api_client import OpenWebUIClient

def main():
    parser = argparse.ArgumentParser(description="OpenWebUI RAG Sync Pipeline")
    parser.add_argument("--path", "-p", help="Source directory to scan for documents (Discovery)")
    parser.add_argument("--keyword", help="Keyword to filter documents during discovery")
    parser.add_argument("--staged-dir", "-s", help="Tracking directory for raw documents (Upload)")
    parser.add_argument("--digest-dir", "-d", help="Destination directory for Markdown digests (Download)")
    parser.add_argument("--kb-id", help="Knowledge Base ID")
    parser.add_argument("--kb-name", help="Knowledge Base Name")
    parser.add_argument("--digest-git", action="store_true", help="Enable Git version control for the digest directory")
    parser.add_argument("--insecure", action="store_true", help="Skip SSL certificate verification")
    
    args = parser.parse_args()

    if args.insecure:
        os.environ["OPENWEBUI_VERIFY_SSL"] = "false"

    # Mode Determination
    if args.path:
        mode = "SYNC"
        staged_dir = args.staged_dir or "staged-docs"
        digest_dir = args.digest_dir or "digest-docs"
    elif args.staged_dir and args.digest_dir:
        mode = "SYNC_STANDALONE"
        staged_dir = args.staged_dir
        digest_dir = args.digest_dir
    elif args.staged_dir:
        mode = "UPLOAD"
        staged_dir = args.staged_dir
        digest_dir = None
    elif args.digest_dir:
        mode = "DOWNLOAD"
        staged_dir = None
        digest_dir = args.digest_dir
    else:
        parser.error("Must provide either --path, --staged-dir, or --digest-dir to determine operation mode.")

    try:
        # 1. Validate configuration (Core API only)
        Config.validate()
        client = OpenWebUIClient()
        
        # 2. Resolve Knowledge Base ID (Only if KB info is provided)
        kb_id = args.kb_id
        if not kb_id and args.kb_name:
            print(f"Resolving Knowledge Base ID for name: '{args.kb_name}'...")
            kb_id = client.get_kb_id_by_name(args.kb_name)
            if not kb_id:
                if mode in ["SYNC", "UPLOAD"] or args.path:
                    print(f"Knowledge Base '{args.kb_name}' not found. Creating it...")
                    kb_id = client.create_kb(args.kb_name, description=f"Sync collection")
                    print(f"Created new Knowledge Base with ID: {kb_id}")
                else:
                    print(f"Warning: Knowledge Base '{args.kb_name}' not found. OpenWebUI features will be skipped.")
        
        if kb_id:
            print(f"Using Knowledge Base ID: {kb_id}")
        else:
            print("No Knowledge Base provided. Skipping OpenWebUI upload/download phases.")

        # Ensure directories exist and get absolute paths
        staged_path = ensure_git_repo(staged_dir) if staged_dir else None
        
        if digest_dir:
            if args.digest_git:
                digest_path = ensure_git_repo(digest_dir)
            else:
                digest_path = pathlib.Path(digest_dir).expanduser().resolve()
                digest_path.mkdir(exist_ok=True, parents=True)
        else:
            digest_path = None

        print(f"\n--- {mode} MODE ---")

        # --- Phase 1: Discovery ---
        discovered_results = []
        if args.path:
            msg = f"\n--- DISCOVERY ---"
            msg += f"\nScanning {args.path}"
            if staged_dir:
                msg += f" into {staged_dir}"
            if args.keyword:
                msg += f" with keyword '{args.keyword}'..."
            else:
                msg += "..."
            print(msg)
            discovered_results = discover_files(args.path, args.keyword, target_dir=staged_dir)
            print(f"Found {len(discovered_results)} document(s).")

        # --- Phase 2: Upload (Requires kb_id) ---
        processed_files = [] 
        success_count = 0
        failed_files = []
        
        upload_queue = []
        if staged_dir:
            print(f"\n--- VERSIONING (Tracking Mode) ---")
            print(f"Checking for changes in {staged_path}...")
            updated_rel, deleted_rel = get_changed_files(staged_dir)
            
            # Deletions
            if deleted_rel:
                print(f"Handling {len(deleted_rel)} deleted file(s)...")
                for rel in deleted_rel:
                    if digest_path:
                        d_name = rel if rel.lower().endswith(".md") else f"{rel}.md"
                        if (digest_path / d_name).exists():
                            (digest_path / d_name).unlink()
                    subprocess.run(["git", "rm", rel], cwd=staged_path, check=True, capture_output=True)

            for rel in updated_rel:
                upload_queue.append({"path": staged_path / rel, "flattened": pathlib.Path(rel).name, "rel_path": rel, "context": staged_path})
        elif discovered_results:
            print(f"\n--- UPLOAD PREP (Direct Mode) ---")
            for item in discovered_results:
                upload_queue.append({"path": item["original"], "flattened": item["flattened"], "rel_path": None, "context": None})

        if upload_queue:
            if not kb_id:
                print(f"Skipping Upload: No Knowledge Base ID or Name provided for {len(upload_queue)} file(s).")
            else:
                print(f"\n--- UPLOAD ---")
                print(f"Processing {len(upload_queue)} file(s)...")
                for item in upload_queue:
                    f_path, f_flattened = item["path"], item["flattened"]
                    try:
                        if item["context"] and item["rel_path"]:
                            subprocess.run(["git", "add", item["rel_path"]], cwd=item["context"], check=True)
                        
                        print(f"Uploading {f_flattened}...")
                        file_id = client.upload_file(str(f_path))
                        
                        print(f"Linking to KB {kb_id}...")
                        result = client.add_to_kb(file_id, kb_id)
                        
                        sync_status = "synced"
                        if isinstance(result, dict) and result.get("status") == "duplicate":
                            print(f"Note: {result.get('message')}")
                        else:
                            print("Successfully linked.")
                        
                        processed_files.append({"id": file_id, "name": f_flattened})
                        success_count += 1
                        
                        if item["context"]:
                            manifest_path = item["context"] / "sync_manifest.json"
                            if manifest_path.exists():
                                with open(manifest_path, "r") as f: manifest = json.load(f)
                                if item["rel_path"] in manifest:
                                    manifest[item["rel_path"]].update({"file_id": file_id, "status": sync_status, "last_sync": datetime.datetime.now().isoformat()})
                                    with open(manifest_path, "w") as f: json.dump(manifest, f, indent=2)
                                    
                    except Exception as e:
                        print(f"Error processing {f_flattened}: {e}")
                        failed_files.append(f_flattened)
                        if item["context"] and item["rel_path"]:
                            log = item["context"] / "sync_failures.log"
                            with open(log, "a") as f: f.write(f"[{datetime.datetime.now()}] FILE: {item['rel_path']} | ERROR: {e}\n")
                            subprocess.run(["git", "rm", "--cached", item["rel_path"]], cwd=item["context"], capture_output=True)
                            manifest_path = item["context"] / "sync_manifest.json"
                            if manifest_path.exists():
                                with open(manifest_path, "r") as f: manifest = json.load(f)
                                if item["rel_path"] in manifest:
                                    manifest[item["rel_path"]].update({"status": "failed", "last_sync": datetime.datetime.now().isoformat()})
                                    with open(manifest_path, "w") as f: json.dump(manifest, f, indent=2)

            # Commit Tracking Repo
            if staged_path and (success_count > 0 or failed_files or deleted_rel):
                print("\nCommitting changes to tracking repository...")
                subprocess.run(["git", "add", "sync_manifest.json", "sync_failures.log"], cwd=staged_path, capture_output=True)
                staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=staged_path, capture_output=True, text=True)
                if staged.stdout.strip():
                    subprocess.run(["git", "commit", "-m", f"feat: sync documents ({success_count} success, {len(failed_files)} failed)"], cwd=staged_path)

        # --- Phase 3: Download (Requires kb_id) ---
        if digest_path:
            if not kb_id:
                print("\nSkipping Download: No Knowledge Base ID or Name provided.")
            else:
                print(f"\n--- DOWNLOAD ---")
                download_list = []
                if processed_files:
                    print(f"Downloading digests for {len(processed_files)} updated files...")
                    download_list = processed_files
                else:
                    print(f"Standalone mode: Fetching all files from Knowledge Base {kb_id}...")
                    kb_files = client.get_kb_files(kb_id)
                    for f in kb_files:
                        meta = f.get("meta", {})
                        download_list.append({"id": f.get("id"), "name": f.get("filename") or meta.get("name") or f"file_{f.get('id')}"})
                    print(f"Found {len(download_list)} files.")

                download_count = 0
                for item in download_list:
                    try:
                        f_id, f_name = item["id"], item["name"]
                        print(f"Downloading: {f_name}...")
                        if processed_files: client.wait_for_processing(f_id)
                        content = client.get_content(f_id)
                        d_name = f_name if f_name.lower().endswith(".md") else f"{f_name}.md"
                        (digest_path / d_name).write_text(content)
                        download_count += 1
                    except Exception as e:
                        print(f"Failed to download {item['name']}: {e}")

                print(f"\nDownload complete. Successfully retrieved {download_count} files.")

                if args.digest_git and download_count > 0:
                    print("Committing changes to digest repository...")
                    subprocess.run(["git", "add", "-A", "."], cwd=digest_path)
                    subprocess.run(["git", "commit", "-m", f"feat: updated digests ({download_count} files)"], cwd=digest_path)

        print("\nPipeline successfully completed.")

    except Exception as e:
        print(f"\nError: {e}")
        exit(1)

if __name__ == "__main__":
    main()
