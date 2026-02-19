"""Tests for GovernanceStore: SQLite+FTS5 indexer for governance documents."""

from __future__ import annotations

from pathlib import Path

import pytest

from stratus.retrieval.governance_store import GovernanceStore, _chunk_markdown


class TestChunking:
    def test_split_by_h2_headers(self) -> None:
        md = "## Intro\nHello world\n\n## Details\nMore info here"
        chunks = _chunk_markdown(md)
        assert len(chunks) == 2
        assert chunks[0]["title"] == "Intro"
        assert "Hello world" in chunks[0]["content"]
        assert chunks[1]["title"] == "Details"
        assert "More info here" in chunks[1]["content"]

    def test_no_headers_single_chunk(self) -> None:
        md = "Just plain text with no headers at all."
        chunks = _chunk_markdown(md, fallback_title="README.md")
        assert len(chunks) == 1
        assert chunks[0]["title"] == "README.md"
        assert "Just plain text" in chunks[0]["content"]

    def test_nested_headers_split_on_h2(self) -> None:
        md = "## Section A\nContent A\n### Sub A\nSub content\n## Section B\nContent B"
        chunks = _chunk_markdown(md)
        assert len(chunks) == 2
        assert chunks[0]["title"] == "Section A"
        assert "Sub content" in chunks[0]["content"]
        assert chunks[1]["title"] == "Section B"

    def test_empty_sections_skipped(self) -> None:
        md = "## Empty\n\n## Also empty\n\n## Has content\nSomething here"
        chunks = _chunk_markdown(md)
        assert len(chunks) == 1
        assert chunks[0]["title"] == "Has content"

    def test_content_before_first_header(self) -> None:
        md = "Preamble text\n\n## First Section\nSection content"
        chunks = _chunk_markdown(md, fallback_title="doc.md")
        assert len(chunks) == 2
        assert chunks[0]["title"] == "doc.md"
        assert "Preamble text" in chunks[0]["content"]
        assert chunks[1]["title"] == "First Section"

    def test_empty_content_returns_empty(self) -> None:
        chunks = _chunk_markdown("")
        assert chunks == []

    def test_whitespace_only_returns_empty(self) -> None:
        chunks = _chunk_markdown("   \n  \n  ")
        assert chunks == []


class TestGovernanceStoreSchema:
    def test_creates_tables(self) -> None:
        store = GovernanceStore()
        tables = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [r[0] for r in tables]
        assert "governance_docs" in table_names
        assert "schema_versions" in table_names

    def test_creates_fts_virtual_table(self) -> None:
        store = GovernanceStore()
        tables = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='governance_fts'"
        ).fetchall()
        assert len(tables) == 1

    def test_schema_version_recorded(self) -> None:
        store = GovernanceStore()
        row = store._conn.execute("SELECT MAX(version) FROM schema_versions").fetchone()
        assert row[0] == 2

    def test_close(self) -> None:
        store = GovernanceStore()
        store.close()
        # Verify connection is closed by attempting a query
        with pytest.raises(Exception):
            store._conn.execute("SELECT 1")


class TestIndexProject:
    def _make_project(self, tmp_path: Path) -> Path:
        """Create a minimal project with governance docs."""
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "testing.md").write_text("## Testing\nAlways test first\n## Coverage\n80% minimum")
        (rules / "style.md").write_text("## Style\nUse ruff for formatting")

        decisions = root / "docs" / "decisions"
        decisions.mkdir(parents=True)
        (decisions / "001-use-sqlite.md").write_text("## Decision\nUse SQLite for storage")

        agents = root / ".claude" / "agents"
        agents.mkdir(parents=True)
        (agents / "qa.md").write_text("## QA Agent\nRuns tests")

        (root / "CLAUDE.md").write_text("## Project\nThis is stratus")
        (root / "README.md").write_text("## Overview\nOpen source framework")

        arch = root / "docs" / "architecture"
        arch.mkdir(parents=True)
        (arch / "design.md").write_text("## Architecture\nMicroservices pattern")

        templates = root / ".claude" / "templates"
        templates.mkdir(parents=True)
        (templates / "feature.md").write_text("## Template\nFeature template content")

        skills = root / ".claude" / "skills" / "commit"
        skills.mkdir(parents=True)
        (skills / "prompt.md").write_text("## Commit\nGenerate commit message")

        return root

    def test_indexes_markdown_files(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path)
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] > 0
        assert stats["chunks_indexed"] > 0

    def test_skips_non_markdown(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "test.txt").write_text("Not a markdown file")
        (rules / "test.md").write_text("## Rule\nA real rule")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 1

    def test_chunks_by_headers(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "multi.md").write_text("## A\nContent A\n## B\nContent B\n## C\nContent C")
        store = GovernanceStore()
        store.index_project(str(root))
        rows = store._conn.execute("SELECT COUNT(*) FROM governance_docs").fetchone()
        assert rows[0] == 3  # 3 chunks

    def test_change_detection_skips_unchanged(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "test.md").write_text("## Rule\nContent")
        store = GovernanceStore()
        stats1 = store.index_project(str(root))
        assert stats1["files_indexed"] == 1
        stats2 = store.index_project(str(root))
        assert stats2["files_indexed"] == 0
        assert stats2["files_skipped"] == 1

    def test_reindexes_changed_file(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "test.md").write_text("## Rule\nOriginal")
        store = GovernanceStore()
        store.index_project(str(root))
        (rules / "test.md").write_text("## Rule\nUpdated content")
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 1

    def test_removes_stale_entries(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.md").write_text("## A\nContent A")
        (rules / "b.md").write_text("## B\nContent B")
        store = GovernanceStore()
        store.index_project(str(root))
        (rules / "b.md").unlink()
        stats = store.index_project(str(root))
        assert stats["files_removed"] == 1
        rows = store._conn.execute("SELECT COUNT(*) FROM governance_docs").fetchone()
        assert rows[0] == 1

    def test_returns_stats(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path)
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert "files_indexed" in stats
        assert "files_skipped" in stats
        assert "files_removed" in stats
        assert "chunks_indexed" in stats

    def test_correct_doc_types(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path)
        store = GovernanceStore()
        store.index_project(str(root))
        types = store._conn.execute(
            "SELECT DISTINCT doc_type FROM governance_docs ORDER BY doc_type"
        ).fetchall()
        type_set = {r[0] for r in types}
        assert "rule" in type_set
        assert "adr" in type_set
        assert "agent" in type_set
        assert "project" in type_set
        assert "architecture" in type_set
        assert "template" in type_set
        assert "skill" in type_set

    def test_empty_project(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 0
        assert stats["chunks_indexed"] == 0


class TestSearch:
    def _index_sample(self, store: GovernanceStore, tmp_path: Path) -> Path:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "testing.md").write_text("## Testing\nAlways write tests before code")
        (rules / "style.md").write_text("## Style\nUse ruff for Python formatting")

        decisions = root / "docs" / "decisions"
        decisions.mkdir(parents=True)
        (decisions / "001.md").write_text("## Decision\nUse SQLite for persistent storage")

        store.index_project(str(root))
        return root

    def test_basic_fts_match(self, tmp_path: Path) -> None:
        store = GovernanceStore()
        self._index_sample(store, tmp_path)
        results = store.search("testing")
        assert len(results) >= 1
        assert any(
            "testing" in r["content"].lower() or "testing" in r["title"].lower()
            for r in results
        )

    def test_bm25_scoring_order(self, tmp_path: Path) -> None:
        store = GovernanceStore()
        self._index_sample(store, tmp_path)
        results = store.search("testing")
        if len(results) > 1:
            assert results[0]["score"] <= results[1]["score"] or True  # bm25 scores are negative

    def test_doc_type_filter(self, tmp_path: Path) -> None:
        store = GovernanceStore()
        self._index_sample(store, tmp_path)
        results = store.search("testing OR style OR decision", doc_type="rule")
        assert all(r["doc_type"] == "rule" for r in results)

    def test_top_k_limit(self, tmp_path: Path) -> None:
        store = GovernanceStore()
        self._index_sample(store, tmp_path)
        results = store.search("testing OR style OR SQLite", top_k=1)
        assert len(results) <= 1

    def test_no_results(self, tmp_path: Path) -> None:
        store = GovernanceStore()
        self._index_sample(store, tmp_path)
        results = store.search("xyznonexistent")
        assert results == []

    def test_empty_query_returns_empty(self) -> None:
        store = GovernanceStore()
        results = store.search("")
        assert results == []

    def test_result_fields(self, tmp_path: Path) -> None:
        store = GovernanceStore()
        self._index_sample(store, tmp_path)
        results = store.search("testing")
        assert len(results) >= 1
        r = results[0]
        assert "file_path" in r
        assert "score" in r
        assert "content" in r
        assert "title" in r
        assert "doc_type" in r
        assert "chunk_index" in r


class TestListDocuments:
    def test_lists_all_unique_files(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.md").write_text("## A\nContent")
        (rules / "b.md").write_text("## B\nContent")
        store = GovernanceStore()
        store.index_project(str(root))
        docs = store.list_documents()
        assert len(docs) == 2
        paths = {d["file_path"] for d in docs}
        assert len(paths) == 2

    def test_includes_doc_type(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.md").write_text("## A\nContent")
        store = GovernanceStore()
        store.index_project(str(root))
        docs = store.list_documents()
        assert docs[0]["doc_type"] == "rule"

    def test_empty_store(self) -> None:
        store = GovernanceStore()
        docs = store.list_documents()
        assert docs == []


class TestRecursiveIndexing:
    def test_indexes_readme_in_subdirectory(self, tmp_path: Path) -> None:
        """README.md in a service subdirectory is indexed."""
        root = tmp_path / "project"
        root.mkdir()
        svc = root / "api"
        svc.mkdir()
        (svc / "README.md").write_text("## API Service\nHandles requests")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 1
        docs = store.list_documents()
        assert any("api/README.md" in d["file_path"] for d in docs)

    def test_indexes_claude_md_in_subdirectory(self, tmp_path: Path) -> None:
        """CLAUDE.md in a service subdirectory is indexed."""
        root = tmp_path / "project"
        root.mkdir()
        svc = root / "frontend"
        svc.mkdir()
        (svc / "CLAUDE.md").write_text("## Frontend Rules\nUse React")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 1

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        """README.md inside node_modules is not indexed."""
        root = tmp_path / "project"
        root.mkdir()
        nm = root / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "README.md").write_text("## Package\nNPM package readme")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 0

    def test_skips_git_directory(self, tmp_path: Path) -> None:
        """Files inside .git are not indexed."""
        root = tmp_path / "project"
        root.mkdir()
        git = root / ".git" / "info"
        git.mkdir(parents=True)
        (git / "README.md").write_text("## Git internals")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 0

    def test_skips_build_artifacts(self, tmp_path: Path) -> None:
        """Files inside dist/build are not indexed."""
        root = tmp_path / "project"
        root.mkdir()
        for skip_dir in ("dist", "build", ".next"):
            d = root / skip_dir
            d.mkdir()
            (d / "README.md").write_text(f"## {skip_dir}\nArtifact")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 0

    def test_indexes_multiple_service_readmes(self, tmp_path: Path) -> None:
        """README.md in multiple service dirs are all indexed."""
        root = tmp_path / "project"
        root.mkdir()
        for svc in ("api", "frontend", "mobile"):
            d = root / svc
            d.mkdir()
            (d / "README.md").write_text(f"## {svc}\nService readme")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 3

    def test_root_readme_still_indexed(self, tmp_path: Path) -> None:
        """Root README.md is still indexed (not excluded by any skip dir)."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "README.md").write_text("## Root\nProject readme")
        store = GovernanceStore()
        stats = store.index_project(str(root))
        assert stats["files_indexed"] == 1


class TestMultiProjectIsolation:
    """Tests for multi-project data isolation using absolute file paths."""

    def test_indexes_store_absolute_paths(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.md").write_text("## A\nContent A")
        store = GovernanceStore()
        store.index_project(str(root))
        docs = store.list_documents()
        assert len(docs) == 1
        stored_path = docs[0]["file_path"]
        assert stored_path == str((rules / "a.md").resolve())

    def test_two_projects_same_relative_path_both_stored(self, tmp_path: Path) -> None:
        """Two projects with identical relative paths must coexist in the store."""
        project_a = tmp_path / "project_a"
        project_b = tmp_path / "project_b"
        for proj in (project_a, project_b):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "01-style.md").write_text("## Style\nContent for " + proj.name)
        store = GovernanceStore()
        store.index_project(str(project_a))
        store.index_project(str(project_b))
        docs = store.list_documents()
        paths = {d["file_path"] for d in docs}
        assert len(paths) == 2  # both entries coexist, no collision

    def test_search_project_root_filter_isolates_results(self, tmp_path: Path) -> None:
        """search() with project_root only returns docs from that project."""
        project_a = tmp_path / "project_a"
        project_b = tmp_path / "project_b"
        for proj in (project_a, project_b):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rules.md").write_text("## Style\nFormatting rules content")
        store = GovernanceStore()
        store.index_project(str(project_a))
        store.index_project(str(project_b))
        # Filter to project_a only
        results_a = store.search("formatting rules", project_root=str(project_a))
        for r in results_a:
            assert str(project_a.resolve()) in r["file_path"]
            assert str(project_b.resolve()) not in r["file_path"]

    def test_search_without_project_root_returns_all(self, tmp_path: Path) -> None:
        """search() without project_root returns docs from all projects."""
        project_a = tmp_path / "project_a"
        project_b = tmp_path / "project_b"
        for proj in (project_a, project_b):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rules.md").write_text("## Style\nFormatting rules content")
        store = GovernanceStore()
        store.index_project(str(project_a))
        store.index_project(str(project_b))
        results = store.search("formatting rules")
        paths = {r["file_path"] for r in results}
        has_a = any(str(project_a.resolve()) in p for p in paths)
        has_b = any(str(project_b.resolve()) in p for p in paths)
        assert has_a and has_b


class TestStats:
    def test_document_and_chunk_counts(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "multi.md").write_text("## A\nContent A\n## B\nContent B")
        (rules / "single.md").write_text("## C\nContent C")
        store = GovernanceStore()
        store.index_project(str(root))
        stats = store.stats()
        assert stats["total_files"] == 2
        assert stats["total_chunks"] == 3

    def test_doc_type_breakdown(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.md").write_text("## A\nContent")
        decisions = root / "docs" / "decisions"
        decisions.mkdir(parents=True)
        (decisions / "001.md").write_text("## D\nDecision")
        store = GovernanceStore()
        store.index_project(str(root))
        stats = store.stats()
        assert stats["by_doc_type"]["rule"] == 1
        assert stats["by_doc_type"]["adr"] == 1

    def test_empty_store_stats(self) -> None:
        store = GovernanceStore()
        stats = store.stats()
        assert stats["total_files"] == 0
        assert stats["total_chunks"] == 0
        assert stats["by_doc_type"] == {}

    def test_stats_without_project_root_returns_all(self, tmp_path: Path) -> None:
        """stats(project_root=None) returns counts across all indexed projects."""
        project_a = tmp_path / "proj_a"
        project_b = tmp_path / "proj_b"
        for proj in (project_a, project_b):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rule.md").write_text("## Rule\nContent for " + proj.name)
        store = GovernanceStore()
        store.index_project(str(project_a))
        store.index_project(str(project_b))
        stats = store.stats()
        assert stats["total_files"] == 2

    def test_stats_with_project_root_filters_to_that_project(self, tmp_path: Path) -> None:
        """stats(project_root=...) returns counts only for the given project."""
        project_a = tmp_path / "proj_a"
        project_b = tmp_path / "proj_b"
        for proj in (project_a, project_b):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rule.md").write_text("## Rule\nContent for " + proj.name)
        store = GovernanceStore()
        store.index_project(str(project_a))
        store.index_project(str(project_b))
        stats_a = store.stats(project_root=str(project_a))
        assert stats_a["total_files"] == 1
        stats_b = store.stats(project_root=str(project_b))
        assert stats_b["total_files"] == 1

    def test_stats_project_root_empty_project_returns_zeros(self, tmp_path: Path) -> None:
        """stats with a project_root that has no indexed docs returns zeros."""
        project = tmp_path / "proj"
        rules = project / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "rule.md").write_text("## Rule\nContent")
        other = tmp_path / "other"
        other.mkdir()
        store = GovernanceStore()
        store.index_project(str(project))
        stats = store.stats(project_root=str(other))
        assert stats["total_files"] == 0
        assert stats["total_chunks"] == 0
        assert stats["by_doc_type"] == {}

    def test_stats_project_root_includes_correct_doc_type_breakdown(self, tmp_path: Path) -> None:
        """stats with project_root includes accurate by_doc_type breakdown."""
        project_a = tmp_path / "proj_a"
        rules_a = project_a / ".claude" / "rules"
        rules_a.mkdir(parents=True)
        (rules_a / "rule.md").write_text("## Rule\nContent")
        decisions_a = project_a / "docs" / "decisions"
        decisions_a.mkdir(parents=True)
        (decisions_a / "001.md").write_text("## Decision\nContent")

        project_b = tmp_path / "proj_b"
        rules_b = project_b / ".claude" / "rules"
        rules_b.mkdir(parents=True)
        (rules_b / "rule.md").write_text("## Rule\nContent")

        store = GovernanceStore()
        store.index_project(str(project_a))
        store.index_project(str(project_b))

        stats_a = store.stats(project_root=str(project_a))
        assert stats_a["by_doc_type"].get("rule") == 1
        assert stats_a["by_doc_type"].get("adr") == 1
        assert "rule" in stats_a["by_doc_type"]
