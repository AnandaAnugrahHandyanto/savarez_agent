import io
import zipfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from tools.skills_hub import ClawHubSource, SKILLS_DIR

def test_clawhub_zip_slip_prevention(tmp_path):
    """
    Test that ClawHubSource._download_zip correctly identifies and skips 
    malicious paths that attempt directory traversal (Zip Slip).
    """
    # Create a dummy ClawHubSource
    source = ClawHubSource()
    
    # Create a malicious ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # 1. Normal file
        zf.writestr("good_file.md", "safe content")
        # 2. Path traversal (Zip Slip)
        zf.writestr("../../../evil.txt", "should be blocked")
        # 3. Absolute path (some systems/zip libs might handle this dangerously)
        zf.writestr("/tmp/absolute_evil.txt", "should be blocked")
        # 4. Nested safe file
        zf.writestr("subdir/nested.md", "safe nested content")

    # Mock the HTTP response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = buf.getvalue()
    
    # We need to mock SKILLS_DIR to use our tmp_path for the resolution test
    with patch("tools.skills_hub.SKILLS_DIR", tmp_path), \
         patch("tools.skills_hub.httpx.get", return_value=mock_resp):
        
        # Call the method
        files = source._download_zip("test-skill", "1.0.0")
        
        # Verify results
        assert "good_file.md" in files
        assert files["good_file.md"] == "safe content"
        
        assert "subdir/nested.md" in files
        assert files["subdir/nested.md"] == "safe nested content"
        
        # Malicious paths should NOT be in the result
        assert "../../../evil.txt" not in files
        assert "evil.txt" not in files
        assert "/tmp/absolute_evil.txt" not in files
        assert "absolute_evil.txt" not in files
        
        # Ensure only 2 files were extracted
        assert len(files) == 2
