# Sync Claude Memory

This standalone Python tool copies Claude Code's per-project Markdown memory into Codex CLI's native external-agent import extension. Codex can then consolidate those resources into its searchable `MEMORY.md` registry and compact `memory_summary.md` index.

## Requirements

- `uv`
- Python 3.13 or newer, installed automatically by `uv` when needed
- Claude Code project data under `~/.claude/projects`
- A Codex CLI version with native memories enabled

The script has no third-party Python dependencies.

## Usage

Preview all changes:

```console
./sync_claude_memory.py --dry-run
```

Sync all discoverable project memories:

```console
./sync_claude_memory.py
```

Sync one project by its working directory:

```console
./sync_claude_memory.py --project /path/to/project
```

Delete resources that this tool synced previously but that no longer exist in Claude:

```console
./sync_claude_memory.py --delete
```

Use `--verbose` to print every file operation. Alternate data directories can be supplied with `--claude-home` and `--codex-home`.

## How discovery works

Claude stores memory files under `~/.claude/projects/<project-key>/memory/`. The tool resolves each key back to its working directory from the durable per-project `sessions-index.json`. It also checks `~/.claude/sessions`, Claude history and configuration, and local transcript metadata as fallbacks.

Projects whose working directory cannot be resolved are reported and skipped because Codex requires an explicit `cwd` scope. Files are copied byte-for-byte and never interpreted or executed by this tool.

## Codex destination

The generated structure follows Codex's native import convention:

```text
~/.codex/memories/extensions/external_agent_import/
├── instructions.md
└── resources/
    └── <project-key>/
        ├── scope.json
        ├── MEMORY.md
        └── <topic>.md
```

The manifest `.sync-claude-memory.json` records only files owned by this tool. The `--delete` option removes stale files only when they appear in that manifest; unrelated resources are left untouched.

## Caveats

- This is a one-way sync. The tool does not copy Codex memories back to Claude or modify Claude's source files.
- Codex consolidates imported resources asynchronously. The files are available in the native extension immediately, but normal lookup through Codex's `MEMORY.md` registry may not find them until a background memory consolidation run finishes.
- Codex does not currently expose a CLI command to force consolidation. Starting Codex allows its memory jobs to run, subject to its normal scheduling and rate limits.
- The external-agent import layout is an internal Codex format verified with Codex CLI 0.149.1. A later Codex release may change it.
- A Claude project is skipped when its working directory cannot be recovered. Codex needs this path to keep imported memory scoped to the correct project.
- The script copies memory locally and does not make network requests. Codex may send imported content to its configured model provider when it consolidates or uses that memory.

Run with `--dry-run` before the first sync to review the destination paths and the number of files that would be copied.

## License

This project is available under the [MIT License](LICENSE).
