import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch
from agent.recipe_installer import RecipeInstaller

def test_recipe_installer_deploy(tmp_path):
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    
    # Mock hermes dir
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / ".env").touch()
    
    (hermes_dir / "cron").mkdir()
    (hermes_dir / "cron" / "jobs.json").write_text('{"jobs": []}')
    
    # Write a test recipe using the exact block syntax parsed by recipe_installer
    recipe_content = """
Some description here
INSTALL: keys
```yaml
TEST_KEY: required
```
INSTALL: cron
```json
[{"prompt": "fake job"}]
```
INSTALL: file:dummy.py
```python
print("Hello")
```
"""
    recipe_file = recipes_dir / "test-recipe.md"
    recipe_file.write_text(recipe_content)
    
    installer = RecipeInstaller(recipes_dir=str(recipes_dir))
    installer.hermes_dir = hermes_dir 
    
    # Let installer write dummy.py to tmp_path
    with patch("agent.recipe_installer.__file__", str(tmp_path / "recipe_installer.py")):
        res = installer.install("test-recipe")
    
    assert res is True
    
    # Check Env Keys
    env_content = (hermes_dir / ".env").read_text()
    assert "TEST_KEY=" in env_content
    
    # Check Cron
    jobs_content = json.loads((hermes_dir / "cron" / "jobs.json").read_text())
    assert len(jobs_content["jobs"]) == 1
    assert jobs_content["jobs"][0]["prompt"] == "fake job"
