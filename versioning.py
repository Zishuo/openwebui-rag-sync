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
    
    # Get list of staged files (new, modified, renamed)
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=target_path, capture_output=True, text=True, check=True
    )
    files = [line for line in result.stdout.splitlines() if line.strip()]
    
    # Immediately unstage everything so we can stage them one-by-one in the orchestrator
    if files:
        try:
            # Check if HEAD exists to determine the correct unstage command
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_path, check=True, capture_output=True)
            subprocess.run(["git", "reset"], cwd=target_path, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # No HEAD yet (new repo), use rm --cached
            subprocess.run(["git", "rm", "-r", "--cached", "."], cwd=target_path, check=True, capture_output=True)
    
    # Return relative paths (as strings)
    return files
