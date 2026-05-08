import json
import pandas as pd
import re

def parse_json_content(content_str):
    """
    Attempts to parse JSON from a string that might contain other text.
    Uses regex to find the main JSON block starting/ending at line boundaries.
    """
    try:
        return json.loads(content_str)
    except json.JSONDecodeError:
        pass
    
    # Try finding block bounded by lines starting with { and }
    # This avoids matching { in text like "Label: {value}"
    try:
        # Find first line that looks like start of JSON object
        start_match = re.search(r'^\s*\{', content_str, re.MULTILINE)
        if start_match:
            start = start_match.start()
            # Find last line that looks like end of JSON object
            # We iterate all '^\s*}' and take the last one
            end_matches = list(re.finditer(r'^\s*\}', content_str, re.MULTILINE))
            if end_matches:
                end = end_matches[-1].end()
                
                json_candidate = content_str[start:end]
                try:
                    return json.loads(json_candidate)
                except json.JSONDecodeError:
                    # If failed, maybe we took too wide a range. 
                    # Try fallback to simple brace finding but skip the first bad one?
                    pass
    except:
        pass

    # Fallback: iterative attempt
    # Find all '{' positions
    starts = [m.start() for m in re.finditer(r'\{', content_str)]
    # Find last '}'
    ends = [m.end() for m in re.finditer(r'\}', content_str)]
    
    if ends:
        last_end = ends[-1]
        # Try starts from first to last (limit checks to avoid stuck)
        for s in starts:
            try:
                candidate = content_str[s : last_end]
                return json.loads(candidate)
            except:
                continue
                
    return None

def flatten_json(y):
    """
    Flattens a nested JSON object into a single-level dictionary with dot notation key names.
    Handles nested dictionaries and lists.
    """
    out = {}

    def flatten(x, name=''):
        if isinstance(x, dict):
            for a in x:
                flatten(x[a], name + a + '.')
        elif isinstance(x, list):
            i = 0
            for a in x:
                flatten(a, name + str(i) + '.')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out

def extract_schema(df):
    """
    Analyzes a DataFrame and returns a schema dictionary mapping columns to their types and possible values.
    Schema format:
    {
        'column_name': {
            'type': 'bool' | 'number' | 'string',
            'min': value, 'max': value, # for numbers
            'options': [list of unique values] # for strings
        }
    }
    """
    schema = {}
    
    # Exclude non-data columns if any (though we assume all flattened cols are data for now)
    # We might want to skip 'filename', 'image_path' if they exist, but let's handle them in UI or here.
    exclude_cols = ['filename', 'image_path', 'filepath']
    
    for col in df.columns:
        if col in exclude_cols:
            continue
            
        col_dtype = df[col].dtype
        
        if pd.api.types.is_bool_dtype(col_dtype):
            schema[col] = {'type': 'bool'}
        elif pd.api.types.is_numeric_dtype(col_dtype):
            schema[col] = {
                'type': 'number',
                'min': float(df[col].min()),
                'max': float(df[col].max())
            }
        else:
            # Assume string/object. Collect unique values for multiselect.
            # Handle list-like strings or just strings.
            # For now, treat as atomic strings.
            unique_vals = df[col].dropna().unique().tolist()
            # If too many unique values (e.g. unique ID), maybe skip? 
            # User requirement: "String (Metin) değerleri -> Multiselect (Klasördeki tüm benzersiz değerleri toplayıp listeye doldurmalı)"
            # So we list them all.
            schema[col] = {
                'type': 'string',
                'options': sorted([str(v) for v in unique_vals])
            }
            
    return schema
