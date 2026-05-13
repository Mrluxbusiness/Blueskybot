import os
import re
import time
import random
import requests
import tempfile
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

NVIDIA_API_KEY       = os.environ.get("NVIDIA_API_KEY")
TIKTOK_COURSE_URL    = os.environ.get("TIKTOK_COURSE_URL", "")
INSTAGRAM_COURSE_URL = os.environ.get("INSTAGRAM_COURSE_URL", "")

if not NVIDIA_API_KEY:
    print("❌ NVIDIA_API_KEY missing!")
    exit(1)

# ─── NVIDIA NIM CLIENT ────────────────────────────────────────────────────────
nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)


# ─── MASTER PROMPT ────────────────────────────────────────────────────────────
#
# Style 3 = "Teach then sell" → Slot 1 (Morning) & Slot 2 (Afternoon)
#   Teach ONE specific, concrete thing about the platform.
#   At the end, mention the course as a natural next step — not a hard pitch.
#
# Style 4 = "Honest builder" → Slot 3 (Evening)
#   No income claims. No price anchoring. No fake urgency.
#   Sound like a real person sharing something they built.
#   Name ONE concrete skill the buyer walks away with.
#

def build_master_prompt(slot: int, course: str, variation: int) -> dict:
    course_url   = INSTAGRAM_COURSE_URL if course == "instagram" else TIKTOK_COURSE_URL
    platform     = "Instagram" if course == "instagram" else "TikTok"

    # ── SLOT 1 — Morning: Style 3 "Teach then sell" ──────────────────────────
    # Lead with a real, specific insight. The course mention is the last line,
    # framed as "I documented this" — not "buy now".
    slot1_instruction = f"""You are posting a TEACH-THEN-SELL post (Style 3).

Step 1 — Teach ONE specific, counterintuitive thing about how the {platform} algorithm works in 2026.
  - Name a concrete mechanism (e.g. "watch time %", "saves vs likes", "repost signals")
  - Explain briefly WHY it matters — the logic, not just the fact
  - Keep it to 2–3 short paragraphs

Step 2 — End with a single soft offer line, like:
  "I documented this + more in a $7 course → [link]"
  or "Built a $7 course around this exact thing → [link]"

Rules:
- The teaching must be SPECIFIC. Not "post consistently" — give the actual mechanic.
- No income claims. No "I grew from X to Y".
- The offer line must feel like a natural footnote, not a sales pitch.
- The course link will be appended automatically — do NOT include a URL in your text.
- End with 2 specific hashtags only (e.g. #{platform}Tips, #ContentStrategy)."""

    # ── SLOT 2 — Afternoon: Style 3 variant "Relatable story + teach" ────────
    # Start with a relatable mistake or observation. Teach the fix. Soft offer.
    slot2_instruction = f"""You are posting a STORY-THEN-TEACH post (Style 3 variant).

Step 1 — Open with a relatable observation or common mistake creators make on {platform}.
  Frame it as: "Most creators do X — but actually Y"
  OR: "I noticed that accounts which [do X] consistently [get Y result]"
  Be specific — name the actual behaviour, not a vague platitude.

Step 2 — Explain the better approach in 1–2 short paragraphs. Concrete, not generic.

Step 3 — One soft offer line at the end:
  "Covered this in detail in my $7 {platform} course → [link]"
  or "I broke this down properly in a $7 course → [link]"

Rules:
- NO income claims ("I made $X", "from 0 to 10K followers")
- The course mention is a footnote — 1 line max
- The course link will be appended automatically — do NOT include a URL
- 2 specific hashtags only"""

    # ── SLOT 3 — Evening: Style 4 "Honest builder" ───────────────────────────
    # Shorter. No hype. Sound like a person sharing their work.
    # Name ONE concrete skill or outcome. $7 mentioned naturally.
    slot3_instruction = f"""You are posting an HONEST BUILDER post (Style 4).

You spent time learning {platform} growth and documented what actually works into a $7 course.
Your job: sound like a real person sharing something they built — not a marketer selling it.

Structure:
1. One honest opening — why you made this (e.g. "Spent months figuring out {platform}...")
2. Name ONE specific, concrete skill the buyer gets (not vague like "grow your account" —
   something like "you'll know exactly which content format gets saved and why saves beat likes for reach")
3. Mention $7 naturally — not as a discount or deal, just as the price
4. One gentle CTA. The course link will be appended automatically — do NOT include a URL.

Hard rules:
- NO price anchoring ("gurus charge $497")
- NO income claims
- NO fake urgency ("price going up!")
- NO generic phrases like "step by step", "game changer", "passive income"
- Keep it under 220 characters of actual text (before the link is added)
- 2 hashtags max — make them specific, not #MakeMoneyOnline"""

    slot_instruction = {1: slot1_instruction, 2: slot2_instruction, 3: slot3_instruction}[slot]

    variation_note = (
        f"\n\nVariation #{variation + 1}: Use a completely different opening word, "
        "angle, and sentence structure from other variations. Same topic, fresh voice."
        if variation > 0 else ""
    )

    system = f"""You write Bluesky posts for a creator who sells a $7 {platform} growth course.

Bluesky users are tech-savvy, left Twitter to escape guru culture, and will instantly
ignore anything that smells like a marketing bot. They reward specificity and honesty.

Your writing style:
- Sounds like a real person who actually uses {platform} and noticed something
- Specific and concrete — names mechanisms, behaviours, numbers where relevant
- Never hype-y, never salesy, never generic
- Short paragraphs. Breathing room. Not a wall of text.

You NEVER write:
- Income claims ("I made $X/month", "from 200 to $4000")
- Price anchoring ("gurus charge $497, I charge $7")
- Fake urgency ("price going up!", "limited time")
- Generic hashtags (#MakeMoneyOnline, #OnlineBusiness, #Hustle)
- Filler phrases ("game changer", "passive income", "step by step system")

Return ONLY the post text. No quotes around it. Nothing else."""

    return {
        "system":     system,
        "user":       slot_instruction + variation_note,
        "slot":       slot,
        "course":     course,
        "course_url": course_url,
        "platform":   platform,
    }


# ─── IMAGE METADATA ───────────────────────────────────────────────────────────
IMAGE_META = {
    1: {
        "instagram": ("Instagram Algorithm 2026",     "What actually gets you reach 📈",  "value"),
        "tiktok":    ("TikTok Tips That Work",         "Grow faster this year 🚀",         "value"),
    },
    2: {
        "instagram": ("Most Creators Get This Wrong",  "Here's what actually works 💡",    "curiosity"),
        "tiktok":    ("The Mistake Killing Your Reach","And the simple fix 🔧",            "curiosity"),
    },
    3: {
        "instagram": ("Instagram Growth Course",       "Practical · $7 · No fluff 🎯",    "offer"),
        "tiktok":    ("TikTok Growth Course",          "Practical · $7 · No fluff 🎯",    "offer"),
    },
}


# ─── WEEKLY COURSE ROTATION ───────────────────────────────────────────────────
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

    completion = nvidia_client.chat.completions.create(
        model="deepseek-ai/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": built["system"]},
            {"role": "user",   "content": built["user"]},
        ],
        temperature=0.88,
        top_p=0.95,
        max_tokens=320,
    )
    text = completion.choices[0].message.content.strip()

    # Strip surrounding quotes if model adds them
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]

    return text


def append_link(text: str, slot: int, course: str) -> str:
    """
    All 3 slots now get the course link — soft offer is baked into every post.
    Slot 1 & 2: link appears as a natural footnote at the end.
    Slot 3: same, but the CTA line before it is more direct.
    """
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

    slot_label = {
        1: "☀️ Morning (Teach then Sell)",
        2: "🍔 Afternoon (Story + Teach)",
        3: "🌆 Evening (Honest Builder Offer)",
    }

    print(f"🚀 Bluesky Bot — Style 3 & 4 Prompt System")
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
