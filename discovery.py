import pathlib
import shutil
import json
import subprocess

def get_repo_root(path):
    """Finds the root of a git or svn repository."""
    current = pathlib.Path(path).expanduser().resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / ".svn").exists():
            return parent
    return None

def discover_files(source_path, keyword=None, target_dir=None):
    """
    Scans source_path for documents. 
    If target_dir is provided, copies files there and updates sync_manifest.json.
    Returns a list of dicts: {'original': Path, 'flattened': str, 'staged': Path or None}
    """
    source = pathlib.Path(source_path).expanduser().resolve()
    target = pathlib.Path(target_dir).expanduser().resolve() if target_dir else None
    
    # Identify Repo Root for enhanced flattening
    repo_root = get_repo_root(source)
    
    manifest = {}
    if target:
        target.mkdir(exist_ok=True, parents=True)
        manifest_path = target / "sync_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load manifest: {e}")

    results = []
    extensions = {'.doc', '.docx', '.pdf', '.md'}
    
    # 1. Discovery
    for path in source.rglob('*'):
        if path.is_file() and path.suffix.lower() in extensions:
            if not keyword or keyword.lower() in path.name.lower():
                try:
                    abs_file_path = path.resolve()
                    
                    # Calculate flattened name based on repo context or source folder
                    if repo_root and repo_root != abs_file_path:
                        # Path relative to the root of the repository
                        rel_path = abs_file_path.relative_to(repo_root)
                        path_parts = list(rel_path.parts)
                    else:
                        # Fallback to current source folder logic
                        rel_path = abs_file_path.relative_to(source)
                        path_parts = [source.name] + list(rel_path.parts)
                    
                    flattened_name = "_".join(path_parts)
                    
                    staged_path = None
                    if target:
                        staged_path = target / flattened_name
                        shutil.copy2(path, staged_path)
                        # Update manifest entry
                        if flattened_name not in manifest or not isinstance(manifest[flattened_name], dict):
                            manifest[flattened_name] = {}
                        manifest[flattened_name]["original_path"] = str(abs_file_path)
                    
                    results.append({
                        "original": abs_file_path,
                        "flattened": flattened_name,
                        "staged": staged_path
                    })
                except ValueError:
                    continue
    
    # 2. Deletion Check (only if staging)
    if target:
        to_delete = []
        for flattened_name, entry in manifest.items():
            original_path_str = entry["original_path"] if isinstance(entry, dict) else entry
            original_path = pathlib.Path(original_path_str)
            
            if str(original_path).startswith(str(source)):
                if not original_path.exists():
                    staged_file = target / flattened_name
                    if staged_file.exists():
                        print(f"Source deleted: {original_path_str}. Removing staged file: {flattened_name}")
                        staged_file.unlink()
                    to_delete.append(flattened_name)
        
        for key in to_delete:
            del manifest[key]
            
        with open(target / "sync_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
            
    return results
