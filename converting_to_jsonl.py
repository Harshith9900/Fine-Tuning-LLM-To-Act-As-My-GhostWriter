import os
import json
import random
import glob

# Configuration
INPUT_DIR = "./gemini_data" 
OUTPUT_DIR = "./compile_data"
VALIDATION_SPLIT_COUNT = 260
SYSTEM_PROMPT = "Expand this rough draft into a full chapter in the style of webnovel novel:\n\n"


dataset = []
    
file_paths = glob.glob(os.path.join(INPUT_DIR, "chapter_*.json"))
print(f" Processing {len(file_paths)} chapter files... ")
    
for files in file_paths:
    with open(files, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
                
            draft = data.get("rough_draft", "").strip()
            final_text = data.get("text", "").strip()
                
            if not draft or not final_text:
                continue
                
            mlx_format = {
                "messages": [
                    {"role": "user", "content": f"{SYSTEM_PROMPT}{draft}"},
                    {"role": "assistant", "content": final_text}
                ]
            }
            dataset.append(mlx_format)
                
        except json.JSONDecodeError:
            print(f"Error reading {files}, skipping.")
                
random.shuffle(dataset)
    
# Spliting the dataset
valid_data = dataset[:VALIDATION_SPLIT_COUNT]
train_data = dataset[VALIDATION_SPLIT_COUNT:]
    
# valid.jsonl
valid_path = os.path.join(OUTPUT_DIR, "valid.jsonl")
with open(valid_path, "w", encoding="utf-8") as f:
    for item in valid_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
# train.jsonl
train_path = os.path.join(OUTPUT_DIR, "train.jsonl")
with open(train_path, "w", encoding="utf-8") as f:
    for item in train_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
print(f"Created validation set with {len(valid_data)} examples.")
print(f"Created training set with {len(train_data)} examples.")

