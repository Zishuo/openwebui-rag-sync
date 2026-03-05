import pathlib
import shutil
import json
import subprocess
from utils import log

def get_repo_info(path):
    """Finds the root, type, and remote URL of a git or svn repository."""
    current = pathlib.Path(path).expanduser().resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            remote_url = None
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=parent, capture_output=True, text=True
                )
                if result.returncode == 0:
                    remote_url = result.stdout.strip()
            except Exception:
                pass
            return parent, "git", remote_url
            
        if (parent / ".svn").exists():
            remote_url = None
            try:
                result = subprocess.run(
                    ["svn", "info", "--show-item", "url"],
                    cwd=parent, capture_output=True, text=True
                )
                if result.returncode == 0:
                    remote_url = result.stdout.strip()
            except Exception:
                pass
            return parent, "svn", remote_url
            
    return None, None, None

def discover_files(source_path, keyword=None, target_dir=None):
    """
    Scans source_path for documents. 
    Groups files by repository in sync_manifest.json.
    """
    source = pathlib.Path(source_path).expanduser().resolve()
    target = pathlib.Path(target_dir).expanduser().resolve() if target_dir else None
    
    repo_root, repo_type, repo_remote = get_repo_info(source)
    
    manifest = {"repositories": {}}
    if target:
        target.mkdir(exist_ok=True, parents=True)
        manifest_path = target / "sync_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    data = json.load(f)
                    # Migration logic from flat to nested
                    if "repositories" not in data:
                        log("CONFIG", "Migrating flat manifest to repository-grouped format...")
                        for fname, entry in data.items():
                            if isinstance(entry, dict) and "original_path" in entry:
                                orig = pathlib.Path(entry["original_path"])
                                r_root, r_type, r_remote = get_repo_info(orig)
                                r_key = str(r_root) if r_root else "local"
                                if r_key not in manifest["repositories"]:
                                    manifest["repositories"][r_key] = {"type": r_type or "local", "remote": r_remote, "files": {}}
                                manifest["repositories"][r_key]["files"][fname] = entry
                    else:
                        manifest = data
            except Exception as e:
                log("ERROR", f"Failed to load manifest: {e}")

    results = []
    extensions = {'.doc', '.docx', '.pdf', '.md'}
    
    # 1. Discovery
    for path in source.rglob('*'):
        if path.is_file() and path.suffix.lower() in extensions:
            # Skip hidden system directories (like .git, .svn)
            rel_parts = list(path.relative_to(source).parts)
            if ".git" in rel_parts or ".svn" in rel_parts:
                continue
            if path.name == ".DS_Store":
                continue
                
            if not keyword or keyword.lower() in path.name.lower():
                try:
                    # Skip empty files
                    if path.stat().st_size == 0:
                        continue
                        
                    abs_file_path = path.resolve()
                    
                    if repo_root:
                        rel_path = abs_file_path.relative_to(repo_root)
                        path_parts = [repo_root.name] + list(rel_path.parts)
                        repo_key = str(repo_root)
                        current_repo_type = repo_type
                        current_repo_remote = repo_remote
                    else:
                        rel_path = abs_file_path.relative_to(source)
                        path_parts = [source.name] + list(rel_path.parts)
                        repo_key = "local"
                        current_repo_type = "local"
                        current_repo_remote = None
                    
                    flattened_name = "_".join(path_parts)
                    
                    staged_path = None
                    if target:
                        staged_path = target / flattened_name
                        shutil.copy2(path, staged_path)
                        
                        # Update manifest entry
                        if repo_key not in manifest["repositories"]:
                            manifest["repositories"][repo_key] = {"type": current_repo_type, "remote": current_repo_remote, "files": {}}
                        
                        # Update remote URL if it was missing or changed
                        manifest["repositories"][repo_key]["remote"] = current_repo_remote
                        
                        repo_files = manifest["repositories"][repo_key]["files"]
                        if flattened_name not in repo_files:
                            repo_files[flattened_name] = {}
                        
                        repo_files[flattened_name]["original_path"] = str(abs_file_path)
                    
                    results.append({
                        "original": abs_file_path,
                        "flattened": flattened_name,
                        "staged": staged_path
                    })
                except ValueError:
                    continue
    
    # 2. Deletion Check
    if target:
        for r_path, r_data in manifest["repositories"].items():
            to_delete = []
            files = r_data.get("files", {})
            for fname, entry in files.items():
                orig_path = pathlib.Path(entry["original_path"])
                # Only check deletions for files within the current scan path
                if str(orig_path).startswith(str(source)):
                    is_gone = not orig_path.exists()
                    is_empty = False
                    if not is_gone:
                        try:
                            is_empty = orig_path.stat().st_size == 0
                        except Exception:
                            is_gone = True
                            
                    if is_gone or is_empty:
                        reason = "deleted" if is_gone else "empty"
                        staged_file = target / fname
                        if staged_file.exists():
                            log("CLEANUP", f"Source {reason}: {orig_path.name}. Removing staged file: {fname}")
                            staged_file.unlink()
                        to_delete.append(fname)
            
            for key in to_delete:
                del files[key]
        
        with open(target / "sync_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
            
    return results
