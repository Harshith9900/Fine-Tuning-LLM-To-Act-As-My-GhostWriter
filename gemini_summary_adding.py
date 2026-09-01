import os
import json
import time
import sys
from google import genai
from google.genai import types
from google.genai.errors import APIError

DATA_DIR = "gemini_data"

API_KEYS = [
    "gemini_api_keys"
]


MODEL_TIERS = [    
    # "gemini-3.6-flash",      
    # "gemini-3-flash-preview",
    "gemini-3.5-flash-lite", # 500 RPD
    "gemini-3.1-flash-lite" # 500 RP 
    # "gemini-3.7-flash",
    # "gemini-3.5-flash"
]


key_index = 0
model_index = 0

client = genai.Client(api_key=API_KEYS[key_index])

SYSTEM_PROMPT = """
You are an expert ghostwriter. You are helping build a machine learning dataset to train an AI model in the style of a gritty, dark-fantasy webnovel.
Your task is to read the provided chapter and reverse-engineer it into an unpolished, human-written first draft.

STRICT RULES:
1. MIMIC A HUMAN DRAFT: Write this as if an author is quickly drafting the scene. Include some flowery language, basic sensory details, and natural narrative transitions, but keep it noticeably messier, looser, and less atmospheric than the original gritty text.
2. SHORTHAND SYSTEM UI: When encountering system messages, spell announcements, or stat blocks, write them as rough author notes or shorthand (e.g., "System prompt: received Weaver's mask, divine rank, tool type"). DO NOT use the polished brackets or exact formatting from the original text. The draft must reflect raw notes.
3. NO PLAGIARISM: Paraphrase the narrative events entirely in your own words.
4. RETAIN THE MEAT: Ensure every major micro-action, dialogue beat, and plot progression is captured.
5. WORD COUNT: The final draft MUST be between 500 and 800 words.
6. PRESERVE LORE: Retain all specific proper nouns, power scaling ranks, item names, and artifacts exactly as they appear. 
7. NO ANALYTICAL CONCLUSIONS: When the physical events stop, the draft must instantly stop. Do not write a concluding summary.

Analyze the provided chapter and reverse-engineer it into a rough draft following the strict rules above.
You must output strictly valid JSON using this exact schema:
{
  "rough_draft": "Your rough draft text here"
}
"""

def generate_rough_draft(chapter_text, current_model):
    response = client.models.generate_content(
        model=current_model,
        contents=f"{SYSTEM_PROMPT}\n\nChapter Text:\n{chapter_text}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.35,
        )
    )
    return json.loads(response.text)



print(".......STARTING.......")
print(f"Using Model: [{MODEL_TIERS[model_index]}] | Using Key: [{key_index + 1}/{len(API_KEYS)}]\n")

files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])
processed_count = 0

for filename in files:
    filepath = os.path.join(DATA_DIR, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "rough_draft" in data and data["rough_draft"].strip():
        continue

    print(f"Processing {filename} {data.get("chapter_number")}...")

    while True:
        current_model = MODEL_TIERS[model_index]
        try:
            synthetic_response = generate_rough_draft(data["text"], current_model)

            data["rough_draft"] = synthetic_response.get("rough_draft", "")

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            processed_count += 1
            print(f"[✓] Completed [{filename}] using [{current_model}] ( Using Key {key_index + 1})")

            # sleep to not hit per min limits 4s for flash lite , 15s for flash models
            time.sleep(4) 
            # time.sleep(15)
            break 

        except APIError as e:
            # 429: Quota/RPD limit hit
            if e.code == 429:
                print(f"\n [!] Key {key_index + 1} used up '{current_model}' (429 Limit).")
                
                key_index += 1
                
                if key_index >= len(API_KEYS):
                    print(f"[!] All {len(API_KEYS)} keys exhausted for model '{current_model}'.")
                    model_index += 1
                    key_index = 0  

                    if model_index >= len(MODEL_TIERS):
                        print("\n [❌] ALL KEYS ON ALL MODEL TIERS USED UP.")
                        print(f" Total processed : {processed_count}")
                        sys.exit(0)
                        
                    print(f"[!] Switching Models [{MODEL_TIERS[model_index]}] Using Key 1 ")
                else:
                    print(f"[!] Switching Keys , Using {key_index + 1} of [{current_model}]...")

                # Rebuilding client with the new active key
                client = genai.Client(api_key=API_KEYS[key_index])
                time.sleep(15)
                
            elif e.code == 503:
                print(f"[!] Server overloaded ERROR :503 , sleeping for 20s ...")
                time.sleep(20)
            else:
                print(f"[!] API Error: {e}, sleeping for 15s...")
                time.sleep(15)

        except json.JSONDecodeError:
            print(f"[!] Malformed JSON returned for {filename}, sleeping for 15s...")
            time.sleep(15)

        except Exception as e:
            print(f"[!] Network/Unknown error: {e} , sleeping for 15s...")
            time.sleep(15)

print("\nFinished processing") 
print(f"\nTotal summaries generated:{processed_count}")
