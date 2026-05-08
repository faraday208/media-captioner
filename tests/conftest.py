"""Test fixture'ları — media-captioner."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def caption_dataset(tmp_path: Path) -> Path:
    """Sahte caption JSON dataset — json_to_txt için."""
    import json
    # 2 caption JSON
    (tmp_path / "img1.json").write_text(json.dumps({
        "captioning": {
            "short": "A red car on the street.",
            "medium": "A vintage red sports car parked on a city street.",
            "long": "A vintage red sports car with chrome details parked on a busy city street during golden hour.",
        }
    }))
    (tmp_path / "img2.json").write_text(json.dumps({
        "captioning": {
            "short": "Mountain landscape.",
            "medium": "Snow-covered mountain peaks against blue sky.",
            "long": "Majestic snow-covered mountain peaks rising against a clear blue sky in the morning light.",
        }
    }))
    # Pass dosyası — json_to_txt filter etmeli
    (tmp_path / "img1_pass1_face.json").write_text("{}")
    return tmp_path
