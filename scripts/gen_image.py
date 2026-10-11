# /// script
# requires-python = ">=3.11"
# dependencies = ["google-genai>=1.65", "pillow"]
# ///
"""Design helper: generate images with Gemini (Nano Banana 2) for Elissa's character and UI references.

Runs isolated from the app (its SDK pins an older websockets):
    uv run scripts/gen_image.py "prompt" -o design/out/name.png [-r reference.png ...] [--aspect 1:1] [--size 2K]
    uv run scripts/gen_image.py --list-models

The key is read from GEMINI_API_KEY / GOOGLE_API_KEY in the environment or in the git-ignored project .env.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gemini-3.1-flash-image"


def load_key() -> str:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    env = ROOT / ".env"
    names = []
    if env.exists():
        for line in env.read_text("utf-8").splitlines():
            k, sep, v = line.partition("=")
            k = k.strip().removeprefix("export ").strip()
            if not sep or k.startswith("#"):
                continue
            names.append(k)
            if k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_AISTUDIO", "GEMINI_KEY"):
                return v.strip().strip('"').strip("'")
    sys.exit(f"No encontré la key de Gemini. Variables en .env: {names or 'ninguna'} "
             "(usa GEMINI_API_KEY=...).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("-o", "--out", default="design/out/image.png")
    ap.add_argument("-r", "--ref", action="append", default=[], help="reference image (repeatable)")
    ap.add_argument("--aspect", default="1:1")
    ap.add_argument("--size", default="1K", help="1K, 2K or 4K")
    ap.add_argument("--model", default=os.environ.get("ELISSA_IMAGE_MODEL", DEFAULT_MODEL))
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    from google import genai
    from google.genai import types
    from PIL import Image

    client = genai.Client(api_key=load_key())
    if args.list_models:
        for m in client.models.list():
            if "image" in m.name:
                print(m.name)
        return
    if not args.prompt:
        ap.error("falta el prompt")

    contents = [Image.open(r) for r in args.ref] + [args.prompt]
    response = client.models.generate_content(
        model=args.model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=args.aspect, image_size=args.size),
        ),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    saved = 0
    for part in response.parts or []:
        if part.inline_data:
            target = out if saved == 0 else out.with_stem(f"{out.stem}-{saved}")
            target.write_bytes(part.inline_data.data)
            print(target)
            saved += 1
        elif part.text:
            print(part.text, file=sys.stderr)
    if not saved:
        sys.exit("El modelo no devolvió imagen.")


if __name__ == "__main__":
    main()
