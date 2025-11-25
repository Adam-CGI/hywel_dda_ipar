import importlib.util
import os


def _load_app():
    """Dynamically load the Flask application without relying on package resolution."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'flask_app', 'application.py')
    spec = importlib.util.spec_from_file_location("_app_module", app_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore
    return module.app


def test_about_page_status_and_content():
    app = _load_app()
    client = app.test_client()
    resp = client.get('/about')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'What It Is' in html
    assert 'Future Development' in html
    assert 'Hywel Dda University Health Board' in html
    assert '<h2>' in html  # markdown headings rendered
