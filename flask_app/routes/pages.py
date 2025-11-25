"""Static / informational pages blueprint (About page).
Loads markdown content for easy non-technical editing.
"""
import os
import re
import logging
from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

pages_bp = Blueprint('pages', __name__)

ABOUT_MD_REL_PATH = os.path.join('content', 'about.md')

try:
    import markdown  # type: ignore
    _MARKDOWN_AVAILABLE = True
except Exception:
    _MARKDOWN_AVAILABLE = False
    logger.warning("markdown package not available; /about will serve raw text")


def _segment_markdown(raw_md: str):
    """Break markdown into sections keyed by normalized heading text.
    Returns dict: {heading_key: markdown_body}.
    """
    pattern = re.compile(r"^##\s+(.*?)\n(.*?)(?=\n##\s+|\Z)", re.MULTILINE | re.DOTALL)
    sections = {}
    for match in pattern.finditer(raw_md):
        heading = match.group(1).strip()
        body = match.group(2).strip()
        key = heading.lower().replace(' ', '_').replace("'", '').replace(':', '').replace('&', '')
        sections[key] = body
    return sections


def _convert_md(md_text: str):
    if _MARKDOWN_AVAILABLE:
        return markdown.markdown(md_text, extensions=['fenced_code', 'tables'])
    escaped = md_text.replace('<', '&lt;').replace('>', '&gt;')
    return f"<pre style='white-space:pre-wrap'>{escaped}</pre>"


def _load_about_markdown():
    """Load markdown, segment into sections and convert each to HTML.
    Returns dict with html fragments and flags.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # flask_app/
    md_path = os.path.join(base_dir, ABOUT_MD_REL_PATH)
    if not os.path.exists(md_path):
        logger.warning(f"About markdown file missing at {md_path}")
        return {
            'full_html': "<p><em>About content file missing. Create 'flask_app/content/about.md'.</em></p>",
            'converted': True,
            'sections': {}
        }
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        sections_md = _segment_markdown(raw)
        sections_html = {k: _convert_md(v) for k, v in sections_md.items()}
        logger.info(f"Parsed {len(sections_html)} sections: {list(sections_html.keys())}")
        return {
            'full_html': _convert_md(raw),
            'converted': _MARKDOWN_AVAILABLE,
            'sections': sections_html
        }
    except Exception as e:
        logger.error(f"Failed to load about markdown: {e}")
        return {
            'full_html': f"<p><em>Error loading about content: {e}</em></p>",
            'converted': True,
            'sections': {}
        }


@pages_bp.route('/about', methods=['GET'])
def about():  # endpoint: pages.about
    """Render the About page with markdown-driven content."""
    data = _load_about_markdown()
    return render_template(
        'about.html',
        about_html=data['full_html'],
        markdown_converted=data['converted'],
        about_sections=data['sections']
    )
