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
from utils import log

def main():
    parser = argparse.ArgumentParser(description="OpenWebUI RAG Sync Pipeline")
    parser.add_argument("--path", "-p", help="Source directory to scan for documents (Discovery)")
    parser.add_argument("--keyword", help="Keyword to filter documents during discovery")
    parser.add_argument("--staged-dir", "-s", help="Tracking directory for raw documents (Upload)")
    parser.add_argument("--export-dir", "-e", help="Destination directory for Markdown exports (Export)")
    parser.add_argument("--kb-id", help="Knowledge Base ID")
    parser.add_argument("--kb-name", help="Knowledge Base Name")
    parser.add_argument("--export-git", action="store_true", help="Enable Git version control for the export directory")
    parser.add_argument("--force", action="store_true", help="Force upload all files, ignoring Git tracking")
    parser.add_argument("--insecure", action="store_true", help="Skip SSL certificate verification")
    
    args = parser.parse_args()

    if args.insecure:
        os.environ["OPENWEBUI_VERIFY_SSL"] = "false"

    # Mode Determination
    if args.path:
        mode = "SYNC"
        staged_dir = args.staged_dir or "staged-docs"
        export_dir = args.export_dir
    elif args.staged_dir and args.export_dir:
        mode = "SYNC_STANDALONE"
        staged_dir = args.staged_dir
        export_dir = args.export_dir
    elif args.staged_dir:
        mode = "UPLOAD"
        staged_dir = args.staged_dir
        export_dir = None
    elif args.export_dir:
        mode = "EXPORT"
        staged_dir = None
        export_dir = args.export_dir
    else:
        parser.error("Must provide either --path, --staged-dir, or --export-dir to determine operation mode.")

    try:
        # 1. Validate configuration
        Config.validate()
        client = OpenWebUIClient()
        
        log("CONFIG", f"Mode: {mode}")
        
        # 2. Resolve Knowledge Base ID
        kb_id = args.kb_id
        if not kb_id and args.kb_name:
            log("API", f"Resolving Knowledge Base ID for name: '{args.kb_name}'...")
            kb_id = client.get_kb_id_by_name(args.kb_name)
            if not kb_id:
                if mode in ["SYNC", "UPLOAD"] or args.path:
                    log("API", f"Knowledge Base '{args.kb_name}' not found. Creating it...")
                    kb_id = client.create_kb(args.kb_name, description=f"Sync collection")
                    log("API", f"Created new Knowledge Base with ID: {kb_id}")
                else:
                    log("API", f"Warning: Knowledge Base '{args.kb_name}' not found. Skipping OpenWebUI phases.")
        
        if kb_id:
            log("API", f"Using Knowledge Base ID: {kb_id}")
        else:
            log("API", "No Knowledge Base provided. Skipping upload/download phases.")

        # Ensure directories exist
        staged_path = ensure_git_repo(staged_dir) if staged_dir else None
        if export_dir:
            if args.export_git:
                export_path = ensure_git_repo(export_dir)
            else:
                export_path = pathlib.Path(export_dir).expanduser().resolve()
                export_path.mkdir(exist_ok=True, parents=True)
        else:
            export_path = None

        # --- Phase 1: Discovery ---
        discovered_results = []
        if args.path:
            log("DISCOVERY", f"Scanning {args.path}...")
            discovered_results = discover_files(args.path, args.keyword, target_dir=staged_dir)
            log("DISCOVERY", f"Found {len(discovered_results)} document(s).")

        # --- Phase 2: Upload ---
        processed_files = [] 
        success_count = 0
        failed_files = []
        upload_queue = []
        
        if staged_dir:
            if args.force:
                log("VERSIONING", f"Forcing upload for all files in {staged_path}...")
                for path in staged_path.rglob('*'):
                    if path.is_file():
                        rel_parts = list(path.relative_to(staged_path).parts)
                        # Skip .git/ directory contents and sync tracking files
                        if ".git" in rel_parts or ".svn" in rel_parts:
                            continue
                        if path.name in ["sync_manifest.json", "sync_failures.log", ".DS_Store"]:
                            continue
                        upload_queue.append({"path": path, "flattened": path.name, "rel_path": str(path.relative_to(staged_path)), "context": staged_path})
            else:
                log("VERSIONING", f"Checking for changes in {staged_path}...")
                updated_rel, deleted_rel = get_changed_files(staged_dir)
                
                if deleted_rel:
                    log("CLEANUP", f"Handling {len(deleted_rel)} deleted file(s)...")
                    for rel in deleted_rel:
                        if export_path:
                            export_filename = rel if rel.lower().endswith(".md") else f"{rel}.md"
                            if (export_path / export_filename).exists():
                                log("CLEANUP", f"Deleting local export: {export_filename}")
                                (export_path / export_filename).unlink()
                        subprocess.run(["git", "rm", rel], cwd=staged_path, check=True, capture_output=True)

                for rel in updated_rel:
                    upload_queue.append({"path": staged_path / rel, "flattened": pathlib.Path(rel).name, "rel_path": rel, "context": staged_path})
        elif discovered_results:
            log("VERSIONING", "Adding discovered files to upload queue...")
            for item in discovered_results:
                upload_queue.append({"path": item["original"], "flattened": item["flattened"], "rel_path": None, "context": None})

        if upload_queue:
            if not kb_id:
                log("UPLOAD", f"Skipping Upload: No Knowledge Base ID provided for {len(upload_queue)} files.")
            else:
                log("UPLOAD", f"Processing {len(upload_queue)} file(s)...")
                failure_log_path = staged_path / "sync_failures.log" if staged_path else None
                manifest_path = staged_path / "sync_manifest.json" if staged_path else None

                for item in upload_queue:
                    f_path, f_flattened = item["path"], item["flattened"]
                    rel_file_path = item["rel_path"]
                    try:
                        # Validation
                        if f_path.stat().st_size == 0:
                            log("VERSIONING", f"Skipping empty file: {f_flattened}")
                            continue
                        
                        if f_path.suffix.lower() == '.md':
                            with open(f_path, 'r', errors='ignore') as f:
                                if not f.read().strip():
                                    log("VERSIONING", f"Skipping empty Markdown: {f_flattened}")
                                    continue

                        if item["context"] and rel_file_path:
                            subprocess.run(["git", "add", rel_file_path], cwd=item["context"], check=True)
                        
                        log("UPLOAD", f"Uploading: {f_flattened}")
                        file_id = client.upload_file(str(f_path))
                        
                        log("UPLOAD", f"Waiting for processing: {file_id}")
                        client.wait_for_processing(file_id)
                        
                        log("UPLOAD", f"Linking to KB...")
                        result = client.add_to_kb(file_id, kb_id)
                        
                        sync_status = "synced"
                        if isinstance(result, dict) and result.get("status") == "duplicate":
                            log("UPLOAD", f"Soft Success: Content already exists.")
                        else:
                            log("UPLOAD", "Successfully linked.")
                        
                        processed_files.append({"id": file_id, "name": f_flattened})
                        success_count += 1
                        
                        # Manifest update
                        if manifest_path and manifest_path.exists() and rel_file_path:
                            with open(manifest_path, "r") as f: manifest = json.load(f)
                            updated_m = False
                            if "repositories" in manifest:
                                for r_data in manifest["repositories"].values():
                                    if rel_file_path in r_data.get("files", {}):
                                        r_data["files"][rel_file_path].update({
                                            "file_id": file_id, "status": sync_status, "last_sync": datetime.datetime.now().isoformat()
                                        })
                                        updated_m = True
                                        break
                            if updated_m:
                                with open(manifest_path, "w") as f: json.dump(manifest, f, indent=2)
                                    
                    except Exception as e:
                        log("ERROR", f"Failed {f_flattened}: {e}")
                        failed_files.append(f_flattened)
                        if item["context"] and rel_file_path:
                            if failure_log_path:
                                with open(failure_log_path, "a") as f:
                                    f.write(f"[{datetime.datetime.now()}] FILE: {rel_file_path} | ERROR: {e}\n")
                            subprocess.run(["git", "rm", "--cached", rel_file_path], cwd=item["context"], capture_output=True)
                            if manifest_path and manifest_path.exists():
                                with open(manifest_path, "r") as f: manifest = json.load(f)
                                updated_m = False
                                if "repositories" in manifest:
                                    for r_data in manifest["repositories"].values():
                                        if rel_file_path in r_data.get("files", {}):
                                            r_data["files"][rel_file_path].update({
                                                "status": "failed", "last_sync": datetime.datetime.now().isoformat()
                                            })
                                            updated_m = True
                                            break
                                if updated_m:
                                    with open(manifest_path, "w") as f: json.dump(manifest, f, indent=2)

            if staged_path and (success_count > 0 or failed_files or (deleted_rel if 'deleted_rel' in locals() else False)):
                log("GIT", "Committing changes to tracking repository...")
                subprocess.run(["git", "add", "sync_manifest.json", "sync_failures.log"], cwd=staged_path, capture_output=True)
                staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=staged_path, capture_output=True, text=True)
                if staged.stdout.strip():
                    subprocess.run(["git", "commit", "-m", f"feat: sync ({success_count} success, {len(failed_files)} failed)"], cwd=staged_path)

        # --- Phase 3: Export ---
        if export_path:
            if not kb_id:
                log("EXPORT", "Skipping Export: No Knowledge Base provided.")
            else:
                export_list = []
                if processed_files:
                    log("EXPORT", f"Exporting {len(processed_files)} updated files...")
                    export_list = processed_files
                else:
                    log("EXPORT", f"Fetching all files from Knowledge Base {kb_id} for export...")
                    kb_files = client.get_kb_files(kb_id)
                    for f in kb_files:
                        meta = f.get("meta", {})
                        export_list.append({"id": f.get("id"), "name": f.get("filename") or meta.get("name") or f"file_{f.get('id')}"})
                    log("EXPORT", f"Found {len(export_list)} files.")

                export_count = 0
                for item in export_list:
                    try:
                        f_id, f_name = item["id"], item["name"]
                        log("EXPORT", f"Retrieving: {f_name}")
                        if processed_files: client.wait_for_processing(f_id)
                        content = client.get_content(f_id)
                        export_filename = f_name if f_name.lower().endswith(".md") else f"{f_name}.md"
                        (export_path / export_filename).write_text(content)
                        export_count += 1
                    except Exception as e:
                        log("ERROR", f"Failed to export {item['name']}: {e}")

                log("EXPORT", f"Exported {export_count} files.")

                if args.export_git and export_count > 0:
                    log("GIT", "Committing changes to export repository...")
                    subprocess.run(["git", "add", "-A", "."], cwd=export_path)
                    subprocess.run(["git", "commit", "-m", f"feat: updated exports ({export_count} files)"], cwd=export_path)

        log("FINISH", "Pipeline successfully completed.")

    except Exception as e:
        log("FATAL", str(e))
        exit(1)

if __name__ == "__main__":
    main()
