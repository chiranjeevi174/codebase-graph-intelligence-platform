"""Unit tests for Repository Loader file enumeration and gitignore pathspec filtering."""

import tempfile
from pathlib import Path

from app.ingestion.git_loader import LocalGitLoader


def test_repository_loader_enumeration():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create dummy Python files and ignored files
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def add(a, b): return a + b")

        # Create .gitignore
        (tmp_path / ".gitignore").write_text("ignored.py\n.venv/\n")
        (tmp_path / "ignored.py").write_text("secret = 1")

        # Create subfolder with python file
        sub = tmp_path / "module"
        sub.mkdir()
        (tmp_path / "module" / "helper.py").write_text("class Helper: pass")

        loader = LocalGitLoader()
        repo_info, files = loader.load_repository(str(tmp_path))

        rel_paths = [f.relative_path for f in files]

        assert repo_info.total_files == 3
        assert "main.py" in rel_paths
        assert "utils.py" in rel_paths
        assert "module/helper.py" in rel_paths or "module\\helper.py" in [
            f.relative_path.replace("/", "\\") for f in files
        ]
        assert "ignored.py" not in rel_paths
