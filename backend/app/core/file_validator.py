from pathlib import Path
from typing import Tuple

class UnsafeFileTypeError(ValueError):
    pass

# Dangerous magic headers (PE/EXE/DLL, ELF, Mach-O, Shebang scripts)
_DANGEROUS_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"#!",
)

def inspect_file_magic(data: bytes, filename: str = "") -> Tuple[str, str]:
    """
    Validate file contents using binary magic bytes rather than trusting client-supplied
    Content-Type headers or extensions.
    Returns (verified_mime_type, evidence_category).
    Raises UnsafeFileTypeError for executables or unsupported binary formats.
    """
    if not data or len(data) < 4:
        raise UnsafeFileTypeError("File payload is empty or too short for signature verification.")

    header = data[:64]

    for sig in _DANGEROUS_PREFIXES:
        if header.startswith(sig):
            raise UnsafeFileTypeError("Executable or script binaries are prohibited in the evidence vault.")

    # Images
    if header.startswith(b"\xff\xd8\xff"):
        return ("image/jpeg", "image")
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ("image/png", "image")
    if header.startswith((b"GIF87a", b"GIF89a")):
        return ("image/gif", "image")
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return ("image/webp", "image")
    if header.startswith(b"BM"):
        return ("image/bmp", "image")
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return ("image/tiff", "image")

    # Audio / Video containers
    if header.startswith(b"RIFF") and len(header) >= 12:
        fourcc = header[8:12]
        if fourcc == b"WAVE":
            return ("audio/wav", "audio")
        if fourcc == b"AVI ":
            return ("video/x-msvideo", "video")

    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand.startswith(b"M4A"):
            return ("audio/mp4", "audio")
        return ("video/mp4", "video")

    if header.startswith(b"\x1a\x45\xdf\xa3"):
        # Matroska / WebM
        ext = Path(filename).suffix.lower()
        if ext == ".webm":
            return ("video/webm", "video")
        return ("video/x-matroska", "video")

    if header.startswith(b"ID3") or (header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
        # Differentiate ADTS AAC vs MP3
        if header[0] == 0xFF and (header[1] & 0xF6) in (0xF0, 0xF8):
            return ("audio/aac", "audio")
        return ("audio/mpeg", "audio")

    if header.startswith(b"OggS"):
        return ("audio/ogg", "audio")
    if header.startswith(b"fLaC"):
        return ("audio/flac", "audio")

    # Documents
    if header.startswith(b"%PDF-"):
        return ("application/pdf", "document")

    # Plain text documents (strictly reject null bytes / HTML script injection)
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".json", ".csv", ".log", ".md"}:
        if b"\x00" in data[:4096]:
            raise UnsafeFileTypeError("Binary bytes detected inside text document.")
        lower_sample = data[:1024].lower()
        if b"<script" in lower_sample or b"<html" in lower_sample:
            raise UnsafeFileTypeError("Active HTML/script markup is not allowed in text evidence.")
        return ("text/plain", "document")

    raise UnsafeFileTypeError(
        "Unsupported or unrecognized file signature. Allowed formats: JPEG, PNG, GIF, WebP, BMP, TIFF, MP4, MOV, WebM, AVI, WAV, MP3, OGG, FLAC, PDF, TXT/JSON/CSV."
    )
