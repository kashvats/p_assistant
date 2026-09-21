from __future__ import annotations

from pathlib import Path

APP = Path('src/living_assistant/webui/src/main.js')
INDEX = Path('src/living_assistant/webui/index.html')


def _app() -> str:
    return APP.read_text(encoding='utf-8')


def test_ui02_chat_renders_assistant_markdown_without_html_injection():
    app = _app()
    assert "m.role === 'assistant' ? h(Markdown, {text: m.text}) : m.text" in app
    assert 'function Markdown({text})' in app
    assert 'dangerouslySetInnerHTML' not in app
    assert '.innerHTML' not in app


def test_ui03_chat_uses_local_prism_syntax_highlighting():
    app = _app()
    index = INDEX.read_text(encoding='utf-8')
    assert 'Prism.tokenize' in app
    assert 'function CodeBlock({language, source})' in app
    assert '/vendor/prism.js' in index
    assert '/vendor/prism-python.min.js' in index
    assert '/vendor/prism-javascript.min.js' in index
    assert '/vendor/prism-bash.min.js' in index


def test_ui04_chat_has_live_streaming_token_indicator():
    app = _app()
    assert "if(event.type==='token')" in app
    assert "this.setState({streaming:false})" in app
    assert "this.state.streaming" in app
    assert "'Generating'" in app
    assert 'animate-pulse' in app


def test_ui05_approvals_use_non_blocking_toast_for_new_requests():
    app = _app()
    assert 'this.approvalSeen = new Set()' in app
    assert 'const fresh = approvals.filter' in app
    assert 'this.notify(`${fresh.length} new approval' in app
    assert "this.state.toast ? h('div'" in app
    assert 'alert(' not in app


def test_ui08_dashboard_uses_mobile_first_responsive_layout():
    app = _app()
    index = INDEX.read_text(encoding='utf-8')
    assert 'name="viewport"' in index
    assert "lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]" in app
    assert "flex lg:block" in app
    assert "overflow-x-auto" in app
    assert "flex-col sm:flex-row" in app
    assert "grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4" in app
    assert "h-64 md:h-[58vh]" in app
