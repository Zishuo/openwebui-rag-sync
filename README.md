# OpenWebUI RAG Sync Pipeline

**An automated document synchronization pipeline for OpenWebUI RAG (Retrieval-Augmented Generation). It handles recursive discovery, Git-based change tracking, and Markdown digest retrieval.**

This project implements an automated pipeline for synchronizing documents with OpenWebUI's RAG system. It automates file discovery, change tracking via Git, and API-driven knowledge base updates.

The pipeline's primary goal is to maintain a local mirror of processed document digests while ensuring only new or modified files are uploaded to OpenWebUI to minimize API overhead and redundancy.

## 🚀 Quick Start

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/zishuo/openwebui-rag-sync.git
    cd openwebui-rag-sync
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment:**
    Copy `.env.example` to `.env` and fill in your OpenWebUI API details:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and set:
    - `OPENWEBUI_BASE_URL`: Your OpenWebUI instance URL (e.g., `https://chat.domain.com`).
    - `OPENWEBUI_API_KEY`: Found in **Settings > Account** in OpenWebUI.

4.  **Run a Sync:**
    ```bash
    python3 sync.py -p ~/MyDocuments -kb-name "MyKnowledgeBase"
    ```

## 🏗 Core Architecture

- **Phase 1: Discovery:** Recursively scans a source path for documents (`.pdf`, `.md`, `.doc`, `.docx`). Filenames are flattened to prevent collisions (e.g., `source_subdir_file.md`).
- **Phase 2: Upload:** Uses Git-based change detection in the tracking directory to identify new or modified files, uploads them to OpenWebUI, and links them to a Knowledge Base.
- **Phase 3: Download:** Retrieves parsed Markdown digests from the OpenWebUI API.

## ⚙️ Environment & Configuration

### Prerequisites
- **Runtime:** Python 3.9+
- **Version Control:** Git (installed and available in PATH).
- **Dependencies:** `requests`, `python-dotenv`.

### Required Environment Variables
- `OPENWEBUI_API_KEY`: Authentication key for the OpenWebUI instance.
- `OPENWEBUI_BASE_URL`: Base URL of the OpenWebUI API.

## 🛠 Usage Guidelines

The script performs actions based on the provided parameters. You can combine them for a full sync or use them individually for specific tasks.

### Command Line Options
- `--path`, `-p`: (Optional) Source directory to scan. Triggers **Discovery** into the staging directory.
- `--staged-dir`, `-s`: (Optional) Tracking directory for raw files. Triggers **Upload** of new/modified files.
- `--digest-dir`, `-d`: (Optional) Destination for digests. Triggers **Download**.
- `--keyword`: (Optional) Filter discovered files by name.
- `--kb-id` / `--kb-name`: (Required) Target Knowledge Base identification.
- `--digest-git`: (Optional) Enable Git version control for the digest directory (disabled by default).

### Example Scenarios

#### 1. Full Synchronization
Scan a folder, upload changes, and download new digests.
```bash
python3 sync.py -p ~/Docs -s ~/staged -d ~/digests --kb-name "MyKB"
```

#### 2. Standalone Upload
Upload and link any files currently sitting in your tracking directory.
```bash
python3 sync.py -s ~/staged --kb-name "MyKB"
```

#### 3. Standalone Download
Download all parsed Markdown digests for an entire Knowledge Base.
```bash
python3 sync.py -d ~/digests --kb-name "MyKB"
```

#### 4. Automatic Discovery (Default Paths)
If you omit directories, the script uses `staged-docs/` and `digest-docs/` by default.
```bash
python3 sync.py -p ~/Documents --kb-name "MyKB"
```

## 📜 Development Conventions
- **Compositional Logic:** Actions (Discover, Upload, Download) are independent and triggered by their respective CLI arguments.
- **Flattened Paths:** Files are staged using underscores to join path segments, preventing name collisions across multiple source directories.
- **Duplicate Detection:** Identical content is recognized as a "Soft Success" to prevent infinite retries.
- **Error Logging:** Failures are recorded in `sync_failures.log` and committed to history.
