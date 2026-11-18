import hashlib
import io
from typing import Dict, Any, Optional
from PIL import Image
import imagehash

def compute_sha256_from_bytes(data: bytes) -> str:
    """Calculate cryptographic SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()

def compute_sha256_from_file(file_path: str) -> str:
    """Calculate cryptographic SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def compute_perceptual_hashes(image_input: Any) -> Dict[str, str]:
    """
    Compute perceptual hashes (pHash, dHash, aHash, wHash) from PIL Image, file path, or bytes.
    Perceptual hashes remain invariant under compression, scaling, minor cropping, and watermarking.
    """
    try:
        if isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, str):
            img = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise ValueError("Unsupported image input type")
        
        # Ensure image is in RGB or L
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
            
        phash_val = str(imagehash.phash(img))
        dhash_val = str(imagehash.dhash(img))
        ahash_val = str(imagehash.average_hash(img))
        whash_val = str(imagehash.whash(img))
        
        return {
            "phash": phash_val,
            "dhash": dhash_val,
            "ahash": ahash_val,
            "whash": whash_val
        }
    except Exception as e:
        return {
            "error": str(e),
            "phash": "",
            "dhash": "",
            "ahash": "",
            "whash": ""
        }

def compute_hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
    """
    Calculate Hamming distance between two hex-encoded image hashes.
    0 means identical perceptual hash. <= 10 indicates strong visual similarity.
    """
    try:
        h1 = imagehash.hex_to_hash(hash1_hex)
        h2 = imagehash.hex_to_hash(hash2_hex)
        return int(h1 - h2)
    except Exception:
        return 64 # Max distance for standard 64-bit hash

def calculate_similarity_score(hash1_hex: str, hash2_hex: str, hash_bits: int = 64) -> float:
    """
    Convert Hamming distance to a normalized similarity percentage [0.0, 1.0].
    1.0 = exact perceptual match.
    """
    dist = compute_hamming_distance(hash1_hex, hash2_hex)
    similarity = max(0.0, min(1.0, 1.0 - (dist / hash_bits)))
    return round(similarity, 4)
