#!/usr/bin/env python3
"""
Menu photo pipeline for Hotel Lazzy-Kitchen.

Every dish needs ONE photo at  frontend/assets/images/menu/<slug>.jpg
(slugs come from backend/menu_catalog.py). Until a photo exists the site shows
a themed emoji tile, so nothing breaks.

Usage (run from project root, needs:  pip install Pillow requests):

  python3 tools/menu_images.py list
      Show every slug and whether its photo exists.

  python3 tools/menu_images.py process [--src tools/raw_images]
      Take photos YOU downloaded (save as <slug>.jpg/.png/.webp in --src),
      centre-crop to 4:3, resize to 800x600 and save optimised progressive
      JPEGs (~60-120 KB) into frontend/assets/images/menu/.

  python3 tools/menu_images.py fetch [--only slug ...]
      Search Wikimedia Commons for each missing dish, download the best openly
      licensed JPEG, process it, and record author/licence in
      tools/image_credits.json. Results are a starting point: REVIEW every
      image and replace poor matches with a better photo via `process`.
      Respect the licence terms (CC BY / CC BY-SA need attribution).
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
from menu_catalog import CATALOG  # noqa: E402

OUT_DIR = os.path.join(ROOT, "frontend", "assets", "images", "menu")
CREDITS = os.path.join(ROOT, "tools", "image_credits.json")
SIZE = (800, 600)

# Better search phrases than the display name for a few dishes
QUERY_HINTS = {
    "idly": "idli sambar", "plain-dosa": "plain dosa", "ghee-roast": "ghee roast dosa",
    "medu-vadai": "medu vada", "special-sambar": "sambar bowl", "parotta": "kerala parotta",
    "poori": "poori masala", "pongal": "ven pongal", "chicken-65": "chicken 65",
    "mutton-mandi": "mutton mandi", "chicken-kothu-parotta": "kothu parotta",
    "paneer-butter-masala": "paneer butter masala", "egg-omelette": "omelette plate",
    "filter-coffee": "south indian filter coffee", "normal-tea": "indian masala chai cup",
    "black-tea": "black tea cup", "ginger-tea": "ginger tea",
    "classic-chicken-shawarma": "chicken shawarma wrap", "spicy-chicken-shawarma": "chicken shawarma",
    "peri-peri-fries": "peri peri fries", "veg-loaded-pizza": "vegetable pizza",
}
ALLOWED_LICENCES = ("cc0", "cc by", "cc-by", "public domain", "pd")


def process_image(data: bytes, dest: str):
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img = ImageOps.fit(img, SIZE, method=Image.LANCZOS, centering=(0.5, 0.5))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    img.save(dest, "JPEG", quality=80, optimize=True, progressive=True)
    return os.path.getsize(dest)


def dest_for(slug):
    return os.path.join(OUT_DIR, f"{slug}.jpg")


def cmd_list(_):
    missing = 0
    for it in CATALOG:
        ok = os.path.exists(dest_for(it["slug"]))
        missing += (not ok)
        print(f"{'OK     ' if ok else 'MISSING'}  {it['slug']:28} {it['name']}")
    print(f"\n{len(CATALOG) - missing}/{len(CATALOG)} photos present")


def cmd_process(args):
    done = 0
    for it in CATALOG:
        for ext in ("jpg", "jpeg", "png", "webp"):
            src = os.path.join(args.src, f"{it['slug']}.{ext}")
            if os.path.exists(src):
                with open(src, "rb") as fh:
                    size = process_image(fh.read(), dest_for(it["slug"]))
                print(f"processed {it['slug']}  ({size // 1024} KB)")
                done += 1
                break
    print(f"{done} image(s) processed into {OUT_DIR}")


def cmd_fetch(args):
    import requests
    api = "https://commons.wikimedia.org/w/api.php"
    headers = {"User-Agent": "LazzyKitchenImageTool/1.0 (learning project)"}
    credits = json.load(open(CREDITS)) if os.path.exists(CREDITS) else {}
    for it in CATALOG:
        slug = it["slug"]
        if args.only and slug not in args.only:
            continue
        if os.path.exists(dest_for(slug)) and not args.only:
            continue
        query = QUERY_HINTS.get(slug, it["name"])
        params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                  "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": 15, "prop": "imageinfo",
                  "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 1200}
        try:
            pages = requests.get(api, params=params, headers=headers, timeout=20).json().get("query", {}).get("pages", {})
        except Exception as exc:  # noqa: BLE001
            print(f"[{slug}] search failed: {exc}")
            continue
        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            licence = (meta.get("LicenseShortName", {}).get("value", "")).lower()
            if info.get("mime") != "image/jpeg" or info.get("width", 0) < 800 or info.get("height", 0) < 600:
                continue
            if not any(a in licence for a in ALLOWED_LICENCES) or "nc" in licence.split():
                continue
            try:
                data = requests.get(info["thumburl"], headers=headers, timeout=30).content
                size = process_image(data, dest_for(slug))
            except Exception as exc:  # noqa: BLE001
                print(f"[{slug}] download failed: {exc}")
                continue
            credits[slug] = {"title": page["title"], "source": info.get("descriptionurl"),
                             "author": meta.get("Artist", {}).get("value", ""),
                             "licence": meta.get("LicenseShortName", {}).get("value", "")}
            print(f"[{slug}] {page['title']}  ({size // 1024} KB, {credits[slug]['licence']})")
            break
        else:
            print(f"[{slug}] no suitable image found — add one manually")
    json.dump(credits, open(CREDITS, "w"), indent=2)
    print(f"Credits written to {CREDITS}. Please review each image visually.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("process"); p.add_argument("--src", default=os.path.join(ROOT, "tools", "raw_images")); p.set_defaults(fn=cmd_process)
    f = sub.add_parser("fetch"); f.add_argument("--only", nargs="*"); f.set_defaults(fn=cmd_fetch)
    a = ap.parse_args(); a.fn(a)
