import os
import json
import pandas as pd
from typing import List, Dict
from .json_handler import flatten_json, parse_json_content

def scan_directory(directory_path: str) -> List[Dict]:
    """
    Scans the directory for .json files and attempts to find matching image files.
    Returns a list of dictionaries, each containing:
    - filename: basename without extension
    - image_path: absolute path to the image
    - json_path: absolute path to the json file
    """
    valid_image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    items = []
    
    if not os.path.exists(directory_path):
        return []

    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith('.json'):
                basename = os.path.splitext(file)[0]
                json_path = os.path.join(root, file)
                
                # Check for corresponding image
                image_path = None
                for ext in valid_image_extensions:
                    potential_params = [
                        os.path.join(root, basename + ext),
                        os.path.join(root, basename + ext.upper())
                    ]
                    for p in potential_params:
                        if os.path.exists(p):
                            image_path = p
                            break
                    if image_path:
                        break
                
                if image_path:
                    items.append({
                        'filename': basename,
                        'json_path': json_path,
                        'image_path': image_path
                    })
    
    return items

def load_dataset(items: List[Dict]) -> pd.DataFrame:
    """
    Loads JSON content from the scanned items, flattens them, and returns a DataFrame.
    """
    data = []
    
    for item in items:
        try:
            with open(item['json_path'], 'r', encoding='utf-8') as f:
                content_str = f.read()
                
            content = parse_json_content(content_str)
            if content is None:
                continue

            flat_content = flatten_json(content)
            
            # Merge metadata with content
            row = {
                'filename': item['filename'],
                'image_path': item['image_path'],
                'json_path': item['json_path'],
                **flat_content
            }
            data.append(row)
        except Exception as e:
            print(f"Error loading {item['json_path']}: {e}")
            continue
            
    if not data:
        return pd.DataFrame()
        
    return pd.DataFrame(data)
