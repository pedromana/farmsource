SCENE_BY_THEME = {
    "fresh produce": "cinematic produce closeups with crisp greens, berries, herbs, and market-style crates",
    "local farms": "golden-hour farm rows, farmers harvesting, and realistic regional farm textures",
    "seasonal products": "seasonal harvest visuals with hands packing colorful produce",
    "weekly produce boxes": "produce unboxing scene with a weekly farm box on a kitchen counter",
    "Seattle/local community": "Seattle-themed local food visuals with neighborhood delivery and overcast natural light",
    "farm-to-door delivery": "local delivery scenes with packed produce boxes arriving at front doors",
    "healthy meals": "healthy meal prep using seasonal vegetables in a bright home kitchen",
    "behind-the-scenes delivery": "behind-the-scenes route packing, labels, crates, and driver handoff",
    "recipe inspiration": "recipe prep scene with chopped seasonal vegetables and herbs",
}


def generate_video_prompt(content_theme: str | None, target_platform: str) -> str:
    scene = SCENE_BY_THEME.get(content_theme or "", SCENE_BY_THEME["fresh produce"])
    return (
        f"Cinematic vertical video for {target_platform}: {scene}, realistic lighting, natural colors, "
        "shallow depth of field, high-quality social media video, no text overlays, warm community-focused mood."
    )


def generate_short_script(title: str, content_theme: str | None, target_audience: str) -> str:
    theme = content_theme or "local produce"
    return (
        "0-2s: Open on a close-up of fresh produce or a packed Farmsource box.\n"
        f"2-6s: Show {theme.lower()} with quick cuts of harvesting, packing, or delivery.\n"
        f"6-10s: Explain why it matters for {target_audience}: fresher food, local support, and planned routes.\n"
        f"10-15s: End card idea: {title}. Join Farmsource for launch updates."
    )
