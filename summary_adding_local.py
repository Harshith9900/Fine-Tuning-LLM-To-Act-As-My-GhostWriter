import os
import json
import time
import logging
from tqdm import tqdm
from datetime import timedelta
import ollama

DATA_DIR= "data_local"
MODEL_NAME = "qwen2.5:32b"
NUM_CTX = 8192 # enough context length to hold 1500-2000 words 
MAX_RETRIES = 3
MAX_OVERLAP_RATIO = 0.40

LOG_FILE = "test_run.log"
FAIL_LOG_FILE = "final_test_run.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", # (1) YYYY-MM-DD HH:MM:SS,mmm , ()s used to convert it to string (2) severity level (3) whatever i am message success failure whatever
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"), # better to use utf-8 encoding just in case llm gives some random symbol
        # i prefer all my terminal messages are my log entries than print statements 
        logging.StreamHandler()
    ]
)

log = logging.getLogger(__name__) # to tag the log message from which python file it came from , well i dont have mutliple python files cooperating yet so using main should be fine but whatever name also works 

# this is the two network libraries of ollama httpx and httpcore 
# using .WARNING to they give only stuff like [INFO] [WARNING] [ERROR] i dont want log messages like http request local host whatever 
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# using gemini to give my prompt llms are better acting giving prompts to llms afterall 
DRAFT_PROMPT = """
You are an assistant preparing a machine learning dataset. 
Your task is to read the provided Dark Fantasy chapter and reverse-engineer it into a 500-750 word rough draft.

STRICT RULES:
1. DE-STYLIZE COMPLETELY: Strip away all of the author's atmospheric prose, sensory details, and stylistic embellishments. Write in completely flat, dry, factual sentences. 
2. NO PLAGIARISM: Do not copy any phrases longer than 4 words from the original text. You must paraphrase the events entirely in your own words.
3. RETAIN THE MEAT: Ensure every major micro-action, dialogue exchange, and plot progression is captured in the draft, just written in a boring, unpolished way.
4. WORD COUNT: Try to keep the final draft word count between 500 and 700 words .

Output ONLY the raw text of the rough draft. Do not include JSON formatting, titles, or commentary.
"""

def generate_rough_draft(chapter_text, temp=0.55):
    user_content = f"Original Reference Text:\n{chapter_text}"
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            # my prompt to qwen 
            {'role': 'system', 'content': DRAFT_PROMPT},
            # qwen output 
            {'role': 'user', 'content': user_content}
        ],
        options={'temperature': temp, 'num_ctx': NUM_CTX}
    )
    # from the json file outputed by qwen we are extracting the message and content keys cuz thats what we are interested in , not token counts or/and timestamps actually i am interested but i dont have enough time to play with those metrics 
    draft = response['message']['content'].strip()
    if not draft:
        # stoping code using raise and using value error in case local llm glitches and generates blank answer and % overlap lets it go through into the dataset
        raise ValueError("Model generated an empty draft.")
    return draft

# to see if ai got lazy and copy pasted some sentences 
def get_shingles(text, n=8):
    # had gemini give me this plagiarism checker my prev one used to consider words with punctuation eg ( hello, and hello ) as diff words and used to pass it on to the data set when i used to proof read it , it was so similar 😭
    words = [w.strip(".,!?:;\"'()[]{}").lower() for w in text.split()]
    words = [w for w in words if w]
    # if the model gives less than 8 words before crashing then its not possible to create 8 word chunk and trust me the index error was pain to debug , half the code is just condom against errors (std) atp 
    if len(words) < n:
        # returning empty set 
        return set()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}

# this doesnt need a explanation 
def calculate_overlap(draft, original, n=4):
    draft_shingles = get_shingles(draft, n)
    if not draft_shingles:
        return 0.0
    original_shingles = get_shingles(original, n)
    shared = draft_shingles & original_shingles
    return len(shared) / len(draft_shingles)

def process_chapter(filepath, filename):
    with open(filepath, "r", encoding="utf-8") as f:
        # python converts the json into a dictionary ( which i am just naming data ) so later on i would be using the keys were my chapter content is stored to retreive that text
        data = json.load(f)

    # Now only checking if rough_draft exists and to check if its processed chapter or not 
    if "rough_draft" in data and not data.get("_needs_review"):
        return "skipped"

    attempts = 0
    # if u think 0.50 is too high of a temp wait until u see my +0.1 after every failure off not passing overlap check
    temperature = 0.50

    while attempts < MAX_RETRIES :
        attempts += 1
        try:
            draft = generate_rough_draft(data["text"], temp=temperature)

            # Length check
            word_count = len(draft.split())
            if word_count < 350:
                log.warning(f"[Length] {filename}: {word_count} words (too short, want >= 350). Retrying...\n")
                temperature += 0.05 
                continue

            #overlap Check 
            overlap = calculate_overlap(draft, data["text"])
            if overlap > MAX_OVERLAP_RATIO:
                log.warning(f"[Overlap High] {filename}: {overlap:.1%} > {MAX_OVERLAP_RATIO:.0%}. Retrying with higher temp...\n")
                temperature += 0.10  # lol i am crazy i know 
                continue

            # Saving the clean draft directly to the my data dictionary
            data["rough_draft"] = draft
            # if it succesfully ran we dont need the needs review and error keys so we can remove them 
            data.pop("_needs_review", None)
            data.pop("_error", None)

            with open(filepath, "w", encoding="utf-8") as f:
                # saving it back as a json file cuz thats what i would be working with , and turning off ascii so it doesnt overwrite utf-8 encoding and obv using indent = 2 to make it more readable for me 
                json.dump(data, f, ensure_ascii=False, indent=2)

            log.info(f"[✓ OK] {filename} (Overlap: {overlap:.1%}, Attempt: {attempts})\n")
            return "success"

        except Exception as e:
            log.warning(f"  [Retry {attempts}/{MAX_RETRIES}] Engine Error: {e}\n")
            time.sleep(1)

    # FAIL LOGGING
    data["_needs_review"] = True
    data["_error"] = f"Exceeded {MAX_RETRIES} attempts. Overlap constraints failed.\n"
    
    data.pop("rough_draft", None)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    with open(FAIL_LOG_FILE, "a", encoding="utf-8") as fail_log:
        fail_log.write(f"{filename} - Error: {data['_error']}\n")
        
    return "failed"

def main():
    # make sure to give the right data_dir so you dont corrupt your data and if also maintain another copy of the raw data so you dont have to rescrap everything again from scratch (dont ask me how i know this )
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])
    # loggin it in this the above and below lines of code are mostly for the main final dataset for test data sets these are redunant
    log.info(f"Loaded {len(files)} files from {DATA_DIR} using {MODEL_NAME}")

    processed, failed, skipped = 0, 0, 0
    start_time = time.time()
    chapters_since_long_break = 0 # only counts real work (success + failed)

    # i really love tqdm i can see my progress visually rather than 5/10 i do that also but i love that bar filling thing which it shows its kinda over the top thing i do for myself also it gives a eta type thing which is not so really correct but can also use enumerate should work fine 
    pbar = tqdm(files, desc="Processing Chapters", unit="ch")
    for filename in pbar:
        filepath = os.path.join(DATA_DIR, filename)
        status = process_chapter(filepath, filename)

        if status == "success":
            processed += 1
            chapters_since_long_break += 1
        elif status == "failed":
            failed += 1
            chapters_since_long_break += 1
        else:
            skipped += 1

        done = processed + failed + skipped
        elapsed = time.time() - start_time

        # skipping a chapter takes like very less time but if i include skipped in deno of avg_time then it would inflate the time needed to process through a chapter and make it much seem much lower to process chps than actual. 

        if (processed + failed ) > 0:
            avg_time = elapsed / (processed + failed)
            eta = timedelta(seconds=int(avg_time * (len(files) - done)))
            pbar.set_postfix(ok=processed, fail=failed, skip=skipped, eta=str(eta))

        # a short break after a chapter is processed 
        if status != "skipped":
            time.sleep(30)

        # a huge temperature reset for both aluminium case and the hardware 
        if chapters_since_long_break % 100 == 0  and chapters_since_long_break > 0 : 
            log.info("processed 100 chapters taking a 10 min break.....")
            time.sleep(600) 
            # fingers crossed running the code.

    log.info(f"\nRun Complete: {processed} succeeded, {failed} flagged, {skipped} skipped,{done} DONE .")

if __name__ == "__main__":
    main()
