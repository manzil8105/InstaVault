import os
import re
import time
import subprocess
import hashlib
from pathlib import Path
from typing import List, Literal
from pydantic import BaseModel, Field

from google import genai
from google.genai import types

#  config 
# input actual gemini api key 
client = genai.Client(api_key="key")

BASE_DIR = Path.cwd()
NOTES_DIR = BASE_DIR / "Obsidian_Notes"
# reusing temp_reels 
TEMP_DIR = BASE_DIR / "temp_reels" 

#  schemas 
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
                    "Just transcribe and structure the raw information, steps, quotes, or spoken text."
    )

class FolderAnalysis(BaseModel):
    notes: List[ExtractedNote]

#   extraction prompt 
EXTRACTION_PROMPT = f"""
You are a precise data extraction and organization engine. 
Analyze the provided video and extract EVERY bit of useful information from both the spoken audio and on-screen text.

CRITICAL RULES:
1. NO SUMMARIES OR EXPLANATIONS: Do not write things like "This video is about...". 
   Just organize the collected info directly. Transcribe roadmaps, lists, steps, quotes, or concepts verbatim.
2. DO NOT HALLUCINATE: Do not invent URLs, authors, or titles.
3. MULTIPLE TOPICS: If the video recommends 5 different books, return 5 separate note objects. If it's one continuous tutorial, return 1 note object.
4. TAGS: Use only tags from this exact list: {', '.join(ALLOWED_TAGS)}
5. CATEGORIES: Choose exactly one: 'Hpm', 'stem', 'cba', 'self development', or 'others'.
"""

#  UTILS 
def sanitize_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", title)
    return re.sub(r"\s+", " ", cleaned).strip()[:85] or "Untitled Note"

def get_safe_id(url: str) -> str:
    """Creates a safe, 10-character hash for messy Facebook URLs."""
    return hashlib.md5(url.encode()).hexdigest()[:10]

def download_fb_stateless(url: str, post_id: str) -> str:
    """Downloads the MP4 directly using stateless scraping."""
    out_path = TEMP_DIR / f"{post_id}.mp4"
    
    print(f"  -> Downloading MP4...")
    cmd = [
        "yt-dlp",
        url,
        "-f", "b",
        "--no-cookies",
        "--no-warnings",
        "-o", str(out_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if not out_path.exists():
        raise Exception(f"Failed to fetch video. It may be private or restricted.\nLog: {result.stderr.strip()}")
        
    return str(out_path)

def process_link(url: str):
    clean_url = url.split("&")[0].strip() # Strip tracking parameters common in FB links
    post_id = get_safe_id(clean_url)
    
    print(f"\nProcessing: {clean_url}")
    video_path = None
    uploaded_file = None
    
    try:
        # download
        video_path = download_fb_stateless(clean_url, post_id)
        
        # upload to Gemini
        print("  -> Uploading to Gemini API...")
        uploaded_file = client.files.upload(file=video_path)
        
        # wait for Google's servers
        print("  -> Waiting for Gemini to analyze the video frames and audio...")
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise Exception("Gemini failed to process the video file.")
            
        # extract data with exponential backoff
        print("  -> Extracting structured data...")
        max_retries = 5
        analysis = None
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=[EXTRACTION_PROMPT, uploaded_file],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=FolderAnalysis,
                        temperature=0.0,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                )
                
                analysis = FolderAnalysis.model_validate_json(response.text)
                break 
                
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "429" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        print(f"  -> Google servers are busy. Retrying in {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                    else:
                        print(f"  -> [ERROR] Extraction failed: Google API remains unavailable after {max_retries} attempts.")
                        break
                else:
                    print(f"  -> [ERROR] Extraction failed: {error_msg}")
                    break
        
        if not analysis or not analysis.notes:
            print("  -> No useful information extracted.")
            return

        # make otes
        for note in analysis.notes:
            cat_dir = NOTES_DIR / note.category
            cat_dir.mkdir(parents=True, exist_ok=True)
            
            formatted_tags = " ".join([f"[[{tag}]]" for tag in note.tags])
            
            md_content = f"# {note.title}\n\n"
            md_content += f"## Tags\n{formatted_tags}\n\n"
            md_content += f"## Info:\n{note.organized_info}\n\n"
            md_content += f"## Source Video\n- {clean_url}\n"
            
            filename = f"{sanitize_filename(note.title)}.md"
            (cat_dir / filename).write_text(md_content, encoding="utf-8")
            
            print(f"  -> Generated Note: [{note.category}] {filename}")
            
    except Exception as e:
        print(f"  -> [ERROR] {e}")
        
    finally:
        # cleanup
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except:
                pass

#  main CLI 
def main():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    print("========================================")
    print("  FACEBOOK VIDEO -> OBSIDIAN PIPELINE   ")
    print("========================================")
    
    while True:
        try:
            user_input = input("\nPaste Facebook link(s) separated by spaces (or type 'exit'): ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
                
            if not user_input:
                continue
            
            links = [link for link in user_input.split() if "facebook.com" in link.lower() or "fb.watch" in link.lower()]
            
            if not links:
                print("No valid Facebook links detected.")
                continue
                
            for link in links:
                process_link(link)
                
            print("\nBatch complete.")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()