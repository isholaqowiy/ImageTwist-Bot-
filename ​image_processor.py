import os
from PIL import Image

def rotate_image(image_path: str, angle: float, output_path: str) -> bool:
    """Rotates an image by a specific angle while preserving alpha transparency."""
    try:
        with Image.open(image_path) as img:
            # Preserve transparency configurations for PNG/WEBP variations
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert('RGBA')
            
            # expand=True ensures the canvas expands to prevent clipping the corners
            rotated = img.rotate(angle, expand=True, resample=Image.BICUBIC)
            rotated.save(output_path, quality=100, subsampling=0)
            return True
    except Exception:
        return False

def flip_image(image_path: str, direction: str, output_path: str) -> bool:
    """Flips an image horizontally, vertically, or both."""
    try:
        with Image.open(image_path) as img:
            if direction == "horizontal":
                flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif direction == "vertical":
                flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
            elif direction == "both":
                flipped = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
            else:
                return False
            
            flipped.save(output_path, quality=100, subsampling=0)
            return True
    except Exception:
        return False

def resize_image(image_path: str, width: int, height: int, output_path: str) -> bool:
    """Resizes an image, maintaining aspect ratio if one dimension is missing."""
    try:
        with Image.open(image_path) as img:
            orig_w, orig_h = img.size
            
            if width and not height:
                height = int((width / orig_w) * orig_h)
            elif height and not width:
                width = int((height / orig_h) * orig_w)
            elif not width and not height:
                return False
                
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_path, quality=100, subsampling=0)
            return True
    except Exception:
        return False

