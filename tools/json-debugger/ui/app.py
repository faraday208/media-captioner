import sys
import os
import gradio as gr
import pandas as pd
import numpy as np

# Adjust path to find src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.json_handler import flatten_json, extract_schema, parse_json_content
from src.data_loader import scan_directory, load_dataset
from src.export_handler import copy_files

# Global State Helper
def get_empty_df():
    return pd.DataFrame()

def load_and_process(schema_file_path, dataset_dir):
    print(f"Loading... Schema: {schema_file_path}, Data: {dataset_dir}")
    
    # 1. Parse Template to get Base Schema (Keys + Types)
    template_schema = {}
    if schema_file_path and os.path.exists(schema_file_path):
        try:
            with open(schema_file_path, 'r', encoding='utf-8') as f:
                content = parse_json_content(f.read())
                if content:
                    flat_template = flatten_json(content)
                    # Infer types from template values
                    for k, v in flat_template.items():
                        if isinstance(v, bool):
                            template_schema[k] = {'type': 'bool'}
                        elif isinstance(v, (int, float)):
                            template_schema[k] = {'type': 'number', 'min': 0, 'max': 100} # default range if no data
                        else:
                            # Assume string
                            template_schema[k] = {'type': 'string', 'options': []}
                    print(f"Template loaded. Keys: {len(template_schema)}")
        except Exception as e:
            print(f"Schema load error: {e}")
            return None, pd.DataFrame(), f"Error loading schema: {e}", []

    # 2. Load Dataset
    if not dataset_dir or not os.path.exists(dataset_dir):
        return None, pd.DataFrame(), "Invalid dataset directory", []
        
    items = scan_directory(dataset_dir)
    df = load_dataset(items)
    print(f"Dataset loaded. Rows: {len(df)}. Columns: {len(df.columns)}")
    
    if df.empty:
        # If schema exists, we can still return it, just with empty data?
        # But UI expects DF logic.
        return template_schema, pd.DataFrame(), "No valid data found", list(template_schema.keys())

    # 3. Extract Stats from DF
    df_schema = extract_schema(df)
    
    # 4. Merge: Priority to Template Keys
    final_schema = {}
    
    if template_schema:
        print("Merging schemas...")
        matched_keys = 0
        
        # Use template keys. Update options/stats from DF if available.
        for k, t_info in template_schema.items():
            final_schema[k] = t_info.copy()
            
            if k in df_schema:
                matched_keys += 1
                d_info = df_schema[k]
                
                # Debug specific interesting keys
                if "clothing" in k or "face" in k:
                    print(f"DEBUG MERGE [{k}]: Template={t_info.get('type')} Data={d_info.get('type')} OptionsLen={len(d_info.get('options', []))}")

                # Update stats
                if t_info['type'] == 'string':
                    # Force populate options if data has them
                    if 'options' in d_info:
                        final_schema[k]['options'] = d_info['options']
                    else:
                        print(f"DEBUG: Key {k} has no options in data schema. Type: {d_info.get('type')}")
                        
                elif t_info['type'] == 'number' and d_info['type'] == 'number':
                    final_schema[k]['min'] = d_info.get('min', 0)
                    final_schema[k]['max'] = d_info.get('max', 100)
            else:
                 # Debug: Key missing in data
                 # print(f"Key {k} missing in dataset columns.")
                 pass
        
        print(f"Matched {matched_keys} keys out of {len(template_schema)} template keys.")
        print(f"Sample DF Keys: {list(df_schema.keys())[:5]}")
    else:
        # No template provided, use all DF columns
        final_schema = df_schema

    print(f"Final Schema: {len(final_schema)} keys")
    return final_schema, df, f"Loaded {len(df)} items.", list(final_schema.keys())

# Dynamic UI Generation
def create_filter_components(schema):
    filters = []
    filter_keys = []
    
    if not schema:
        return [], []

    for key, info in schema.items():
        if info['type'] == 'bool':
            comp = gr.Radio(label=key, choices=["Any", "True", "False"], value="Any")
            filters.append(comp)
            filter_keys.append(key)
        elif info['type'] == 'string':
            opts = info.get('options', [])
            if len(opts) > 50: # Cap large lists
                opts = opts[:50]
            comp = gr.Dropdown(label=key, choices=["Any"] + opts, value="Any", multiselect=True)
            filters.append(comp)
            filter_keys.append(key)
        elif info['type'] == 'number':
            mn, mx = info.get('min', 0), info.get('max', 100)
            comp = gr.Slider(label=key, minimum=mn, maximum=mx, value=mn, step=1) # simplified
            filters.append(comp)
            filter_keys.append(key)
            
    return filters, filter_keys

def filter_data(df, filter_values, filter_keys):
    if df.empty:
        print("DEBUG FILTER: DF is empty")
        return [], [], "Dataset is empty."
        
    filtered_df = df.copy()
    initial_count = len(filtered_df)
    log_messages = [f"Total items: {initial_count}"]
    
    for key, val in zip(filter_keys, filter_values):
        if val == "Any" or val is None or val == []:
            continue
            
        # Check type in DF
        if key not in filtered_df.columns:
            continue
            
        before_count = len(filtered_df)
        
        # Boolean logic
        if isinstance(val, str) and val in ["True", "False"]:
            bool_val = (val == "True")
            filtered_df = filtered_df[filtered_df[key].astype(bool) == bool_val]
            
        # Multiselect logic (list of strings)
        elif isinstance(val, list) and len(val) > 0:
            # Check if "N/A" is selected
            include_na = "N/A" in val
            # Filter out "N/A" from the search values
            search_vals = [v for v in val if v != "N/A"]
            
            # If nothing left and not including NA? (should rely on list logic)
            # But wait, if val was just ["N/A"], search_vals is [].
            # If val was [], we continued earlier (SKIP logic).
            
            mask = pd.Series(False, index=filtered_df.index)
            
            if search_vals:
                mask |= filtered_df[key].astype(str).isin(search_vals)
            
            if include_na:
                # NaNs or empty strings
                mask |= filtered_df[key].isna() | (filtered_df[key] == "") | (filtered_df[key].astype(str).str.strip() == "")
                
            filtered_df = filtered_df[mask]
            
        # Slider logic (number)
        elif isinstance(val, (int, float)):
             if key in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df[key]):
                 if val > filtered_df[key].min():
                     filtered_df = filtered_df[filtered_df[key] >= val]
    
        after_count = len(filtered_df)
        dropped = before_count - after_count
        if dropped > 0:
            log_messages.append(f"❌ {key}: -{dropped} items")
    
    final_count = len(filtered_df)
    log_messages.append(f"✅ Remaining: {final_count}")
    
    debug_str = " | ".join(log_messages)
    # print(f"DEBUG FILTER: {debug_str}")
                     
    # Return list of tuples (image_path, caption/filename)
    gallery_data = []
    indices = []
    for idx, row in filtered_df.iterrows():
        # format: (image path, label)
        gallery_data.append((row['image_path'], row['filename']))
        indices.append(idx)
        
    return gallery_data, indices, debug_str

# Generate generic components helper (unused now but keeping for safety if referenced)
# Actually, the previous 'create_filter_components' seems to be above this function in the file.
# The stuck code I pasted included 'with gr.Column(): ...' which was totally out of place at module level too?
# Ah, I replaced 'filter_data' ... wait. 
# The previous `replace_file_content` replaced `filter_data` AND some code below it with a nested version.
# The code below `filter_data` in the original file (before my bad edit) was global level functions or the main block?
# Let's just fix `filter_data`.

# Main App
with gr.Blocks(title="Dynamic Dataset Curator") as demo:
    
    # State
    df_state = gr.State(pd.DataFrame())
    schema_state = gr.State({})
    filter_keys_state = gr.State([])
    visible_indices_state = gr.State([]) # Indices of currently shown images
    selected_indices_state = gr.State(set()) # Indices of selected images
    
    with gr.Row():
        # sidebar
        with gr.Column(scale=1, min_width=300):
            gr.Markdown("## Setup")
            schema_input = gr.Textbox(label="Schema JSON Path", value="/opt/media-pipeline/dataset-prep/06-caption/client/v5_detailed_json.txt", placeholder="/path/to/template.json")
            dataset_input = gr.Textbox(label="Dataset Directory", value="/data/characters/Aria/Assets/Datasets/training_v2", placeholder="/path/to/data")
            load_btn = gr.Button("Load Dataset", variant="primary")
            status_msg = gr.Markdown("Ready")
            
            gr.Markdown("## Filters")
            filter_status = gr.Markdown(value="Waiting for data...")
            # Container for dynamic filters
            # We use a wrapper column/group rendered via @gr.render if available or just update visibility
            # Since strict @gr.render is new, verify if we can use it. 
            # If not, we define a fixed number of slots or use a single component that takes JSON?
            # Standard approach without render: pre-define generic components.
            # Efficient approach: Use gr.Column() and append children? Not possible at runtime easily without render.
            # Let's use `gr.Group` and populate it using a function that returns a list of components?
            # Gradio < 4: Changing layout is hard.
            # Gradio >= 4: `gr.Render`
            # For this 'Task', I'll assume I can't use complex dynamic layouts easily properly without potentially breaking.
            # Safe bet: Just generic filters? No, requirment is "Dinamik Yapı".
            # I will assume Gradio 4+ (since I just installed it fresh).
            
            @gr.render(inputs=[schema_state, df_state])
            def render_filters(schema, df):
                if not schema:
                    gr.Markdown("No filters available (no schema loaded)")
                    return
                    
                gr.Markdown(f"### Generated {len(schema)} Filters")
                
                # Create components
                filter_comps = []
                keys = []
                
                with gr.Column():
                    for key, info in schema.items():
                        # Calculate counts if df is available
                        counts = {}
                        if not df.empty and key in df.columns:
                            try:
                                counts = df[key].value_counts().to_dict()
                            except:
                                pass # ignore errors in counting

                        if info['type'] == 'bool':
                            # Choices with counts: [("True (N)", "True"), ("False (M)", "False")]
                            t_count = counts.get(True, 0)
                            f_count = counts.get(False, 0)
                            choices = [(f"True ({t_count})", "True"), (f"False ({f_count})", "False")]
                            
                            c = gr.CheckboxGroup(label=key, choices=choices, value=[], interactive=True)
                        
                        elif info['type'] == 'string':
                            opts = info.get('options', [])[:100] # Increased limit slightly
                            # Clean options
                            opts = [str(o).strip() for o in opts if str(o).strip()]
                            unique_opts = sorted(list(set(opts)))
                            
                            # Calculate missing explicitly
                            missing_count = 0
                            if not df.empty and key in df.columns:
                                missing_count = df[key].isna().sum()
                                # Also count empty strings if not already caught by isna
                                # (forcing str might allow checking for "")
                                missing_count += (df[key].astype(str).str.strip() == "").sum()
                                # Ensure we don't double count if NaN was cast to 'nan' then strip? 
                                # Best to rely on isna().
                                # Actually safely:
                                # mask_na = df[key].isna() | (df[key].astype(str).str.strip() == "") | (df[key].astype(str).str.lower() == "nan")
                                # missing_count = mask_na.sum()
                                
                            # Safe missing count recalculation
                            try:
                                if not df.empty and key in df.columns:
                                    # Basic missing
                                    mask = df[key].isna()
                                    # Empty strings
                                    if pd.api.types.is_string_dtype(df[key]) or pd.api.types.is_object_dtype(df[key]):
                                        mask |= (df[key] == "") | (df[key].astype(str).str.strip() == "")
                                    missing_count = mask.sum()
                            except:
                                pass

                            # Format choices with counts
                            final_choices = []
                            for opt in unique_opts:
                                count = counts.get(opt, 0)
                                final_choices.append((f"{opt} ({count})", opt))
                            
                            if missing_count > 0:
                                final_choices.append((f"N/A ({missing_count})", "N/A"))
                                
                            c = gr.CheckboxGroup(label=key, choices=final_choices, value=[], interactive=True)
                            
                        elif info['type'] == 'number':
                             mn, mx = info.get('min', 0), info.get('max', 100)
                             c = gr.Slider(label=key, minimum=mn, maximum=mx, value=mn)
                        
                        filter_comps.append(c)
                        keys.append(key)
                
                def on_change(*values):
                    return filter_data(df, values, keys)

                for comp in filter_comps:
                    comp.change(on_change, inputs=filter_comps, outputs=[gallery, visible_indices_state, filter_status])

        # Main
        with gr.Column(scale=3):
            gr.Markdown("## Gallery")
            gallery = gr.Gallery(label="Images", columns=4, allow_preview=True, object_fit="contain", interactive=True)
            
            with gr.Row():
                selection_info = gr.Markdown("0 items selected")
                select_all_btn = gr.Button("Select All Visible")
                clear_sel_btn = gr.Button("Clear Selection")

            gr.Markdown("## Export")
            target_dir_input = gr.Textbox(label="Target Directory")
            with gr.Row():
                export_btn = gr.Button("Export Selected Images", variant="primary")
                stats_btn = gr.Button("Export Filtered Stats (JSON)")
            
            export_status = gr.Markdown("")
        
    # --- Event Handlers ---
    
    def on_load(schema_path, data_path):
        sch, df, msg, keys = load_and_process(schema_path, data_path)
        # Initialize gallery with all data
        # We need to construct initial values matching what render_filters will create
        init_vals = []
        if sch:
            for k in keys:
                t = sch[k]['type']
                if t == 'bool':
                    init_vals.append([])
                elif t == 'string':
                    init_vals.append([]) # Empty list for multiselect
                else:
                    init_vals.append(sch[k].get('min', 0))

        gal_data, indices, debug_log = filter_data(df, init_vals, keys)
        # We can ignore debug_log here or use it
        return df, sch, keys, msg, gal_data, indices, debug_log

    def generate_statistics(df, visible_indices, target_dir):
        if df.empty or not visible_indices:
             return "No data to analyze."
             
        # Filter DF
        try:
             # visible_indices is a list of valid indices
             target_df = df.loc[visible_indices]
        except Exception as e:
             return f"Error filtering data: {e}"
        
        stats = {}
        stats["_total_count"] = len(target_df)
        
        for col in target_df.columns:
            if col in ["json_path", "image_path", "filename"]:
                continue
                
            try:
                # Value counts with NaNs
                # Convert to dict
                vc = target_df[col].value_counts(dropna=False).to_dict()
                # Clean keys (strings)
                clean_vc = {str(k): v for k, v in vc.items()}
                stats[col] = clean_vc
            except Exception as e:
                stats[col] = f"Error: {e}"
                
        # Save to JSON
        import json
        out_path = os.path.join(target_dir, "dataset_stats.json")
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=4, ensure_ascii=False)
            return f"Stats saved to {out_path}"
        except Exception as e:
            return f"Error saving stats: {e}"

    load_btn.click(
        on_load, 
        inputs=[schema_input, dataset_input], 
        outputs=[df_state, schema_state, filter_keys_state, status_msg, gallery, visible_indices_state, filter_status]
    )
    
    # Selection Handling
    # Gallery .select event returns SelectData(index, value)
    def on_select(evt: gr.SelectData, visible_indices, current_selection):
        # visible_indices maps valid visual index -> DF index
        # evt.index is the index in the gallery
        if evt.index < len(visible_indices):
            real_idx = visible_indices[evt.index]
            if real_idx in current_selection:
                current_selection.remove(real_idx)
            else:
                current_selection.add(real_idx)
        return current_selection, f"{len(current_selection)} terms selected"

    gallery.select(
        on_select,
        inputs=[visible_indices_state, selected_indices_state],
        outputs=[selected_indices_state, selection_info]
    )

    # Export
    def on_export(df, selection, target):
        if not selection:
            return "Nothing selected."
        
        # Filter DF by selection
        selected_df = df.loc[list(selection)]
        count, errors = copy_files(selected_df, target)
        
        if errors:
            return f"Copied {count} files. Errors: {errors[:3]}..."
        return f"Successfully exported {count} pairs."

    export_btn.click(
        on_export,
        inputs=[df_state, selected_indices_state, target_dir_input],
        outputs=[export_status]
    )

    stats_btn.click(
        generate_statistics,
        inputs=[df_state, visible_indices_state, target_dir_input],
        outputs=[export_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, allowed_paths=["/"])
