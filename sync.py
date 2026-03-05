import argparse
import pathlib
import subprocess
import os
import datetime
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
    
    args = parser.parse_args()

    if not args.kb_id and not args.kb_name:
        parser.error("Must provide either --kb-id or --kb-name")
    
    # Default directories if not provided but needed
    staged_dir = args.staged_dir or ("staged-docs" if args.path else None)
    digest_dir = args.digest_dir or ("digest-docs" if args.path else None)
    
    try:
        # 1. Validate configuration
        Config.validate()
        client = OpenWebUIClient()
        
        # 2. Resolve Knowledge Base ID
        kb_id = args.kb_id
        if not kb_id:
            print(f"Resolving Knowledge Base ID for name: '{args.kb_name}'...")
            kb_id = client.get_kb_id_by_name(args.kb_name)
            if not kb_id:
                if args.path or staged_dir:
                    print(f"Knowledge Base '{args.kb_name}' not found. Creating it...")
                    kb_id = client.create_kb(args.kb_name, description=f"Sync collection")
                    print(f"Created new Knowledge Base with ID: {kb_id}")
                else:
                    raise ValueError(f"Knowledge Base '{args.kb_name}' not found. Cannot download.")
            else:
                print(f"Resolved to ID: {kb_id}")
        else:
            print(f"Using Knowledge Base ID: {kb_id}")

        # --- Phase 1: Discovery ---
        if args.path:
            target_staged = staged_dir or "staged-docs"
            msg = f"\n--- DISCOVERY ---"
            msg += f"\nScanning {args.path} into {target_staged}"
            if args.keyword:
                msg += f" with keyword '{args.keyword}'..."
            else:
                msg += "..."
            print(msg)
            discover_files(args.path, args.keyword, target_dir=target_staged)
            staged_dir = target_staged

        # --- Phase 2: Upload ---
        processed_files = [] # Track (file_id, name) for immediate download
        success_count = 0
        failed_files = []
        
        if staged_dir:
            staged_path = ensure_git_repo(staged_dir)
            print(f"\n--- UPLOAD ---")
            print(f"Checking for changes in {staged_path}...")
            changed_files = get_changed_files(staged_dir)
            
            if not changed_files:
                print("No new or modified files detected.")
            else:
                print(f"Found {len(changed_files)} file(s) to process.")
                failure_log_path = staged_path / "sync_failures.log"

                for rel_file_path in changed_files:
                    abs_file_path = staged_path / rel_file_path
                    try:
                        print(f"\nProcessing {rel_file_path}...")
                        subprocess.run(["git", "add", rel_file_path], cwd=staged_path, check=True)
                        
                        print(f"Uploading to OpenWebUI...")
                        file_id = client.upload_file(str(abs_file_path))
                        f_name = abs_file_path.name
                        print(f"Uploaded. File ID: {file_id}")
                        
                        print(f"Linking to Knowledge Base {kb_id}...")
                        result = client.add_to_kb(file_id, kb_id)
                        if isinstance(result, dict) and result.get("status") == "duplicate":
                            print(f"Note: {result.get('message')}")
                        else:
                            print("Successfully linked.")
                        
                        processed_files.append({"id": file_id, "name": f_name})
                        success_count += 1
                        
                    except Exception as e:
                        error_msg = str(e)
                        print(f"Error processing {rel_file_path}: {error_msg}")
                        failed_files.append(rel_file_path)
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with open(failure_log_path, "a") as f:
                            f.write(f"[{timestamp}] FILE: {rel_file_path} | ERROR: {error_msg}\n")
                        
                        try:
                            subprocess.run(["git", "rm", "--cached", rel_file_path], cwd=staged_path, check=True, capture_output=True)
                            print(f"Unstaged {rel_file_path} for retry.")
                        except Exception:
                            pass

                print(f"\nUpload complete. Success: {success_count}, Failed: {len(failed_files)}")
                if success_count > 0 or len(failed_files) > 0:
                    print("Committing changes to tracking repository...")
                    try:
                        if failure_log_path.exists():
                            subprocess.run(["git", "add", "sync_failures.log"], cwd=staged_path, check=True)
                        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=staged_path, capture_output=True, text=True, check=True)
                        if staged.stdout.strip():
                            commit_msg = f"feat: sync documents ({success_count} success, {len(failed_files)} failed)"
                            subprocess.run(["git", "commit", "-m", commit_msg], cwd=staged_path, check=True)
                    except Exception as e:
                        print(f"Failed to commit: {e}")

        # --- Phase 3: Download ---
        if digest_dir:
            print(f"\n--- DOWNLOAD ---")
            if args.digest_git:
                digest_path = ensure_git_repo(digest_dir)
            else:
                digest_path = pathlib.Path(digest_dir).expanduser().resolve()
                digest_path.mkdir(exist_ok=True, parents=True)
                print(f"Git tracking disabled for {digest_path}")

            download_list = []
            if processed_files:
                # Scenario A: Download exactly what we just uploaded
                print(f"Downloading digests for {len(processed_files)} updated files...")
                download_list = processed_files
            else:
                # Scenario B: Standalone download - fetch all from KB
                print(f"Standalone mode: Fetching all files from Knowledge Base {kb_id}...")
                kb_files = client.get_kb_files(kb_id)
                for f in kb_files:
                    meta = f.get("meta", {})
                    download_list.append({
                        "id": f.get("id"),
                        "name": f.get("filename") or meta.get("name") or f"file_{f.get('id')}"
                    })
                print(f"Found {len(download_list)} files.")

            download_count = 0
            for item in download_list:
                try:
                    f_id = item["id"]
                    f_name = item["name"]
                    print(f"Downloading: {f_name} ({f_id})...")
                    
                    # Ensure it's processed if we just uploaded it
                    if processed_files:
                        client.wait_for_processing(f_id)
                        
                    content = client.get_content(f_id)
                    digest_file_name = f_name if f_name.lower().endswith(".md") else f"{f_name}.md"
                    (digest_path / digest_file_name).write_text(content)
                    download_count += 1
                except Exception as e:
                    print(f"Failed to download {item.get('name')}: {e}")

            print(f"\nDownload complete. Successfully retrieved {download_count} files.")

            if args.digest_git and download_count > 0:
                print("Committing changes to digest tracking repository...")
                try:
                    subprocess.run(["git", "add", "-A", "."], cwd=digest_path, check=True)
                    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=digest_path, capture_output=True, text=True, check=True)
                    if staged.stdout.strip():
                        commit_msg = f"feat: updated digests ({download_count} files)"
                        subprocess.run(["git", "commit", "-m", commit_msg], cwd=digest_path, check=True)
                except Exception as e:
                    print(f"Failed to commit digest: {e}")

        print("\nPipeline successfully completed.")

    except Exception as e:
        print(f"\nError: {e}")
        exit(1)

if __name__ == "__main__":
    main()
