from app.project_data_state import (
    DATA_PAGE_NAMES,
    ProjectDataRevisionState,
)


def test_source_change_marks_only_data_workspaces_dirty() -> None:
    state = ProjectDataRevisionState()

    revision = state.mark_changed()

    assert revision == 1
    assert state.revision == 1
    assert state.dirty_pages == DATA_PAGE_NAMES
    assert "PROJECT" not in state.dirty_pages
    assert "TOOLS" not in state.dirty_pages
    assert "HELP" not in state.dirty_pages


def test_consuming_visible_page_keeps_hidden_pages_dirty() -> None:
    state = ProjectDataRevisionState()
    state.mark_changed()

    assert state.consume("DIALOG") is True
    assert state.is_dirty("DIALOG") is False
    assert state.is_dirty("SCRIPT") is True
    assert state.is_dirty("TRACKING") is True
    assert state.is_dirty("DATA") is True


def test_project_switch_can_mark_all_pages_for_lazy_first_load() -> None:
    state = ProjectDataRevisionState(revision=7)
    state.reset(mark_dirty=True)

    assert state.revision == 0
    assert state.dirty_pages == DATA_PAGE_NAMES


def test_clean_page_is_not_consumed_twice() -> None:
    state = ProjectDataRevisionState()
    state.mark_changed()

    assert state.consume("SCRIPT") is True
    assert state.consume("SCRIPT") is False


def test_multiple_changes_increment_revision_and_re_dirty_consumed_page() -> None:
    state = ProjectDataRevisionState()
    assert state.mark_changed() == 1
    state.consume("SCRIPT")

    assert state.mark_changed() == 2
    assert state.is_dirty("SCRIPT") is True
