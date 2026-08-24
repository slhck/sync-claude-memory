# Sync Claude Memory

This standalone Python tool syncs project memory between Claude Code and Codex CLI. The default direction copies Claude's Markdown memory into Codex's native external-agent import extension. The reverse direction exports consolidated, project-scoped Codex memory back to Claude.

## Requirements

- `uv`
- Python 3.11 or newer, installed automatically by `uv` when needed
- Claude Code project data under `~/.claude/projects`
- A Codex CLI version with native memories enabled
- `ssh` and `scp` for remote transfers

The script has no third-party Python dependencies.

## Claude to Codex

Preview all changes:

```console
./sync_claude_memory.py --dry-run
```

Sync all discoverable Claude project memories to Codex:

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

## Codex to Claude

Preview the reverse sync:

```console
./sync_claude_memory.py --direction codex-to-claude --dry-run
```

Export consolidated Codex memory to existing Claude projects:

```console
./sync_claude_memory.py --direction codex-to-claude
```

Export one project:

```console
./sync_claude_memory.py \
  --direction codex-to-claude \
  --project /path/to/project
```

Codex may contain scoped memory for a project that Claude has never opened. Use `--create-projects` to create the missing Claude project directories:

```console
./sync_claude_memory.py \
  --direction codex-to-claude \
  --create-projects
```

Use `--delete` to remove stale files owned by the selected sync direction. Use `--verbose` to print every file operation. Alternate data directories can be supplied with `--claude-home` and `--codex-home`.

## Remote sync

Use `--source-ssh` when the source memory is on another machine. The destination remains local.

Copy Claude memory from an old machine into local Codex:

```console
./sync_claude_memory.py --source-ssh user@old-host
```

Copy Codex memory from another machine into local Claude:

```console
./sync_claude_memory.py \
  --direction codex-to-claude \
  --source-ssh user@old-host
```

Use `--target-ssh` when the source memory is local and the destination is on another machine.

Copy local Claude memory into Codex on a new machine:

```console
./sync_claude_memory.py --target-ssh user@new-host
```

Copy local Codex memory into Claude on a new machine:

```console
./sync_claude_memory.py \
  --direction codex-to-claude \
  --target-ssh user@new-host
```

Add `--ssh-port PORT` for a non-default SSH port. Remote sync uses non-interactive SSH authentication, so key-based login must already work. When the tool executes remotely, it uses `uv` if available and otherwise falls back to Python 3.11 or newer.

The tool uploads itself and a minimal source snapshot to a randomly named directory under remote `/tmp`. It removes that staging directory after the run. Remote source mode reads the source stores and writes only to temporary staging. Remote target mode writes to the selected remote memory store.

Project `cwd` scopes are preserved exactly. Remote transfer therefore assumes that project checkouts use the same absolute paths on both machines. A memory entry remains available under its original scope when the path does not exist on the destination, but Codex or Claude may not associate it with a differently located checkout.

## How discovery works

Claude stores memory files under `~/.claude/projects/<project-key>/memory/`. The tool resolves each key back to its working directory from the durable per-project `sessions-index.json`. It also checks `~/.claude/sessions`, Claude history and configuration, and local transcript metadata as fallbacks.

Projects whose working directory cannot be resolved are reported and skipped because Codex requires an explicit `cwd` scope. Source memory is copied without interpreting or executing its contents.

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

## Claude destination

The reverse sync reads task groups from Codex's consolidated `~/.codex/memories/MEMORY.md`. A task group must contain an explicit `applies_to: cwd=...` field. The tool groups matching task entries by working directory and writes:

```text
~/.claude/projects/<project-key>/memory/
├── MEMORY.md
└── codex-memory.md
```

The tool adds a managed link to `codex-memory.md` in Claude's existing `MEMORY.md`. It does not replace Claude's own index entries. The generated file and link are excluded from forward sync so the same memory does not loop back into Codex.

The reverse manifest `~/.claude/.sync-codex-memory.json` records generated projects. Reverse sync refuses to overwrite a `codex-memory.md` file that it did not create.

## Caveats

- Each direction is a managed export, not a conflict-resolving two-way merge. Run one direction at a time and review changes with `--dry-run`.
- Codex consolidates imported resources asynchronously. The files are available in the native extension immediately, but normal lookup through Codex's `MEMORY.md` registry may not find them until a background memory consolidation run finishes.
- Codex does not currently expose a CLI command to force consolidation. Starting Codex allows its memory jobs to run, subject to its normal scheduling and rate limits.
- The external-agent import layout is an internal Codex format verified with Codex CLI 0.149.1. A later Codex release may change it.
- A Claude project is skipped when its working directory cannot be recovered. Codex needs this path to keep imported memory scoped to the correct project.
- Reverse sync exports only consolidated task groups with an explicit project path. It does not export global profile data, unscoped memory, raw rollout summaries, or pending extension resources.
- Remote sync transfers memory through SSH/SCP and temporarily stores the transferred subset under `/tmp`. It does not support password prompts or interactive SSH challenges.
- Apart from requested SSH/SCP transfers, the script does not contact network services. Codex may send imported content to its configured model provider when it consolidates or uses that memory.

Run with `--dry-run` before the first sync to review the destination paths and the number of files that would be copied.

## License

This project is available under the [MIT License](LICENSE).
