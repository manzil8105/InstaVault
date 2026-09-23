# InstaVault

This system takes raw Instagram / facebook reels (link as input) or image dumps (downloaded Insta / facebook images or any image in numbered folders), uses Google's Gemini API to extract the core knowledge, and seamlessly structures it into Obsidian-ready Markdown notes. I take a lot of screenshots and save a lot of reels. If your Insta feed is filled not only with brainrot but also with informational content, you can use this system to organise that knowledge. You can also use the XML file, use AI or yourself, to make a system that analyses a JSON file, a JSON file you can export from Meta, which will contain your saved posts and reel info; use that JSON file to hunt down your saved content, extract info and make high end organised notes. But to do this, it's better to use a high end GPU.

---

## The Initial Setup

**Activate environment:**
`     source venv/bin/activate
    `
**Write active Gemini API key into**

`process_reels.py`
`script.py`.

**Dependencies:**
`ffmpeg` must be installed on Mac (`brew install ffmpeg`)
Python libraries up to date (`pip install -U google-genai yt-dlp pydantic`).

---

## Extracting Video

1. Open terminal and run

```
python process_reels.py
or
process_fb.py
```

2. Paste Instagram or facebook links into the prompt. just one, or drop in 10 at the same time, make sure there is a space between each link. Hit Enter.

3. The script will securely rip the MP4, send it to Gemini, generate structured `.md` files in `Obsidian_Notes`, and instantly delete the heavy MP4 so the hard drive stays clean.

---

## Extracting Images, The Dataset Pipeline

1. Make sure image folders (e.g., `122`, `123`) are inside the `dataset_mk_8105` directory. (or whatever it is named for the user)
2. Run the image script:

   `python script.py`

3. Type the folder number which is to be processed, hit Enter. Gemini will read the screenshots, stitch the context together, and drop the formatted notes into `Obsidian_Notes`.

---

## Upgrading the Code (Using AI)

If you want to add new features or fix a bug, don't copy paste code manually into an AI chat.

1. Run bundler: `python bundle_project.py`
2. This makes a tiny, secure file named `vault_context.xml` containing the `.py` scripts. info
3. Drag and drop that XML file into ChatGPT, Claude, or Gemini. The AI will instantly understand your entire project architecture and give you perfectly tailored code updates.
