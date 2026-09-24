import pytest
from pathlib import Path
from src.research.tools import DiskCache, get_cache_key


def test_disk_cache(tmp_path: Path):
    cache = DiskCache(cache_dir=tmp_path)
    key = get_cache_key("https://example.com/api", "prompt")
    
    assert cache.get(key) is None
    cache.set(key, {"status_code": 200, "text": "sample text"})
    
    cached = cache.get(key)
    assert cached is not None
    assert cached["status_code"] == 200
    assert cached["text"] == "sample text"
