import os
import html
from pathlib import Path


# InstaVault context bundler for further development (whiteList)
 
BASE_DIR = Path.cwd()
OUTPUT_FILE = "vault_context.xml"

#  strict whitelist, Only bundle these exact file types
ALLOWED_EXTENSIONS = {".py"}

# skip directories to speed up scanning
IGNORE_DIRS = {
    "venv", ".git", "__pycache__", 
    "dataset_mk_8105", "raw_media", "temp_reels", "Obsidian_Notes"
}

def get_file_tree(startpath):
    tree_str = ""
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        level = root.replace(str(startpath), '').count(os.sep)
        indent = ' ' * 4 * level
        tree_str += f"{indent}{os.path.basename(root)}/\n"
        
        subindent = ' ' * 4 * (level + 1)
        for f in sorted(files):
            if any(f.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                tree_str += f"{subindent}{f}\n"
    return tree_str

def build_xml():
    xml_content = ["<project>\n"]
    
    # inject the directory Architecture
    xml_content.append("<directory_tree>\n")
    xml_content.append(html.escape(get_file_tree(BASE_DIR)))
    xml_content.append("</directory_tree>\n\n")
    
    # inject the code files
    xml_content.append("<files>\n")
    
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in sorted(files):
            # Enforce the strict whitelist
            if not any(file.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                continue
                
            # skip the bundler itself
            if file in [OUTPUT_FILE, Path(__file__).name]:
                continue
                
            file_path = Path(root) / file
            rel_path = file_path.relative_to(BASE_DIR)
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                xml_content.append(f'<file path="{rel_path}">\n')
                xml_content.append(html.escape(content))
                xml_content.append("\n</file>\n\n")
            except Exception:
                pass 

    xml_content.append("</files>\n")
    xml_content.append("</project>")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(xml_content)
        
    # get file size in KB to verify success
    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"✅ Project context bundled successfully into {OUTPUT_FILE}")
    print(f"📊 Final File Size: {size_kb:.2f} KB")

if __name__ == "__main__":
    build_xml()