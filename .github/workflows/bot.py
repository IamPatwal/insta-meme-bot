"""Insta meme bot: Gemini writes the meme, Pillow draws it, Instagram API posts it."""
import os, sys, json, random, time, datetime, textwrap
import requests
from PIL import Image, ImageDraw, ImageFont

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_HANDLE = os.environ.get("IG_HANDLE", "")          # optional, e.g. @mypage
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SIZE = 1080

TOPICS = ["college life", "office life and Monday blues", "exam season", "shaadi season",
          "chai and Maggi", "Mumbai local trains", "Bangalore traffic", "UPI and money",
          "cricket fans", "reel addiction and doomscrolling", "gym motivation that never lasts",
          "Indian parents", "delivery apps (Zomato, Swiggy, Blinkit)", "sigma / aura / rizz slang",
          "overthinking at 3 AM", "relatives asking about your salary", "AI and ChatGPT taking jobs",
          "WFH vs return to office", "hostel life", "monsoon and Indian roads"]

def history():
    try: return json.load(open("posted.json"))
    except Exception: return []

def ask_gemini():
    recent = [h["top"] + " / " + h["bottom"] for h in history()[-40:]]
    topic = random.choice(TOPICS)
    prompt = f"""You run a viral Indian Instagram meme page. Write ONE fresh meme.
Style: Indian brain rot + new-age Gen-Z humour, Hinglish in Roman script, absurd, relatable, punchy.
Topic idea: {topic}.
Rules: original jokes only. No real people's names, no politics, religion, caste, abuse or sexual content.
Keep "top" under 90 characters and "bottom" (the punchline) under 90 characters. No emojis inside top/bottom.
Caption: one short fun line with 1-3 emojis, then a blank line, then 8-12 relevant hashtags.
Do NOT repeat or closely copy these recent memes: {recent}
Return ONLY JSON: {{"top": "...", "bottom": "...", "caption": "..."}}"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(url, params={"key": GEMINI_KEY}, timeout=60, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.1}})
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)

def wrap_fit(draw, text, box_w, box_h, start=96, min_size=36):
    size = start
    while size >= min_size:
        font = ImageFont.truetype(FONT, size)
        lines, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if draw.textlength(test, font=font) <= box_w: line = test
            else: lines.append(line); line = word
        lines.append(line)
        h = len(lines) * int(size * 1.25)
        if h <= box_h: return font, lines, int(size * 1.25)
        size -= 4
    return font, lines, int(size * 1.25)

def draw_block(draw, text, cx, top, box_w, box_h, fill, start=96):
    font, lines, lh = wrap_fit(draw, text, box_w, box_h, start)
    y = top + (box_h - lh * len(lines)) // 2
    for l in lines:
        w = draw.textlength(l, font=font)
        draw.text((cx - w / 2, y), l, font=font, fill=fill)
        y += lh

def render(top, bottom, path):
    layout = random.choice(["card", "split"])
    if layout == "card":
        bg, accent = random.choice([("#111111", "#FFD400"), ("#6A00F4", "#FFFFFF"), ("#0B6E4F", "#FFE066"), ("#E63946", "#FFFFFF"), ("#0077B6", "#FFE066")])
        img = Image.new("RGB", (SIZE, SIZE), bg); d = ImageDraw.Draw(img)
        draw_block(d, top, SIZE // 2, 90, SIZE - 160, 400, "#FFFFFF")
        draw_block(d, bottom, SIZE // 2, 530, SIZE - 160, 400, accent, 88)
    else:
        img = Image.new("RGB", (SIZE, SIZE), "#FFFFFF"); d = ImageDraw.Draw(img)
        d.rectangle([0, SIZE // 2, SIZE, SIZE], fill="#111111")
        draw_block(d, top, SIZE // 2, 40, SIZE - 140, SIZE // 2 - 80, "#111111", 84)
        draw_block(d, bottom, SIZE // 2, SIZE // 2 + 40, SIZE - 140, SIZE // 2 - 80, "#FFD400", 84)
    if IG_HANDLE:
        f = ImageFont.truetype(FONT, 28)
        d.text((SIZE - 40 - d.textlength(IG_HANDLE, font=f), SIZE - 56), IG_HANDLE, font=f, fill="#888888")
    img.save(path, quality=92)

def make():
    m = ask_gemini()
    name = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S") + ".jpg"
    path = f"images/{name}"
    os.makedirs("images", exist_ok=True)
    render(m["top"], m["bottom"], path)
    json.dump({"file": path, "caption": m["caption"]}, open("next_post.json", "w"))
    h = history(); h.append({"top": m["top"], "bottom": m["bottom"], "file": path})
    json.dump(h[-200:], open("posted.json", "w"), indent=1, ensure_ascii=False)
    print("made", path)

def post():
    n = json.load(open("next_post.json"))
    image_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{n['file']}"
    for _ in range(12):                                   # wait until GitHub serves the image
        if requests.head(image_url, timeout=20).status_code == 200: break
        time.sleep(5)
    base = f"https://graph.instagram.com/v26.0/{IG_USER_ID}"
    auth = {"Authorization": f"Bearer {IG_TOKEN}"}
    r = requests.post(f"{base}/media", headers=auth, timeout=60, data={"image_url": image_url, "caption": n["caption"]})
    print(r.text); r.raise_for_status()
    cid = r.json()["id"]
    for _ in range(12):                                   # wait for FINISHED
        s = requests.get(f"https://graph.instagram.com/v26.0/{cid}", headers=auth, params={"fields": "status_code"}, timeout=30).json()
        if s.get("status_code") == "FINISHED": break
        time.sleep(5)
    r = requests.post(f"{base}/media_publish", headers=auth, timeout=60, data={"creation_id": cid})
    print(r.text); r.raise_for_status()
    print("POSTED", r.json())

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "make": make()
    elif mode == "post": post()
    elif mode == "demo":
        render("Nobody: absolutely nobody:", "Me at 2 AM planning my entire personality change", "demo.jpg")
