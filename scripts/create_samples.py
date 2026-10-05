"""Create original, deterministic sample artwork for manual testing."""

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parents[1] / "examples"


def save_color_badge() -> None:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((90, 60, 510, 480), fill="#4B9CD3")
    draw.ellipse((230, 160, 650, 580), fill="#13294B")
    draw.polygon([(570, 70), (840, 300), (570, 530), (640, 300)], fill="#4C9B4A")
    image.save(OUTPUT / "color-badge.png")


def save_adjacent_regions() -> None:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 450, 520), fill="#4B9CD3")
    draw.rectangle((450, 80, 820, 520), fill="#13294B")
    draw.ellipse((330, 190, 570, 430), fill="#F3D34A")
    image.save(OUTPUT / "adjacent-regions.png")


def save_holes_and_curves() -> None:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 60, 660, 540), fill="#13294B")
    draw.ellipse((250, 170, 530, 430), fill="white")
    draw.rounded_rectangle((610, 130, 820, 470), radius=85, fill="#4B9CD3")
    image.save(OUTPUT / "holes-and-curves.png")


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    save_color_badge()
    save_adjacent_regions()
    save_holes_and_curves()
    print(f"Created samples in {OUTPUT}")
