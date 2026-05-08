import json

def debug_parsing():
    sample_path = "/opt/media-pipeline/dataset-prep/06-caption/client/v5_detailed_json.txt"
    with open(sample_path, 'r') as f:
        content = f.read()
    
    start = content.find('{')
    end = content.rfind('}')
    
    print(f"Start: {start}, End: {end}")
    
    if start != -1 and end != -1:
        json_str = content[start : end + 1]
        print(f"Extracted Length: {len(json_str)}")
        print(f"First 50 chars: {json_str[:50]}")
        print(f"Last 50 chars: {json_str[-50:]}")
        
        try:
            json.loads(json_str)
            print("Valid JSON!")
        except Exception as e:
            print(f"JSON Error: {e}")

if __name__ == "__main__":
    debug_parsing()
