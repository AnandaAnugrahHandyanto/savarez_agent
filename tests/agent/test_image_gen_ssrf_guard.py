"""Tests for save_url_image SSRF guard in agent.image_gen_provider."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """Point HERMES_HOME at a temp dir so cache writes land safely."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_PROFILE", raising=False)


def test_save_url_image_blocks_private_loopback():
    """SSRF guard: save_url_image must reject loopback URLs."""
    from agent.image_gen_provider import save_url_image

    with pytest.raises(ValueError, match="private or internal"):
        save_url_image("http://127.0.0.1:8080/secret")


def test_save_url_image_blocks_cloud_metadata():
    """SSRF guard: save_url_image must reject cloud metadata endpoints."""
    from agent.image_gen_provider import save_url_image

    with pytest.raises(ValueError, match="private or internal"):
        save_url_image("http://169.254.169.254/latest/meta-data/")


def test_save_url_image_blocks_internal_host():
    """SSRF guard: save_url_image must reject internal network addresses."""
    from agent.image_gen_provider import save_url_image

    with pytest.raises(ValueError, match="private or internal"):
        save_url_image("http://10.0.0.1/admin")


def test_save_url_image_allows_public_url():
    """SSRF guard: save_url_image should proceed with valid public URLs."""
    from agent.image_gen_provider import save_url_image

    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "image/png"}
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b"\x89PNG\r\n"])

    with patch("requests.get", return_value=mock_response),          patch("tools.url_safety.is_safe_url", return_value=True):
        path = save_url_image("https://api.x.ai/v1/images/abc.png")
        assert path.exists()
        assert path.name.endswith(".png")


def test_save_url_image_blocks_redirect_to_private():
    """SSRF guard: redirect from public URL to private must be blocked."""
    from agent.image_gen_provider import save_url_image

    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "image/png"}
    mock_response.raise_for_status = MagicMock()
    mock_response.url = "http://127.0.0.1:8080/exfil"  # redirect target

    def _is_safe(url: str) -> bool:
        return "127.0.0.1" not in url

    with patch("requests.get", return_value=mock_response),          patch("tools.url_safety.is_safe_url", side_effect=_is_safe):
        with pytest.raises(ValueError, match="redirect target"):
            save_url_image("https://cdn.example.com/image.png")


def test_save_url_image_allows_redirect_to_public():
    """SSRF guard: redirect to another public URL should proceed."""
    from agent.image_gen_provider import save_url_image

    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "image/png"}
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b"\x89PNG\r\n"])
    mock_response.url = "https://cdn2.example.com/final.png"  # redirect

    with patch("requests.get", return_value=mock_response),          patch("tools.url_safety.is_safe_url", return_value=True):
        path = save_url_image("https://cdn1.example.com/image.png")
        assert path.exists()


def test_save_url_image_no_redirect_skips_revalidation():
    """SSRF guard: when response.url matches original, skip re-check."""
    from agent.image_gen_provider import save_url_image

    url = "https://api.x.ai/v1/images/abc.png"
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "image/png"}
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b"\x89PNG\r\n"])
    mock_response.url = url  # same URL — no redirect

    with patch("requests.get", return_value=mock_response),          patch("tools.url_safety.is_safe_url", return_value=True) as mock_safe:
        path = save_url_image(url)
        assert path.exists()
        # is_safe_url should be called once (initial check), not twice
        assert mock_safe.call_count == 1
