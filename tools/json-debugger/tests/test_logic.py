import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.json_handler import parse_json_content, flatten_json
from src.data_loader import scan_directory, load_dataset

def test_parsing():
    print("Testing JSON Parsing...")
    sample_path = "/opt/media-pipeline/dataset-prep/06-caption/client/v5_detailed_json.txt"
    if os.path.exists(sample_path):
        with open(sample_path, 'r') as f:
            content = f.read()
            parsed = parse_json_content(content)
            if parsed:
                print("SUCCESS: Parsed complex JSON file.")
                flat = flatten_json(parsed)
                print(f"Flattened Keys sample: {list(flat.keys())[:5]}")
            else:
                print("FAILURE: Could not parse complex JSON file.")
    else:
        print(f"Skipping file test: {sample_path} not found.")

def test_data_loading():
    # create dummy dir
    dummy_dir = "tests/dummy_data"
    os.makedirs(dummy_dir, exist_ok=True)
    
    # create dummy json and image
    dummy_json = os.path.join(dummy_dir, "test.json")
    dummy_img = os.path.join(dummy_dir, "test.jpg")
    
    with open(dummy_json, 'w') as f:
        f.write('{"foo": {"bar": "baz"}, "num": 1}')
        
    with open(dummy_img, 'w') as f:
        f.write("fake image")
        
    print(f"Scanning {dummy_dir}...")
    items = scan_directory(dummy_dir)
    print(f"Found {len(items)} items.")
    
    if items:
        df = load_dataset(items)
        print("DataFrame loaded:")
        print(df.columns)
        if 'foo.bar' in df.columns:
            print("SUCCESS: Flattening working in loader.")
        else:
            print("FAILURE: 'foo.bar' not in columns.")
            
    # Clean up
    import shutil
    shutil.rmtree(dummy_dir)

if __name__ == "__main__":
    test_parsing()
    test_data_loading()
