import os
import re
import time
import json
import random
import requests
import tempfile
from datetime import datetime, timezone
from image_gen import generate_image

# ─── ACCOUNTS CONFIG ──────────────────────────────────────────────────────────
def load_accounts() -> list[dict]:
    accounts = []
    for i in range(1, 6):
        handle   = os.environ.get(f"BSKY_HANDLE_{i}")
        password = os.environ.get(f"BSKY_PASSWORD_{i}")
        if handle and password:
            accounts.append({"id": i, "handle": handle, "password": password})
    if not accounts:
        print("❌ কোনো account পাওয়া যায়নি! BSKY_HANDLE_1 এবং BSKY_PASSWORD_1 set করুন।")
        exit(1)
    return accounts

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("❌ DEEPSEEK_API_KEY missing!")
    exit(1)

# ─── COURSE URLs (from GitHub Secrets) ────────────────────────────────────────
TIKTOK_COURSE_URL    = os.environ.get("TIKTOK_COURSE_URL", "")
INSTAGRAM_COURSE_URL = os.environ.get("INSTAGRAM_COURSE_URL", "")

# ─── 15 ANGLES — 5 CATEGORIES ────────────────────────────────────────────────
# Category A: VALUE-FIRST (no link) — 40%
# Category B: CURIOSITY + SOFT SELL — 25%
# Category C: SOCIAL PROOF (subtle link) — 15%
# Category D: DIRECT OFFER (bold link) — 15%
# Category E: ENGAGEMENT BAIT (no link) — 5%

ANGLES = {
    # ── Category A: VALUE-FIRST ───────────────────────────────────────────────
    "A1": {
        "id": "A1", "category": "value", "course": "tiktok",
        "image_main": "3 TikTok Hacks That Actually Work",
        "image_sub": "Grow faster in 2026 🚀",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Share 3 quick TikTok growth hacks that actually work in 2026.
Tone: Expert sharing free knowledge. Genuine, helpful, NOT salesy.
Include relevant hashtags: #TikTok #ContentCreator #GrowthHacks
Return ONLY the post text, nothing else."""
    },
    "A2": {
        "id": "A2", "category": "value", "course": "instagram",
        "image_main": "Instagram Algorithm in 2026",
        "image_sub": "What actually gets you reach 📈",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Reveal what Instagram's 2026 algorithm actually favors — Reels length, carousel tips, posting time.
Tone: Insider knowledge, genuinely helpful. NOT an ad.
Include hashtags: #Instagram #Algorithm #SocialMediaTips
Return ONLY the post text, nothing else."""
    },
    "A3": {
        "id": "A3", "category": "value", "course": "tiktok",
        "image_main": "You DON'T Need 10K Followers",
        "image_sub": "To make money on social media 💡",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Myth-bust — you don't need 10K followers to monetize social media. Explain why small accounts can earn too.
Tone: Eye-opening, genuine, encouraging. NOT salesy.
Include hashtags: #MakeMoneyOnline #SocialMedia #Monetization
Return ONLY the post text, nothing else."""
    },
    "A4": {
        "id": "A4", "category": "value", "course": "instagram",
        "image_main": "One Bio Tweak = More DMs",
        "image_sub": "Try this today 🎯",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Quick win — one simple change to your Instagram bio that increases DMs and profile visits.
Tone: Friendly, actionable, like a friend giving a quick tip.
Include hashtags: #InstagramTips #QuickWin #SocialMediaGrowth
Return ONLY the post text, nothing else."""
    },
    "A5": {
        "id": "A5", "category": "value", "course": "tiktok",
        "image_main": "My Actual Content Calendar",
        "image_sub": "Behind the scenes this week 📋",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Behind-the-scenes — share what a real content calendar looks like for a TikTok creator this week.
Tone: Transparent, relatable, authentic. Like letting people peek behind the curtain.
Include hashtags: #ContentCreator #BehindTheScenes #TikTokCreator
Return ONLY the post text, nothing else."""
    },
    "A6": {
        "id": "A6", "category": "value", "course": "instagram",
        "image_main": "The #1 Monetization Mistake",
        "image_sub": "Most people get this wrong ⚠️",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: The #1 mistake people make when trying to monetize Instagram — and what to do instead.
Tone: Honest, educational, slightly cautionary. NOT preachy.
Include hashtags: #InstagramIncome #CommonMistakes #SocialMediaTips
Return ONLY the post text, nothing else."""
    },

    # ── Category B: CURIOSITY + SOFT SELL ─────────────────────────────────────
    "B1": {
        "id": "B1", "category": "curiosity", "course": "instagram",
        "image_main": "$1,700 From Instagram",
        "image_sub": "Last month alone. Here's what changed...",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Income reveal — made $1,700 last month from Instagram. Tease what changed without giving away everything.
End with something like "I put everything in a step-by-step system..."
Tone: Humble flex, genuine surprise, NOT braggy.
Include hashtags: #InstagramIncome #OnlineIncome #SideHustle
Return ONLY the post text, nothing else."""
    },
    "B2": {
        "id": "B2", "category": "curiosity", "course": "tiktok",
        "image_main": "From 200 Followers to $4,000+",
        "image_sub": "6 months. Zero to income. 📈",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Before/after transformation — 6 months ago had 200 followers and $0, now making real income from TikTok.
Hint that there's a system behind it. Don't hard-sell.
Tone: Storytelling, inspiring, authentic.
Include hashtags: #TikTokMoney #Transformation #OnlineIncome
Return ONLY the post text, nothing else."""
    },
    "B3": {
        "id": "B3", "category": "curiosity", "course": "tiktok",
        "image_main": "Student Just Hit $500/Month",
        "image_sub": "Started from scratch 🎉",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Student success — one of your students just hit their first $500 month on TikTok. Celebrate them.
Subtly mention they followed your system/guide.
Tone: Proud mentor, celebrating someone else's win.
Include hashtags: #StudentSuccess #TikTokIncome #MakeMoneyOnline
Return ONLY the post text, nothing else."""
    },
    "B4": {
        "id": "B4", "category": "curiosity", "course": "instagram",
        "image_main": "Courses Are a Waste of Money",
        "image_sub": "Unless they cost $7 and actually work... 🤔",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Controversial take — most courses are overpriced garbage. But what if one cost $7 and actually delivered real results?
Pattern interrupt — make people stop scrolling.
Tone: Bold, slightly provocative, but honest.
Include hashtags: #OnlineCourses #HotTake #MakeMoneyOnline
Return ONLY the post text, nothing else."""
    },

    # ── Category C: SOCIAL PROOF ──────────────────────────────────────────────
    "C1": {
        "id": "C1", "category": "proof", "course": "tiktok",
        "image_main": "Another Payment Just Hit 💸",
        "image_sub": "This system works if you work it",
        "include_link": True, "link_course": "tiktok",
        "prompt": """Write a Bluesky post (STRICTLY under 250 chars, count carefully) in English.
Angle: Payment proof — another payment just hit from TikTok monetization. The system works.
End with a subtle CTA pointing to the course link (the link will be appended separately).
Tone: Grateful, matter-of-fact, NOT braggy.
Include hashtags: #TikTokIncome #ProofOfWork #OnlineIncome
Return ONLY the post text, nothing else."""
    },
    "C2": {
        "id": "C2", "category": "proof", "course": "instagram",
        "image_main": "Got This DM Today...",
        "image_sub": "Student results speak louder 🗣️",
        "include_link": True, "link_course": "instagram",
        "prompt": """Write a Bluesky post (STRICTLY under 250 chars, count carefully) in English.
Angle: Student testimonial — got an amazing DM from a student who's now making money from Instagram.
End with subtle CTA (the link will be appended separately).
Tone: Proud, authentic, sharing someone else's win.
Include hashtags: #Testimonial #InstagramIncome #Results
Return ONLY the post text, nothing else."""
    },

    # ── Category D: DIRECT OFFER ──────────────────────────────────────────────
    "D1_tiktok": {
        "id": "D1_tiktok", "category": "offer", "course": "tiktok",
        "image_main": "TikTok Income Mastery — $7",
        "image_sub": "8 Modules + Action Bonus 🎯",
        "include_link": True, "link_course": "tiktok",
        "prompt": """Write a Bluesky post (STRICTLY under 240 chars, count carefully) in English.
Angle: Price anchor — most TikTok courses cost $197-$497. Yours is $7. Explain why (you want to help, not gatekeep).
8 modules + action bonus. Real results. CTA: grab it before price goes up.
The course link will be appended separately.
Tone: Direct, confident, value-driven. NOT desperate.
Include hashtags: #TikTokCourse #MakeMoneyOnline #OnlineBusiness
Return ONLY the post text, nothing else."""
    },
    "D1_instagram": {
        "id": "D1_instagram", "category": "offer", "course": "instagram",
        "image_main": "Instagram Income Mastery — $7",
        "image_sub": "8 Modules + Action Bonus 🎯",
        "include_link": True, "link_course": "instagram",
        "prompt": """Write a Bluesky post (STRICTLY under 240 chars, count carefully) in English.
Angle: Price anchor — most Instagram courses cost $197-$497. Yours is $7. Explain why.
8 modules + action bonus. Step-by-step system. CTA: lock it in now.
The course link will be appended separately.
Tone: Direct, confident, value-driven.
Include hashtags: #InstagramCourse #MakeMoneyOnline #OnlineBusiness
Return ONLY the post text, nothing else."""
    },
    "D2": {
        "id": "D2", "category": "offer", "course": "tiktok",
        "image_main": "Price Going Up Soon ⏰",
        "image_sub": "$7 → $27 — Lock it in now",
        "include_link": True, "link_course": "tiktok",
        "prompt": """Write a Bluesky post (STRICTLY under 240 chars, count carefully) in English.
Angle: Urgency — the $7 price is temporary, going up soon. Real scarcity, not fake hype.
CTA: get it before the price changes. The link will be appended separately.
Tone: Urgent but honest, NOT fake countdown pressure.
Include hashtags: #LimitedTime #TikTokCourse #OnlineIncome
Return ONLY the post text, nothing else."""
    },
    "D3_tiktok": {
        "id": "D3_tiktok", "category": "offer", "course": "tiktok",
        "image_main": "8 Modules. Real Results. $7.",
        "image_sub": "TikTok Income Mastery 👇",
        "include_link": True, "link_course": "tiktok",
        "prompt": """Write a Bluesky post (STRICTLY under 240 chars, count carefully) in English.
Angle: Direct CTA — 8 modules, action bonuses, real student results, only $7.
Simple, clear, no fluff. The link will be appended separately.
Tone: Confident, minimal, punchy.
Include hashtags: #TikTokCourse #SideHustle #OnlineBusiness
Return ONLY the post text, nothing else."""
    },
    "D3_instagram": {
        "id": "D3_instagram", "category": "offer", "course": "instagram",
        "image_main": "8 Modules. Real Results. $7.",
        "image_sub": "Instagram Income Mastery 👇",
        "include_link": True, "link_course": "instagram",
        "prompt": """Write a Bluesky post (STRICTLY under 240 chars, count carefully) in English.
Angle: Direct CTA — 8 modules, action bonuses, real student results, only $7. For Instagram.
Simple, clear, no fluff. The link will be appended separately.
Tone: Confident, minimal, punchy.
Include hashtags: #InstagramCourse #SideHustle #OnlineBusiness
Return ONLY the post text, nothing else."""
    },

    # ── Category E: ENGAGEMENT BAIT ───────────────────────────────────────────
    "E1": {
        "id": "E1", "category": "engagement", "course": "tiktok",
        "image_main": "What's Stopping You?",
        "image_sub": "Wrong answers only 👇😂",
        "include_link": False,
        "prompt": """Write a Bluesky post (STRICTLY under 280 chars, count carefully) in English.
Angle: Engagement question — ask "What's stopping you from making money online?" in a fun way.
Invite wrong answers only or hot takes. Make it interactive.
Tone: Fun, playful, community-building.
Include hashtags: #MakeMoneyOnline #Question #Community
Return ONLY the post text, nothing else."""
    },
}

# ─── WEEKLY SCHEDULE ──────────────────────────────────────────────────────────
# Day → (Morning angle, Afternoon angle, Evening angle)
# Slot 1 = morning (value), Slot 2 = afternoon (curiosity/proof), Slot 3 = evening (offer/engagement)
WEEKLY_SCHEDULE = {
    0: ("A1", "B1",          "D1_tiktok"),      # Monday
    1: ("A2", "B2",          "E1"),              # Tuesday
    2: ("A3", "C1",          "D2"),              # Wednesday
    3: ("A4", "B3",          "D3_tiktok"),       # Thursday
    4: ("A5", "B4",          "D1_instagram"),    # Friday
    5: ("A6", "C2",          "D3_instagram"),    # Saturday
    6: ("A1", "B1",          "E1"),              # Sunday
}

# ─── DEEPSEEK: TEXT GENERATE ──────────────────────────────────────────────────
def generate_post_text(angle_data: dict, variation_seed: int = 0) -> str:
    """Generate unique post text. variation_seed ensures different text per account."""
    prompt = angle_data["prompt"]
    if variation_seed > 0:
        prompt += f"\n\nIMPORTANT: This is variation #{variation_seed}. Make it meaningfully different from other versions — use different opening, different structure, different examples. Be creative."

    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 350,
            "temperature": 0.95,
        },
        timeout=30,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"].strip()

    # Remove any quotes DeepSeek might add
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]

    return text


def append_course_link(text: str, angle_data: dict) -> str:
    """Append course link to post text if this angle includes a link."""
    if not angle_data.get("include_link"):
        return text

    course = angle_data.get("link_course", "tiktok")
    url = TIKTOK_COURSE_URL if course == "tiktok" else INSTAGRAM_COURSE_URL

    if not url:
        print(f"  ⚠️  {course.upper()}_COURSE_URL not set — skipping link")
        return text

    combined = f"{text}\n\n👉 {url}"

    # Enforce 300 char limit
    if len(combined) > 300:
        max_text = 300 - len(f"\n\n👉 {url}")
        text = text[:max_text - 3] + "..."
        combined = f"{text}\n\n👉 {url}"

    return combined


# ─── BLUESKY: LOGIN ───────────────────────────────────────────────────────────
def bsky_login(handle: str, password: str) -> dict:
    r = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ─── BLUESKY: IMAGE UPLOAD ────────────────────────────────────────────────────
def bsky_upload_image(session: dict, image_path: str) -> dict | None:
    try:
        with open(image_path, "rb") as f:
            img_data = f.read()
        r = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
            headers={
                "Authorization": f"Bearer {session['accessJwt']}",
                "Content-Type": "image/jpeg",
            },
            data=img_data,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["blob"]
    except Exception as e:
        print(f"  ⚠️  Image upload error: {e}")
        return None
    finally:
        try:
            os.unlink(image_path)
        except:
            pass


# ─── FACETS: HASHTAG + LINK ───────────────────────────────────────────────────
def build_facets(text: str) -> list:
    """Build Bluesky rich-text facets for both hashtags and URLs."""
    facets = []

    # Hashtag facets
    for match in re.finditer(r"#(\w+)", text):
        tag   = match.group(1)
        start = len(text[:match.start()].encode("utf-8"))
        end   = len(text[:match.end()].encode("utf-8"))
        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}],
        })

    # Link facets — detect URLs
    url_pattern = r"https?://[^\s\)\]\}\"']+"
    for match in re.finditer(url_pattern, text):
        url   = match.group(0)
        start = len(text[:match.start()].encode("utf-8"))
        end   = len(text[:match.end()].encode("utf-8"))
        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        })

    return facets


# ─── BLUESKY: POST ────────────────────────────────────────────────────────────
def bsky_post(session: dict, text: str, image_path: str | None = None, alt_text: str = "") -> str:
    facets = build_facets(text)

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if facets:
        record["facets"] = facets

    # Image attach
    if image_path:
        blob = bsky_upload_image(session, image_path)
        if blob:
            record["embed"] = {
                "$type": "app.bsky.embed.images",
                "images": [{"image": blob, "alt": alt_text or "Course marketing image"}],
            }

    r = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["uri"]


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    accounts = load_accounts()

    # Determine which time slot (1=morning, 2=afternoon, 3=evening)
    time_slot = int(os.environ.get("TIME_SLOT", "1"))

    # Determine day of week (0=Monday ... 6=Sunday) in EST
    # GitHub Actions runs in UTC, but we base schedule on EST day
    from datetime import timedelta
    utc_now = datetime.now(timezone.utc)
    est_now = utc_now - timedelta(hours=5)  # Approximate EST
    day_of_week = est_now.weekday()

    # Get today's schedule
    schedule = WEEKLY_SCHEDULE.get(day_of_week, ("A1", "B1", "D1_tiktok"))
    slot_index = max(0, min(time_slot - 1, 2))
    angle_id = schedule[slot_index]
    angle_data = ANGLES[angle_id]

    print(f"🚀 Bluesky Course Marketing Poster")
    print(f"📅 Day: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_of_week]} | Slot: {time_slot}")
    print(f"📌 Angle: {angle_id} ({angle_data['category']})")
    print(f"🎯 Course: {angle_data['course']}")
    print(f"👥 Accounts: {len(accounts)}টি\n")

    results = []

    for i, account in enumerate(accounts):
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"👤 Account {account['id']}: {account['handle']}")
        print(f"📌 Angle: {angle_id} | Variation: {i + 1}")

        try:
            # 1. Login
            print(f"  🔑 Login করছি...")
            session = bsky_login(account["handle"], account["password"])
            print(f"  ✅ Login সফল!")

            # 2. Generate unique text (variation per account)
            print(f"  🤖 Text লিখছি (variation {i + 1})...")
            post_text = generate_post_text(angle_data, variation_seed=i)

            # 3. Append course link if needed
            post_text = append_course_link(post_text, angle_data)

            # Enforce 300 char hard limit
            if len(post_text) > 300:
                post_text = post_text[:297] + "..."

            print(f"  ✍️  {post_text[:80]}...")
            print(f"  📏 {len(post_text)} chars")

            # 4. Generate image
            print(f"  🖼️  Image বানাচ্ছি...")
            image_path = generate_image(
                main_text=angle_data["image_main"],
                sub_text=angle_data["image_sub"],
                category=angle_data["category"],
                course=angle_data["course"],
            )
            print(f"  ✅ Image তৈরি!")

            # 5. Post
            print(f"  📤 Post করছি...")
            alt_text = f"{angle_data['image_main']} — {angle_data['image_sub']}"
            uri = bsky_post(session, post_text, image_path, alt_text)
            print(f"  ✅ পোস্ট সফল! {uri}")
            results.append({"account": account["handle"], "status": "success", "uri": uri})

        except Exception as e:
            print(f"  ❌ ব্যর্থ: {e}")
            results.append({"account": account["handle"], "status": "failed", "error": str(e)})

        # Random delay between accounts (anti-spam)
        if i < len(accounts) - 1:
            delay = random.randint(10, 30)
            print(f"  ⏳ {delay} সেকেন্ড অপেক্ষা...")
            time.sleep(delay)

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    failed  = sum(1 for r in results if r["status"] == "failed")
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 সারসংক্ষেপ: ✅ {success} সফল | ❌ {failed} ব্যর্থ")
    print(f"📌 Angle: {angle_id} | Category: {angle_data['category']} | Course: {angle_data['course']}")
    print("🎉 সম্পন্ন!")

    if success == 0:
        exit(1)


if __name__ == "__main__":
    main()
