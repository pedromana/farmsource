from dataclasses import dataclass

from app.services.ai_services.caption_generator import generate_call_to_action, generate_caption
from app.services.ai_services.hashtag_generator import generate_hashtags
from app.services.ai_services.video_prompt_generator import generate_short_script, generate_video_prompt


CONTENT_TYPES = [
    "producer_spotlight",
    "product_spotlight",
    "produce_box",
    "seasonal_content",
    "recipe_content",
    "delivery_content",
    "behind_the_scenes",
    "educational",
    "driver_recruitment",
    "producer_recruitment",
    "launch_announcement",
]

TARGET_PLATFORMS = ["instagram", "tiktok", "youtube_shorts", "facebook"]
TARGET_AUDIENCES = ["customers", "producers", "drivers", "general"]
CONTENT_STATUSES = ["draft", "generated", "ready_for_review", "approved", "rejected", "posted"]
POSTING_STATUSES = ["planned", "pending", "posted", "failed"]


@dataclass(frozen=True)
class GeneratedMarketingContent:
    title: str
    short_description: str
    ai_prompt: str
    generated_caption: str
    generated_hashtags: str
    generated_video_prompt: str
    generated_script: str


def generate_post_idea(content_type: str, content_theme: str | None, target_audience: str) -> tuple[str, str]:
    readable_type = content_type.replace("_", " ")
    theme = content_theme or "fresh produce"
    title = f"{theme.title()} {readable_type.title()}"
    description = f"A {readable_type} concept for {target_audience} focused on {theme.lower()} and manual social posting."
    return title, description


def generate_marketing_content(
    content_type: str,
    content_theme: str | None,
    target_platform: str,
    target_audience: str,
    seed_title: str | None = None,
    notes: str | None = None,
) -> GeneratedMarketingContent:
    title, description = generate_post_idea(content_type, content_theme, target_audience)
    if seed_title:
        title = seed_title
    prompt = _build_prompt(content_type, content_theme, target_platform, target_audience, notes)
    caption = generate_caption(title, content_theme, target_audience, target_platform)
    cta = generate_call_to_action(target_audience)
    return GeneratedMarketingContent(
        title=title,
        short_description=description,
        ai_prompt=prompt,
        generated_caption=f"{caption}\n\nCTA: {cta}",
        generated_hashtags=generate_hashtags(content_theme, target_audience),
        generated_video_prompt=generate_video_prompt(content_theme, target_platform),
        generated_script=generate_short_script(title, content_theme, target_audience),
    )


def _build_prompt(content_type: str, content_theme: str | None, target_platform: str, target_audience: str, notes: str | None) -> str:
    return (
        "Generate a manually reviewed Farmsource social media draft. "
        f"Content type: {content_type}. Theme: {content_theme or 'fresh produce'}. "
        f"Platform: {target_platform}. Audience: {target_audience}. "
        "Include an engaging caption, dynamic hashtags, a vertical short-video prompt, a concise script, and a clear CTA. "
        "Do not post automatically or call any social media API. "
        f"Notes: {notes or 'None'}"
    )
