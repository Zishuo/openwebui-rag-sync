import subprocess
import pathlib

def ensure_git_repo(target_path):
    """Ensures the directory exists and is a standalone git repository."""
    target_path = pathlib.Path(target_path).expanduser().resolve()
    target_path.mkdir(exist_ok=True, parents=True)
    
    # Check if this specific directory has a .git folder
    if not (target_path / ".git").exists():
        print(f"Initializing standalone Git tracking in {target_path}...")
        subprocess.run(["git", "init"], cwd=target_path, check=True)
    
    return target_path

def get_changed_files(target_dir="staged-docs"):
    target_path = ensure_git_repo(target_dir)
    
    # Stage all changes temporarily to identify them
    subprocess.run(["git", "add", "-A", "."], cwd=target_path, check=True)
    
    # Get list of staged files using porcelain for easier parsing of status
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target_path, capture_output=True, text=True, check=True
    )
    
    updated = []
    deleted = []
    
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        
        status = line[:2]
        file_path = line[3:].strip().strip('"') # Strip quotes if they exist
        
        # Explicitly ignore manifest
        if file_path == "sync_manifest.json":
            continue
            
        if status.startswith('D') or status.endswith('D'):
            deleted.append(file_path)
        else:
            updated.append(file_path)
    
    # Immediately unstage everything so we can stage them one-by-one in the orchestrator
    if updated or deleted:
        try:
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_path, check=True, capture_output=True)
            subprocess.run(["git", "reset"], cwd=target_path, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(["git", "rm", "-r", "--cached", "."], cwd=target_path, check=True, capture_output=True)
    
    return updated, deleted
