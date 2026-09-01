import os 
import json

DATA_DIR = "../DATA/gemini_data"


files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])

for filename in files:
    filepath = os.path.join(DATA_DIR, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False
    

    if "rough_draft" in data:
        del data["rough_draft"]
        modified = True

    if "outline" in data:
        del data["outline"]
        modified = True

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Cleaned] {filename}")

print("cleaning done")
