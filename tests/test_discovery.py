import pathlib
import shutil
import tempfile
import os
import json
from discovery import discover_files

def test_discovery():
    with tempfile.TemporaryDirectory() as tmp_source:
        source = pathlib.Path(tmp_source)
        source_dir_name = source.name
        
        # Create dummy files
        (source / "project_report.pdf").touch()
        (source / "notes.md").touch()
        (source / "meeting_notes.docx").touch()
        (source / "other.txt").touch()
        
        with tempfile.TemporaryDirectory() as tmp_target:
            # Discover files with keyword 'notes'
            found = discover_files(tmp_source, "notes", target_dir=tmp_target)
            
            assert len(found) == 2
            # found is list of {'original': Path, 'flattened': str, 'staged': Path}
            found_names = {f['flattened'] for f in found}
            
            assert f"{source_dir_name}_notes.md" in found_names
            assert f"{source_dir_name}_meeting_notes.docx" in found_names
            
            # Verify they were copied
            target = pathlib.Path(tmp_target)
            assert (target / f"{source_dir_name}_notes.md").exists()
            assert (target / f"{source_dir_name}_meeting_notes.docx").exists()
            
            # Verify manifest (New nested structure)
            manifest_path = target / "sync_manifest.json"
            assert manifest_path.exists()
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            
            # Find the local repo key
            repo_key = "local"
            assert repo_key in manifest["repositories"]
            repo_files = manifest["repositories"][repo_key]["files"]
            assert f"{source_dir_name}_notes.md" in repo_files
            assert repo_files[f"{source_dir_name}_notes.md"]["original_path"] == str((source / "notes.md").resolve())

def test_discovery_nested():
    with tempfile.TemporaryDirectory() as tmp_source:
        source = pathlib.Path(tmp_source)
        source_dir_name = source.name
        
        # Create nested structure
        (source / "subdir").mkdir()
        (source / "subdir" / "notes.md").touch()
        (source / "subdir" / "deep").mkdir()
        (source / "subdir" / "deep" / "notes.md").touch()
        (source / "notes.md").touch()
        
        with tempfile.TemporaryDirectory() as tmp_target:
            found = discover_files(tmp_source, target_dir=tmp_target)
            
            # Should find 3 notes.md files
            assert len(found) == 3
            found_names = {f['flattened'] for f in found}
            
            assert f"{source_dir_name}_notes.md" in found_names
            assert f"{source_dir_name}_subdir_notes.md" in found_names
            assert f"{source_dir_name}_subdir_deep_notes.md" in found_names

            # Verify files exist in target
            target = pathlib.Path(tmp_target)
            assert (target / f"{source_dir_name}_notes.md").exists()
            assert (target / f"{source_dir_name}_subdir_notes.md").exists()
            assert (target / f"{source_dir_name}_subdir_deep_notes.md").exists()

def test_discovery_deletion():
    with tempfile.TemporaryDirectory() as tmp_source:
        source = pathlib.Path(tmp_source)
        source_dir_name = source.name
        test_file = source / "to_delete.md"
        test_file.touch()
        
        with tempfile.TemporaryDirectory() as tmp_target:
            target = pathlib.Path(tmp_target)
            # 1. First scan
            discover_files(tmp_source, target_dir=tmp_target)
            staged_file = target / f"{source_dir_name}_to_delete.md"
            assert staged_file.exists()
            
            # 2. Delete source
            test_file.unlink()
            
            # 3. Second scan
            discover_files(tmp_source, target_dir=tmp_target)
            assert not staged_file.exists()
            
            # 4. Verify manifest cleanup
            with open(target / "sync_manifest.json", "r") as f:
                manifest = json.load(f)
            repo_files = manifest["repositories"]["local"]["files"]
            assert f"{source_dir_name}_to_delete.md" not in repo_files

def test_discovery_repo_aware():
    with tempfile.TemporaryDirectory() as tmp_root:
        root = pathlib.Path(tmp_root).resolve()
        # 1. Create a git-like structure
        (root / ".git").mkdir()
        (root / "project" / "docs").mkdir(parents=True)
        test_file = root / "project" / "docs" / "api.md"
        test_file.touch()
        test_file.write_text("content")
        
        # 2. Scan from a subpath
        source = root / "project" / "docs"
        
        with tempfile.TemporaryDirectory() as tmp_target:
            results = discover_files(str(source), target_dir=tmp_target)
            
            # 3. Verify naming
            # Expected name: <tmp_root_name>_project_docs_api.md
            root_name = root.name
            expected_name = f"{root_name}_project_docs_api.md"
            found_names = {r['flattened'] for r in results}
            assert expected_name in found_names
            assert (pathlib.Path(tmp_target) / expected_name).exists()
            
            # 4. Verify manifest remote (it should be None since we didn't add origin)
            with open(pathlib.Path(tmp_target) / "sync_manifest.json", "r") as f:
                manifest = json.load(f)
            
            # Use resolved string for key lookup
            assert manifest["repositories"][str(root)]["type"] == "git"
            assert manifest["repositories"][str(root)]["remote"] is None

if __name__ == "__main__":
    test_discovery()
    test_discovery_nested()
    test_discovery_deletion()
    test_discovery_repo_aware()
    print("Discovery tests passed!")
