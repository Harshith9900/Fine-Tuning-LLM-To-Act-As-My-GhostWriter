import os 
import json 

longest = 0 
chapter_num = None

DATA_DIR = "../DATA/gemini_data"

files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])

for file in files : 
    file = os.path.join(DATA_DIR,file)

    with open(file ,"r" , encoding="utf-8") as f : 
        data = json.load(f) 

    if data["word_count"] > longest : 
        longest = data["word_count"]
        chapter_num = data["chapter_number"]

print(longest) 
print("\n")
print(chapter_num)
