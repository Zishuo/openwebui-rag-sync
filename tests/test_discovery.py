import pathlib
import shutil
import tempfile
import os
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
            found_names = {f.name for f in found}
            
            assert f"{source_dir_name}_notes.md" in found_names
            assert f"{source_dir_name}_meeting_notes.docx" in found_names
            
            # Verify they were copied
            target = pathlib.Path(tmp_target)
            assert (target / f"{source_dir_name}_notes.md").exists()
            assert (target / f"{source_dir_name}_meeting_notes.docx").exists()

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
            found_names = {f.name for f in found}
            
            # Root notes.md should be 'source_notes.md'
            assert f"{source_dir_name}_notes.md" in found_names
            # Subdir notes.md should be 'source_subdir_notes.md'
            assert f"{source_dir_name}_subdir_notes.md" in found_names
            # Deep notes.md should be 'source_subdir_deep_notes.md'
            assert f"{source_dir_name}_subdir_deep_notes.md" in found_names

            # Verify files exist in target
            target = pathlib.Path(tmp_target)
            assert (target / f"{source_dir_name}_notes.md").exists()
            assert (target / f"{source_dir_name}_subdir_notes.md").exists()
            assert (target / f"{source_dir_name}_subdir_deep_notes.md").exists()

if __name__ == "__main__":
    test_discovery()
    test_discovery_nested()
    print("Discovery tests passed!")
