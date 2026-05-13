import os
import re
import time
import random
import requests
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from image_gen import generate_image

# ─── ACCOUNTS ────────────────────────────────────────────────────────────────
def load_accounts() -> list[dict]:
    accounts = []
    for i in range(1, 6):
        handle   = os.environ.get(f"BSKY_HANDLE_{i}")
        password = os.environ.get(f"BSKY_PASSWORD_{i}")
        if handle and password:
            accounts.append({"id": i, "handle": handle, "password": password})
    if not accounts:
        print("❌ কোনো account পাওয়া যায়নি!")
        exit(1)
    return accounts


NVIDIA_API_KEY    = os.environ.get("NVIDIA_API_KEY")
TIKTOK_COURSE_URL = os.environ.get("TIKTOK_COURSE_URL", "")

if not NVIDIA_API_KEY:
    print("❌ NVIDIA_API_KEY missing!")
    exit(1)


# ─── NVIDIA NIM CLIENT ───────────────────────────────────────────────────────
nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)


# ─── MASTER PROMPT ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert copywriter who writes high-converting social media posts
for a USA audience. Your posts sell a TikTok money-making course.

Your writing is:
- Direct, punchy, and natural American in tone
- Built around curiosity and FOMO — reader must feel they are missing out
- Always beginner-friendly in angle (no experience needed framing)
- Focused on faceless, AI, or automation methods — not showing your face
- Never hype-y or scammy — confident but grounded

You NEVER use:
- Hashtags
- Emojis
- Income claims like "I made $X"
- Fake urgency phrases like "limited time only"
- Generic filler like "game changer" or "passive income"

Return ONLY the post text. No quotes. No explanation. Nothing else."""

USER_PROMPT_TEMPLATE = """Write a high-converting social media post for a USA audience to sell
a TikTok money-making course.

Rules:
- Maximum 250 characters (the course link will be added separately — do NOT include a URL)
- Hook in the very first sentence — make them stop scrolling
- Create curiosity + FOMO naturally
- Mention it works for beginners
- Mention faceless, AI, or automation angle
- End with a soft CTA: Comment "START"
- Natural American tone
- No hashtags
- No emojis
- Every output must be completely unique

Variation #{variation}: Use a fresh hook, different angle, and different sentence structure
from all previous variations. Same rules, totally different feel."""


# ─── IMAGE METADATA ──────────────────────────────────────────────────────────
IMAGE_OPTIONS = [
    ("TikTok Money Without Your Face",  "AI + Automation — Beginner Friendly", "value"),
    ("Most People Don't Know This",     "How TikTok pays you on autopilot",    "curiosity"),
    ("TikTok Course — No Camera Needed","Faceless. Automated. $7 to start.",   "offer"),
]


# ─── AI TEXT GENERATION ──────────────────────────────────────────────────────
def generate_post_text(variation: int) -> str:
    user_msg = USER_PROMPT_TEMPLATE.format(variation=variation + 1)

    completion = nvidia_client.chat.completions.create(
        model="deepseek-ai/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.92,
        top_p=0.95,
        max_tokens=200,
    )
    text = completion.choices[0].message.content.strip()

    # Strip surrounding quotes if model wraps them
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]

    return text


def append_link(text: str) -> str:
    """Append the TikTok course URL to the post text."""
    if not TIKTOK_COURSE_URL:
        print("  ⚠️  TIKTOK_COURSE_URL not set — skipping link")
        return text

    suffix   = f" {TIKTOK_COURSE_URL}"
    combined = text + suffix
    if len(combined) > 300:
        text     = text[: 300 - len(suffix) - 3] + "..."
        combined = text + suffix
    return combined


# ─── BLUESKY HELPERS ─────────────────────────────────────────────────────────
def bsky_login(handle: str, password: str) -> dict:
    r = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def bsky_upload_image(session: dict, image_path: str) -> dict | None:
    try:
        with open(image_path, "rb") as f:
            img_data = f.read()
        r = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
            headers={
                "Authorization": f"Bearer {session['accessJwt']}",
                "Content-Type":  "image/jpeg",
            },
            data=img_data,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["blob"]
    except Exception as e:
        print(f"  ⚠️  Image upload failed: {e}")
        return None
    finally:
        try:
            os.unlink(image_path)
        except Exception:
            pass


def build_facets(text: str) -> list:
    facets = []
    for match in re.finditer(r"#(\w+)", text):
        tag   = match.group(1)
        start = len(text[: match.start()].encode("utf-8"))
        end   = len(text[: match.end()].encode("utf-8"))
        facets.append({
            "index":    {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}],
        })
    for match in re.finditer(r"https?://[^\s\)\]\}\"\')]+", text):
        url   = match.group(0)
        start = len(text[: match.start()].encode("utf-8"))
        end   = len(text[: match.end()].encode("utf-8"))
        facets.append({
            "index":    {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        })
    return facets


def bsky_post(session: dict, text: str, image_path: str | None = None, alt_text: str = "") -> str:
    facets = build_facets(text)
    record = {
        "$type":     "app.bsky.feed.post",
        "text":      text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if facets:
        record["facets"] = facets
    if image_path:
        blob = bsky_upload_image(session, image_path)
        if blob:
            record["embed"] = {
                "$type":  "app.bsky.embed.images",
                "images": [{"image": blob, "alt": alt_text or "TikTok course"}],
            }
    r = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["uri"]


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    accounts  = load_accounts()
    time_slot = int(os.environ.get("TIME_SLOT", "1"))

    utc_now     = datetime.now(timezone.utc)
    est_now     = utc_now - timedelta(hours=5)
    day_of_week = est_now.weekday()

    slot_label = {1: "☀️ Morning", 2: "🍔 Afternoon", 3: "🌆 Evening"}

    print(f"🚀 Bluesky Bot — TikTok Course Poster")
    print(f"📅 {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_of_week]} | {slot_label.get(time_slot, str(time_slot))}")
    print(f"👥 Accounts: {len(accounts)}\n")

    # Rotate image style across the 3 daily slots
    img_main, img_sub, category = IMAGE_OPTIONS[(time_slot - 1) % len(IMAGE_OPTIONS)]

    results = []

    for i, account in enumerate(accounts):
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"👤 Account {account['id']}: {account['handle']}")

        try:
            print(f"  🔑 Logging in...")
            session = bsky_login(account["handle"], account["password"])
            print(f"  ✅ Login success")

            print(f"  🤖 Generating text (variation {i + 1})...")
            post_text = generate_post_text(variation=i)
            post_text = append_link(post_text)

            # Hard safety cap
            if len(post_text) > 300:
                post_text = post_text[:297] + "..."

            print(f"  ✍️  {post_text[:100]}...")
            print(f"  📏 {len(post_text)} chars")

            print(f"  🖼️  Generating image...")
            image_path = generate_image(
                main_text=img_main,
                sub_text=img_sub,
                category=category,
                course="tiktok",
            )
            print(f"  ✅ Image ready")

            print(f"  📤 Posting...")
            alt_text = f"{img_main} — {img_sub}"
            uri = bsky_post(session, post_text, image_path, alt_text)
            print(f"  ✅ Posted! {uri}")
            results.append({"account": account["handle"], "status": "success", "uri": uri})

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results.append({"account": account["handle"], "status": "failed", "error": str(e)})

        if i < len(accounts) - 1:
            delay = random.randint(15, 35)
            print(f"  ⏳ Waiting {delay}s...")
            time.sleep(delay)

    success = sum(1 for r in results if r["status"] == "success")
    failed  = sum(1 for r in results if r["status"] == "failed")
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 Done: ✅ {success} success | ❌ {failed} failed")

    if success == 0:
        exit(1)


if __name__ == "__main__":
    main()
