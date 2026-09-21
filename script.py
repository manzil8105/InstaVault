import os
import re
import sys
import time
from pathlib import Path
from typing import List, Literal
from PIL import Image
import pillow_heif
from pydantic import BaseModel, Field

# google SDK
from google import genai
from google.genai import types

# enable apple HEIC image support
pillow_heif.register_heif_opener()

#  config

# Replace with actual Gemini API Key
client = genai.Client(api_key="key")

BASE_DIR = Path.cwd()
DATASET_DIR = BASE_DIR / "dataset_mk_8105" #give dataset name
NOTES_DIR = BASE_DIR / "Obsidian_Notes" # notes folder name
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".heic", ".heif"}

# schemas , you can edit your own categories 
CategoryType = Literal["Hpm", "stem", "cba", "self development", "others"]
ALLOWED_TAGS = [
    "history", "phi", "psy", "pol", "myth", "science", "tech", "engineering", 
    "math", "coding", "astrophysics", "compSci", "dataScience", "mL", "scifi", 
    "darkFantasy", "realisticCinema", "cinema", "books", "graphicNovels", 
    "anime", "television", "superhero", "csd", "health", "skillDev", "gym", 
    "food", "nutritional", "studying", "routines", "sda", "project", "Links", 
    "academic", "researchPaper", "quant", "finance"
]

class ExtractedNote(BaseModel):
    title: str = Field(description="A highly meaningful and specific title based on the content.")
    category: CategoryType = Field(description="The primary category folder.")
    tags: List[str] = Field(description="A list of relevant tags from the allowed whitelist.")
    organized_info: str = Field(
        description="The extracted information logically organized. NO SUMMARIES. NO INTRODUCTIONS. "
                    "Just transcribe and structure the raw information, steps, quotes, or article text."
    )

class FolderAnalysis(BaseModel):
    notes: List[ExtractedNote] = Field(
        description="List of notes to generate. If the images contain multiple completely separate pieces "
                    "of content (e.g., 5 completely different book recommendations), output 5 separate notes. "
                    "If it is a single continuous article or topic, output 1 note."
    )

# extraction prompt
EXTRACTION_PROMPT = f"""
You are a precise data extraction and organization engine. 
Analyze the provided images and extract EVERY bit of useful information.

CRITICAL RULES:
1. NO SUMMARIES OR EXPLANATIONS: Do not write things like "This post is about..." or "This image shows...". 
   Just organize the collected info directly. Transcribe articles, list roadmap steps sequentially, extract quotes verbatim.
2. DO NOT HALLUCINATE: If text is unclear, mark it as [Uncertain]. Do not invent URLs, authors, or titles.
3. MULTIPLE TOPICS: If the images recommend 5 different books, return 5 separate note objects. If it's one long article across screenshots, return 1 note object. Combine duplicate information cleanly.
4. TAGS: Use only tags from this exact list: {', '.join(ALLOWED_TAGS)}
5. CATEGORIES: Choose exactly one: 'Hpm', 'stem', 'cba', 'self development', or 'others'.
"""

#  UTILS
def sanitize_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", title)
    return re.sub(r"\s+", " ", cleaned).strip()[:85] or "Untitled Note"

def process_folder(folder_num: str):
    target_dir = DATASET_DIR / folder_num
    
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Folder '{folder_num}' does not exist in {DATASET_DIR.name}")
        return

    # Load images
    image_paths = [p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    
    if not image_paths:
        print(f"No supported images found in folder '{folder_num}'.")
        return
        
    print(f"Processing folder {folder_num} ({len(image_paths)} images)...")
    
    payload = [EXTRACTION_PROMPT]
    rel_image_paths = []
    
    for img_path in sorted(image_paths):
        try:
            pil_img = Image.open(img_path).convert("RGB")
            pil_img.thumbnail((2048, 2048)) 
            payload.append(pil_img)
            rel_image_paths.append(f"{DATASET_DIR.name}/{folder_num}/{img_path.name}")
        except Exception as e:
            print(f"Failed to load image {img_path.name}: {e}")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Modern SDK Call
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=payload,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FolderAnalysis,
                    temperature=0.0, 
                )
            )
            
            analysis = FolderAnalysis.model_validate_json(response.text)
            
            if not analysis.notes:
                print("No useful information extracted.")
                return

            for note in analysis.notes:
                # make category folder
                cat_dir = NOTES_DIR / note.category
                cat_dir.mkdir(parents=True, exist_ok=True)
                
                # format tags
                formatted_tags = " ".join([f"[[{tag}]]" for tag in note.tags])
                
                # format image paths
                formatted_images = "\n".join([f"- {path}" for path in rel_image_paths])
                
                # build markdown strictly to user specification
                md_content = f"# {note.title}\n\n"
                md_content += f"## Tags\n{formatted_tags}\n\n"
                md_content += f"## Info:\n{note.organized_info}\n\n"
                md_content += f"## Original Image\n{formatted_images}\n"
                
                filename = f"{sanitize_filename(note.title)}.md"
                (cat_dir / filename).write_text(md_content, encoding="utf-8")
                
            break # success! break out of the retry loop.
            
        except Exception as e:
            error_msg = str(e)
            # catch server overloads (503) and rate limits (429)
            if "503" in error_msg or "UNAVAILABLE" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5 # waits 5s, then 10s, then 15s...
                    print(f"Google servers are busy. Retrying in {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"Extraction failed: Google API remains unavailable after {max_retries} attempts. Try again later.")
            else:
                # if it's a genuine script error (not a traffic jam), fail immediately
                print(f"Extraction failed: {error_msg}")
                break

#  main CLI
def main():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    
    while True:
        try:
            user_input = input("Enter folder number to process (or type 'exit' to quit): ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
                
            if not user_input:
                continue
                
            process_folder(user_input)
            print("done")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()