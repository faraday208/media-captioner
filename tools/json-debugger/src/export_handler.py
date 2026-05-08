import os
import shutil
import pandas as pd

def copy_files(selected_rows: pd.DataFrame, target_dir: str):
    """
    Copies image and json files from the selected rows in the DataFrame to the target directory.
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    copied_count = 0
    errors = []
    
    for _, row in selected_rows.iterrows():
        try:
            src_image = row['image_path']
            src_json = row['json_path']
            filename = row['filename']
            
            # Define targets (preserve original extension)
            # We can use basename from src path to be safe about case and extension
            image_basename = os.path.basename(src_image)
            json_basename = os.path.basename(src_json)
            
            dst_image = os.path.join(target_dir, image_basename)
            dst_json = os.path.join(target_dir, json_basename)
            
            shutil.copy2(src_image, dst_image)
            shutil.copy2(src_json, dst_json)
            
            copied_count += 1
            
        except Exception as e:
            errors.append(f"Error copying {row.get('filename', 'unknown')}: {str(e)}")
            
    return copied_count, errors
