import pathlib
import shutil

def discover_files(source_path, keyword=None, target_dir="staged-docs"):
    target = pathlib.Path(target_dir).expanduser()
    target.mkdir(exist_ok=True, parents=True)
    
    found_files = []
    source = pathlib.Path(source_path).expanduser().resolve()
    
    # Supported extensions
    extensions = {'.doc', '.docx', '.pdf', '.md'}
    
    for path in source.rglob('*'):
        if path.is_file() and path.suffix.lower() in extensions:
            if not keyword or keyword.lower() in path.name.lower():
                # Calculate relative path from source to current file
                # Use resolve() on path to ensure it's absolute before relative_to
                try:
                    rel_path = path.resolve().relative_to(source)
                    # Prepend source directory name and flatten parts by joining with underscores
                    path_parts = [source.name] + list(rel_path.parts)
                    flattened_name = "_".join(path_parts)
                except ValueError:
                    # Fallback to name if path is not relative to source (unlikely with rglob)
                    flattened_name = path.name
                    
                dest = target / flattened_name
                shutil.copy2(path, dest)
                found_files.append(dest)
            
    return found_files
