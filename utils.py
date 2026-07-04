import os
import shutil
import zipfile

TEMP_DIR = "temp_edit"

def ensure_temp_directory():
    """Guarantees isolated sandbox directories exist before running files."""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def clear_user_cache(user_id: int):
    """Safely cleans up stale files belonging to a specific session."""
    if not os.path.exists(TEMP_DIR):
        return
    for filename in os.listdir(TEMP_DIR):
        if filename.startswith(f"img_{user_id}_") or filename.startswith(f"batch_{user_id}_"):
            try:
                os.remove(os.path.join(TEMP_DIR, filename))
            except Exception:
                pass

def create_batch_zip(user_id: int, processed_files: list) -> str:
    """Bundles multiple files into a single ZIP archive for fast downloading."""
    ensure_temp_directory()
    zip_path = os.path.join(TEMP_DIR, f"batch_{user_id}_archive.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in processed_files:
            if os.path.exists(file):
                zipf.write(file, os.path.basename(file))
    return zip_path

