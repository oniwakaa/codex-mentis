import pytest
from unittest.mock import MagicMock, patch
from codex_mentis.knowledge.webfetch_bridge import WebfetchBridge

def test_webfetch_bridge_is_available():
    bridge = WebfetchBridge()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert bridge.is_available() is True
        
        # Reset cached state
        bridge._available = None
        mock_run.return_value.returncode = 1
        assert bridge.is_available() is False

def test_fallback_search():
    bridge = WebfetchBridge()
    bridge._available = False
    
    mock_html = """
    <html>
    <body>
    <div class="result__body">
        <a class="result__a" href="https://example.com/one">Result Title One</a>
        <div class="result__snippet">Snippet contents for result one.</div>
    </div>
    <div class="result__body">
        <a class="result__a" href="https://example.com/two">Result Title Two</a>
        <div class="result__snippet">Snippet contents for result two.</div>
    </div>
    </body>
    </html>
    """
    
    class MockResponse:
        status_code = 200
        text = mock_html
        
    class MockClient:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def get(self, url, headers=None):
            return MockResponse()

    with patch("httpx.Client", return_value=MockClient()):
        results = bridge.search("quantum gravity", max_results=2)
        assert len(results) == 2
        assert results[0]["title"] == "Result Title One"
        assert results[0]["url"] == "https://example.com/one"
        assert results[0]["snippet"] == "Snippet contents for result one."
        assert results[0]["source"] == "duckduckgo_fallback"

def test_fallback_fetch():
    bridge = WebfetchBridge()
    bridge._available = False
    
    mock_html = """
    <html>
    <head><title>My Physics Article</title></head>
    <body>
        <script>alert("hello");</script>
        <style>body { color: red; }</style>
        <h1>Main Title</h1>
        <p>This is the actual article content.</p>
    </body>
    </html>
    """
    
    class MockResponse:
        status_code = 200
        text = mock_html
        
    class MockClient:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def get(self, url, headers=None):
            return MockResponse()

    with patch("httpx.Client", return_value=MockClient()):
        result = bridge.fetch_url("https://example.com/article")
        assert result["title"] == "My Physics Article"
        assert "Main Title" in result["text"]
        assert "actual article content" in result["text"]
        # Script and style should be stripped
        assert "alert" not in result["text"]
        assert "color" not in result["text"]

def test_search_and_fetch():
    bridge = WebfetchBridge()
    bridge._available = False
    
    # Mock both search and fetch
    search_mock = MagicMock(return_value=[
        {"title": "Title 1", "url": "https://url1.com", "snippet": "snippet 1"}
    ])
    fetch_mock = MagicMock(return_value={
        "title": "Page Title 1", "text": "Page text 1", "url": "https://url1.com", "cached": True
    })
    
    bridge.search = search_mock
    bridge.fetch_url = fetch_mock
    
    results = bridge.search_and_fetch("search query")
    assert len(results) == 1
    assert results[0]["full_text"] == "Page text 1"
    assert results[0]["page_title"] == "Page Title 1"
    assert results[0]["cached"] is True
