import os
import re
import time
import random
import requests
import tempfile
from datetime import datetime, timezone, timedelta
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

DEEPSEEK_API_KEY     = os.environ.get("DEEPSEEK_API_KEY")
TIKTOK_COURSE_URL    = os.environ.get("TIKTOK_COURSE_URL", "")
INSTAGRAM_COURSE_URL = os.environ.get("INSTAGRAM_COURSE_URL", "")

if not DEEPSEEK_API_KEY:
    print("❌ DEEPSEEK_API_KEY missing!")
    exit(1)


# ─── MASTER PROMPT ────────────────────────────────────────────────────────────
# Research-backed: Bluesky values authority, specificity, and genuine helpfulness.
# No income claims. No price anchoring. Teach first, sell softly.

def build_master_prompt(slot: int, course: str, variation: int) -> dict:
    """
    slot 1 = Morning  → Pure value, teach something specific. No CTA.
    slot 2 = Afternoon → Curiosity / relatable story. No income claims.
    slot 3 = Evening   → Soft offer, ONE link. Authority-led, not sales-led.

    course = "instagram" or "tiktok"
    variation = 0..4 (for multi-account uniqueness)
    """

    course_url   = INSTAGRAM_COURSE_URL if course == "instagram" else TIKTOK_COURSE_URL
    platform     = "Instagram" if course == "instagram" else "TikTok"
    opp_platform = "TikTok" if course == "instagram" else "Instagram"

    # Slot 3 appends link — keep text shorter to fit 300 char limit
    char_limit = "under 240 characters" if slot == 3 else "under 280 characters"

    slot_instruction = {
        1: f"""You are posting a VALUE post. Your ONLY goal is to teach.
Pick ONE specific, counterintuitive tip about {platform} growth in 2026.
Be concrete — mention a mechanism, a number, or a "why" that most people don't know.
Do NOT mention any course, product, or yourself. Just pure value.
End with a question to spark replies (e.g. "Have you tried this?").""",

        2: f"""You are posting a CURIOSITY / STORY post.
Share a short relatable observation or mistake creators make on {platform}.
Frame it as "I noticed..." or "Most people do X, but actually Y."
Be specific. No vague generalities.
NO income claims (no "$X/month", no follower counts as proof).
A soft, natural mention that you've documented what works is okay — but no hard sell.""",

        3: f"""You are posting a SOFT OFFER post.
You have a practical, affordable {platform} growth course ($7).
Do NOT use price anchoring ("gurus charge $497").
Do NOT make income claims.
Instead, name ONE concrete skill or outcome the student gets from the course —
something specific like "you'll know exactly which content format gets saved on {platform}, and why saves beat likes for the algorithm."
End with a single gentle CTA. The course link will be added below automatically.
Keep it human, not salesy. Sound like a builder sharing their work.""",
    }[slot]

    variation_note = (
        f"\n\nThis is account variation #{variation + 1}. "
        "Use a completely different opening word, angle, and sentence structure "
        "from other variations. Be creative — same topic, fresh voice."
        if variation > 0 else ""
    )

    system = """You are a Bluesky-native creator who understands this platform deeply.
Bluesky users are tech-savvy, anti-spam, and left Twitter to escape "guru" culture.
They reward specificity and punish vague marketing language.
Rules you NEVER break:
- No income claims ("I made $X", "from 200 to $4000")
- No price anchoring ("gurus charge $497, I charge $7")
- No fake urgency ("price going up soon")
- No generic hashtags like #MakeMoneyOnline or #OnlineBusiness
- Use only 2–3 highly specific hashtags relevant to the content
- Sound like a real person, not a marketing bot
- Return ONLY the post text. Nothing else. No quotes around it."""

    user = f"""{slot_instruction}

Platform focus: {platform}
Character limit: {char_limit} — count carefully before returning.
Use 2–3 specific hashtags (e.g. #{platform}Tips, #ContentStrategy, #CreatorTips — pick what fits).
{variation_note}

Return ONLY the post text."""

    return {"system": system, "user": user, "slot": slot, "course": course, "course_url": course_url, "platform": platform}


# ─── IMAGE METADATA ───────────────────────────────────────────────────────────
IMAGE_META = {
    # slot → (main_text, sub_text, category)
    1: {
        "instagram": ("Instagram Algorithm 2026",    "What actually gets you reach 📈",   "value"),
        "tiktok":    ("TikTok Tips That Work",        "Grow faster this year 🚀",          "value"),
    },
    2: {
        "instagram": ("Most Creators Get This Wrong", "Here's what actually works 💡",     "curiosity"),
        "tiktok":    ("The Mistake Killing Your Reach","And the simple fix 🔧",             "curiosity"),
    },
    3: {
        "instagram": ("Instagram Income Mastery",     "Step-by-step · $7 · 8 Modules 🎯", "offer"),
        "tiktok":    ("TikTok Income Mastery",        "Step-by-step · $7 · 8 Modules 🎯", "offer"),
    },
}


# ─── WEEKLY COURSE ROTATION ───────────────────────────────────────────────────
# Alternate Instagram / TikTok so both get equal exposure across the week
COURSE_BY_DAY = {
    0: "instagram",  # Monday
    1: "tiktok",
    2: "instagram",
    3: "tiktok",
    4: "instagram",
    5: "tiktok",
    6: "instagram",  # Sunday
}


# ─── AI TEXT GENERATION ───────────────────────────────────────────────────────
def generate_post_text(prompt_data: dict, variation: int) -> str:
    built = build_master_prompt(prompt_data["slot"], prompt_data["course"], variation)

    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "model":    "deepseek-chat",
            "messages": [
                {"role": "system", "content": built["system"]},
                {"role": "user",   "content": built["user"]},
            ],
            "max_tokens":  300,
            "temperature": 0.92,
        },
        timeout=30,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"].strip()

    # Strip surrounding quotes if model adds them
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]

    return text


def append_link(text: str, slot: int, course: str) -> str:
    """Only slot 3 (evening offer) gets the course link."""
    if slot != 3:
        return text
    url = INSTAGRAM_COURSE_URL if course == "instagram" else TIKTOK_COURSE_URL
    if not url:
        print("  ⚠️  Course URL not set — skipping link")
        return text
    suffix   = f"\n\n👉 {url}"
    combined = text + suffix
    if len(combined) > 300:
        text     = text[: 300 - len(suffix) - 3] + "..."
        combined = text + suffix
    return combined


# ─── BLUESKY HELPERS ──────────────────────────────────────────────────────────
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
        except:
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
    for match in re.finditer(r"https?://[^\s\)\]\}\"']+", text):
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
                "images": [{"image": blob, "alt": alt_text or "Course image"}],
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
    course      = COURSE_BY_DAY.get(day_of_week, "instagram")

    meta     = IMAGE_META[time_slot][course]
    img_main, img_sub, category = meta

    slot_label = {1: "☀️ Morning (Value)", 2: "🍔 Afternoon (Curiosity)", 3: "🌆 Evening (Soft Offer)"}

    print(f"🚀 Bluesky Bot — Single Master Prompt")
    print(f"📅 {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_of_week]} | {slot_label[time_slot]}")
    print(f"🎯 Course: {course.upper()} | Accounts: {len(accounts)}\n")

    prompt_data = {"slot": time_slot, "course": course}
    results     = []

    for i, account in enumerate(accounts):
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"👤 Account {account['id']}: {account['handle']}")

        try:
            print(f"  🔑 Logging in...")
            session = bsky_login(account["handle"], account["password"])
            print(f"  ✅ Login success")

            print(f"  🤖 Generating text (variation {i + 1})...")
            post_text = generate_post_text(prompt_data, variation=i)
            post_text = append_link(post_text, time_slot, course)

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
                course=course,
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
