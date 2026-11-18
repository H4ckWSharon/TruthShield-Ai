import hashlib
import io
from typing import Dict, Any
import numpy as np
from PIL import Image

try:
    import imagehash  # type: ignore
except ImportError:
    imagehash = None


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


def _bits_to_hex(bits: np.ndarray) -> str:
    flat = [1 if bool(b) else 0 for b in bits.flatten()[:64]]
    val = 0
    for bit in flat:
        val = (val << 1) | bit
    return f"{val:016x}"


def _numpy_ahash(img: Image.Image) -> str:
    arr = np.asarray(img.convert("L").resize((8, 8), Image.Resampling.LANCZOS), dtype=np.float32)
    return _bits_to_hex(arr > float(arr.mean()))


def _numpy_dhash(img: Image.Image) -> str:
    arr = np.asarray(img.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.float32)
    return _bits_to_hex(arr[:, 1:] > arr[:, :-1])


def _numpy_phash(img: Image.Image) -> str:
    arr = np.asarray(img.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
    n = 32
    k = np.arange(n, dtype=np.float32)[:, None]
    x = np.arange(n, dtype=np.float32)[None, :]
    dct_mat = np.cos(np.pi * (2.0 * x + 1.0) * k / (2.0 * n))
    dct2 = dct_mat @ arr @ dct_mat.T
    low = dct2[:8, :8]
    med = float(np.median(low))
    return _bits_to_hex(low > med)


def _numpy_whash(img: Image.Image) -> str:
    arr = np.asarray(img.convert("L").resize((16, 16), Image.Resampling.LANCZOS), dtype=np.float32)
    ll = 0.25 * (arr[0::2, 0::2] + arr[0::2, 1::2] + arr[1::2, 0::2] + arr[1::2, 1::2])
    return _bits_to_hex(ll > float(np.median(ll)))


def compute_perceptual_hashes(image_input: Any) -> Dict[str, str]:
    """
    Compute perceptual hashes (pHash, dHash, aHash, wHash) from PIL Image, file path, or bytes.
    Uses imagehash when installed and pure-NumPy/Pillow fallbacks in lightweight environments.
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

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        if imagehash is not None:
            return {
                "phash": str(imagehash.phash(img)),
                "dhash": str(imagehash.dhash(img)),
                "ahash": str(imagehash.average_hash(img)),
                "whash": str(imagehash.whash(img)),
            }

        return {
            "phash": _numpy_phash(img),
            "dhash": _numpy_dhash(img),
            "ahash": _numpy_ahash(img),
            "whash": _numpy_whash(img),
        }
    except Exception as e:
        return {
            "error": str(e),
            "phash": "",
            "dhash": "",
            "ahash": "",
            "whash": "",
        }


def compute_hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
    """
    Calculate Hamming distance between two hex-encoded image hashes.
    0 means identical perceptual hash. <= 10 indicates strong visual similarity.
    """
    try:
        if not hash1_hex or not hash2_hex:
            return 64
        if imagehash is not None:
            h1 = imagehash.hex_to_hash(hash1_hex)
            h2 = imagehash.hex_to_hash(hash2_hex)
            return int(h1 - h2)
        return (int(hash1_hex, 16) ^ int(hash2_hex, 16)).bit_count()
    except Exception:
        return 64


def calculate_similarity_score(hash1_hex: str, hash2_hex: str, hash_bits: int = 64) -> float:
    """
    Convert Hamming distance to a normalized similarity percentage [0.0, 1.0].
    1.0 = exact perceptual match.
    """
    dist = compute_hamming_distance(hash1_hex, hash2_hex)
    similarity = max(0.0, min(1.0, 1.0 - (dist / hash_bits)))
    return round(similarity, 4)
