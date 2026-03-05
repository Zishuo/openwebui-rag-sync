import pathlib
import subprocess
import os
import shutil
import tempfile
from versioning import get_changed_files

def test_versioning():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_dir = pathlib.Path(tmp_dir) / "test-staged-docs"
        test_dir.mkdir(parents=True)
        
        # Create a new file
        test_file = test_dir / "new_file.md"
        test_file.write_text("content")
        
        # Verify it's detected
        updated, deleted = get_changed_files(str(test_dir))
        assert any("new_file.md" in f for f in updated)
        print("Initial detection passed!")

        # Commit it
        try:
            subprocess.run(["git", "add", "."], cwd=str(test_dir), check=True)
            subprocess.run(
                ["git", "commit", "-m", "test: initial commit of new_file.md"], 
                cwd=str(test_dir), check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            raise e

        # Modify it
        test_file.write_text("modified content")

        # Verify it's detected
        updated, deleted = get_changed_files(str(test_dir))
        assert any("new_file.md" in f for f in updated)
        print("Modification detection passed!")

        # Test Deletion
        subprocess.run(["git", "add", "."], cwd=str(test_dir), check=True)
        subprocess.run(["git", "commit", "-m", "test: commit modification"], cwd=str(test_dir), check=True)
        test_file.unlink()

        updated, deleted = get_changed_files(str(test_dir))
        assert any("new_file.md" in f for f in deleted)
        print("Deletion detection passed!")

        
        # Unstage for cleanup
        subprocess.run(["git", "restore", "--staged", "."], cwd=str(test_dir), check=True)

if __name__ == "__main__":
    test_versioning()
    print("Versioning test passed!")
