from app.backends import query_platform_workspace


def test_query_platform_workspace_returns_placeholder_result() -> None:
    results = query_platform_workspace('budget', enabled=True)
    assert len(results) == 1
    assert results[0].source == 'PLATFORM'
    assert results[0].entity_type == 'DOCUMENT'


def test_query_platform_workspace_disabled_returns_empty() -> None:
    assert query_platform_workspace('budget', enabled=False) == []
