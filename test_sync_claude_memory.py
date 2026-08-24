import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("sync_claude_memory.py")


class SyncClaudeMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.claude_home = self.root / ".claude"
        self.codex_home = self.root / ".codex"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_project(self, cwd: str, memory: dict[str, str]) -> str:
        key = "".join(character if character.isalnum() else "-" for character in cwd)
        project = self.claude_home / "projects" / key
        memory_dir = project / "memory"
        memory_dir.mkdir(parents=True)
        (project / "sessions-index.json").write_text(
            json.dumps({"version": 1, "originalPath": cwd, "entries": []})
        )
        for relative, content in memory.items():
            path = memory_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return key

    def run_script(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--claude-home",
                str(self.claude_home),
                "--codex-home",
                str(self.codex_home),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def resource(self, key: str, relative: str) -> Path:
        return (
            self.codex_home
            / "memories/extensions/external_agent_import/resources"
            / key
            / relative
        )

    def claude_memory(self, key: str, relative: str) -> Path:
        return self.claude_home / "projects" / key / "memory" / relative

    def create_codex_registry(self, cwd: str) -> None:
        registry = self.codex_home / "memories/MEMORY.md"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            "# Task Group: Example workflow\n\n"
            "scope: Remember the example workflow.\n"
            f"applies_to: cwd={cwd}; reuse_rule=Use it in this checkout.\n\n"
            "## Reusable knowledge\n\n"
            "- Run `example --check` before publishing.\n\n"
            "# Task Group: Global memory\n\n"
            "scope: This block has no project path.\n"
        )

    def test_syncs_memory_and_scope(self) -> None:
        cwd = "/work/example.project"
        key = self.create_project(
            cwd,
            {"MEMORY.md": "# Index\n", "details/topic.md": "# Topic\n"},
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.resource(key, "MEMORY.md").read_text(), "# Index\n")
        self.assertEqual(
            self.resource(key, "details/topic.md").read_text(), "# Topic\n"
        )
        self.assertEqual(
            json.loads(self.resource(key, "scope.json").read_text()), {"cwd": cwd}
        )

    def test_dry_run_does_not_write(self) -> None:
        self.create_project("/work/example", {"MEMORY.md": "# Index\n"})

        result = self.run_script("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would sync 1 project(s)", result.stdout)
        self.assertFalse(self.codex_home.exists())

    def test_delete_removes_only_manifest_owned_stale_files(self) -> None:
        key = self.create_project(
            "/work/example",
            {"MEMORY.md": "# Index\n", "stale.md": "# Stale\n"},
        )
        self.assertEqual(self.run_script().returncode, 0)
        unrelated = self.resource("unrelated", "keep.md")
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("keep")
        (self.claude_home / "projects" / key / "memory/stale.md").unlink()

        result = self.run_script("--delete")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.resource(key, "stale.md").exists())
        self.assertEqual(unrelated.read_text(), "keep")

    def test_filtered_sync_preserves_other_project_manifest_entries(self) -> None:
        first = self.create_project("/work/first", {"MEMORY.md": "first\n"})
        second = self.create_project("/work/second", {"MEMORY.md": "second\n"})
        self.assertEqual(self.run_script().returncode, 0)
        (self.claude_home / "projects" / second / "memory/MEMORY.md").unlink()

        result = self.run_script("--project", "/work/first", "--delete")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.resource(first, "MEMORY.md").exists())
        self.assertTrue(self.resource(second, "MEMORY.md").exists())
        manifest = json.loads(
            (
                self.codex_home
                / "memories/extensions/external_agent_import"
                / ".sync-claude-memory.json"
            ).read_text()
        )
        self.assertIn(f"{second}/MEMORY.md", manifest["files"])

    def test_delete_preserves_project_when_scope_becomes_unresolvable(self) -> None:
        key = self.create_project("/work/example", {"MEMORY.md": "memory\n"})
        self.assertEqual(self.run_script().returncode, 0)
        (self.claude_home / "projects" / key / "sessions-index.json").unlink()

        result = self.run_script("--delete")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cannot determine cwd", result.stderr)
        self.assertTrue(self.resource(key, "MEMORY.md").exists())

    def test_reverse_sync_exports_scoped_codex_memory(self) -> None:
        cwd = "/work/example"
        key = self.create_project(cwd, {"MEMORY.md": "# Existing Memory\n"})
        self.create_codex_registry(cwd)

        result = self.run_script("--direction", "codex-to-claude")

        self.assertEqual(result.returncode, 0, result.stderr)
        generated = self.claude_memory(key, "codex-memory.md").read_text()
        self.assertTrue(generated.startswith("# Codex Memory\n"))
        self.assertIn("## Task Group: Example workflow", generated)
        self.assertNotIn("Global memory", generated)
        index = self.claude_memory(key, "MEMORY.md").read_text()
        self.assertIn("[Codex memory](codex-memory.md)", index)

    def test_forward_sync_does_not_echo_reverse_sync_content(self) -> None:
        cwd = "/work/example"
        key = self.create_project(cwd, {"MEMORY.md": "# Existing Memory\n"})
        self.create_codex_registry(cwd)
        self.assertEqual(
            self.run_script("--direction", "codex-to-claude").returncode, 0
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        imported_index = self.resource(key, "MEMORY.md").read_text()
        self.assertEqual(imported_index, "# Existing Memory\n")
        imported_generated = (
            self.codex_home
            / "memories/extensions/external_agent_import/resources"
            / key
            / "codex-memory.md"
        )
        self.assertFalse(imported_generated.exists())

    def test_reverse_delete_removes_only_generated_memory(self) -> None:
        cwd = "/work/example"
        key = self.create_project(cwd, {"MEMORY.md": "# Existing Memory\n"})
        self.create_codex_registry(cwd)
        self.assertEqual(
            self.run_script("--direction", "codex-to-claude").returncode, 0
        )
        self.create_codex_registry("/work/other")

        result = self.run_script("--direction", "codex-to-claude", "--delete")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.claude_memory(key, "codex-memory.md").exists())
        index = self.claude_memory(key, "MEMORY.md").read_text()
        self.assertEqual(index, "# Existing Memory\n")

    def test_reverse_sync_refuses_non_owned_target(self) -> None:
        cwd = "/work/example"
        key = self.create_project(
            cwd,
            {
                "MEMORY.md": "# Existing Memory\n",
                "codex-memory.md": "# Handwritten Codex Notes\n",
            },
        )
        self.create_codex_registry(cwd)

        result = self.run_script("--direction", "codex-to-claude")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to overwrite non-tool-owned", result.stderr)
        self.assertEqual(
            self.claude_memory(key, "codex-memory.md").read_text(),
            "# Handwritten Codex Notes\n",
        )


if __name__ == "__main__":
    unittest.main()
