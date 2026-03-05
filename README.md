# OpenWebUI RAG Sync Pipeline

**An automated document synchronization pipeline for OpenWebUI RAG (Retrieval-Augmented Generation). It handles recursive discovery, Git-based change tracking, and Markdown export retrieval.**

This project implements an automated pipeline for synchronizing documents with OpenWebUI's RAG system. It automates file discovery, change tracking via Git, and API-driven knowledge base updates.

## 🚀 Quick Start

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Environment:**
    Copy `.env.example` to `.env` and fill in your OpenWebUI URL and API key.

## 🏗 Core Architecture

- **Discovery:** Recursively scans a source path. Filenames are flattened to prevent collisions.
- **Tracking (Optional):** If `--staged-dir` is used, files are mirrored locally in a Git repository. `sync_manifest.json` tracks original paths to detect deletions in the source.
- **RAG Sync (Optional):** If a Knowledge Base is provided, the script handles uploads, KB linking, and duplicate content detection.
- **Persistence:** Commits successful syncs to the local tracking repository and logs failures to `sync_failures.log`.

## 🛠 Usage Combinations

The script is compositional. Providing a specific parameter "opts-in" to that phase of the pipeline.

### 1. Discovery & Staging (Local Only)
| Combination | Command | Result |
| :--- | :--- | :--- |
| **Discovery Only** | `python3 sync.py -p ~/Docs` | Scans source and reports found documents. No files moved. |
| **Local Mirror** | `python3 sync.py -p ~/Docs -s ./staged` | Scans source, copies files to `./staged`, tracks changes via Git/Manifest. |

### 2. Direct Sync (Stateless / No Local Mirror)
| Combination | Command | Result |
| :--- | :--- | :--- |
| **Direct Upload** | `python3 sync.py -p ~/Docs --kb-name "MyKB"` | Uploads files directly from source to OpenWebUI. No local files created. |
| **Direct Full Sync** | `python3 sync.py -p ~/Docs -e ./export --kb-name "MyKB"` | Uploads from source and downloads parsed Markdown to `./export`. |

### 3. Tracked Sync (Stateful / Git Enabled)
| Combination | Command | Result |
| :--- | :--- | :--- |
| **Tracked Upload** | `python3 sync.py -p ~/Docs -s ./staged --kb-name "MyKB"` | Mirrors files to `./staged`. Only uploads new/modified files. |
| **Full Tracked Sync** | `python3 sync.py -p ~/Docs -s ./staged -e ./export --kb-name "MyKB"` | Full pipeline: Discovery $\rightarrow$ Staging $\rightarrow$ Upload $\rightarrow$ Export. |

### 4. Standalone Operations
| Combination | Command | Result |
| :--- | :--- | :--- |
| **Upload Existing** | `python3 sync.py -s ./staged --kb-name "MyKB"` | Checks `./staged` for changes and uploads them. No new discovery. |
| **Download KB** | `python3 sync.py -e ./export --kb-name "MyKB"` | Standalone export: Fetches all files from KB and saves to `./export`. |

## ⚙️ Command Line Options

- `-p`, `--path`: Source directory to scan. Triggers **Discovery**.
- `-s`, `--staged-dir`: Directory to mirror raw files. Triggers **Stateful Tracking** (Git + Manifest).
- `-e`, `--export-dir`: Directory for Markdown exports. Triggers **Export**.
- `--kb-name` / `--kb-id`: Target Knowledge Base. Required for any OpenWebUI interaction.
- `--keyword`: Optional string to filter filenames during discovery.
- `--force`: Force upload all files, ignoring Git change tracking.
- `--export-git`: Enable Git version control for the export directory (default: off).
- `--insecure`: Skip SSL certificate verification (useful for self-signed certificates).

## 📜 Development Conventions
- **Flattened Paths:** Files are staged using underscores (e.g., `src_subdir_file.md`) to prevent collisions.
- **Deletion Tracking:** Source deletions are detected via manifest and mirrored in tracking repos.
- **Soft Success:** Content duplicates are recorded in Git/Manifest but skip redundant API processing.
- **Error Logging:** Failures are recorded in `sync_failures.log` within the staging directory.
