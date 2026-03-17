---
name: nano-banana-2
version: 1.0.0
description: "Generate images using Google's Nano Banana 2 (Gemini 3.1 Flash Image). This is a faster alternative to Nano Banana Pro. Use when the user says 'nano2' or 'nano-banana-2'."
metadata:
  openclaw:
    category: "multimedia"
    requires:
      bins: ["uv"]
---

# nano-banana-2

This skill uses the `gemini-3.1-flash-image-preview` model to generate images. It is faster and may have different rate limits than the Pro version.

## Usage

```bash
uv run scripts/generate_image_v2.py --prompt "description" --filename "output.png"
```

### Parameters

- `--prompt`, `-p`: Image description (required)
- `--filename`, `-f`: Output filename (required)
- `--resolution`, `-r`: `1K`, `2K`, or `4K` (default: `1K`)
- `--aspect-ratio`, `-a`: Output aspect ratio (e.g., `1:1`, `16:9`, `3:4`)
- `--input-image`, `-i`: Path to an existing image for editing/inpainting (can be used up to 14 times)

## Implementation Details

The underlying script is located at `scripts/generate_image_v2.py`. It requires the `google-genai` and `pillow` Python packages.

## Note

This skill is intended for use when the Pro model is unavailable or when speed is prioritized.
