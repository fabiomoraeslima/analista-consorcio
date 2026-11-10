from src import main


def test_load_attachments_lists_files_sorted(tmp_path, monkeypatch):
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir()
    (attachments_dir / "b.pdf").write_text("b")
    (attachments_dir / "a.jpg").write_text("a")
    (attachments_dir / ".gitkeep").write_text("")
    monkeypatch.setattr(main, "ATTACHMENTS_DIR", attachments_dir)

    result = main.load_attachments()

    assert [p.name for p in result] == ["a.jpg", "b.pdf"]


def test_load_attachments_missing_dir_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "ATTACHMENTS_DIR", tmp_path / "does-not-exist")

    assert main.load_attachments() == []
