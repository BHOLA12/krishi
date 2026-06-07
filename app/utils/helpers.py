import os
import uuid
import shutil
from fastapi import UploadFile

def save_upload_file(upload_file: UploadFile, destination_dir: str) -> str:
    """
    Saves an uploaded file to a target destination directory with a unique UUID name
    to prevent file name collisions.
    """
    os.makedirs(destination_dir, exist_ok=True)
    file_extension = os.path.splitext(upload_file.filename)[1]
    if not file_extension:
        file_extension = ".wav"  # Default fallback
        
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(destination_dir, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
        
    return file_path


# =============================================================================
# ❌ PURANA CODE — WHISPER CRASH KARTA THA (ISLIYE BADLA)
# =============================================================================
# def convert_audio_format(input_path: str, target_format: str = "wav") -> str:
#     base, ext = os.path.splitext(input_path)
#     if ext.lower() == f".{target_format}":
#         return input_path
#
#     output_path = f"{base}_converted.{target_format}"
#
#     # Just copying for the sake of MVP completeness, assuming WAV inputs or ffmpeg fallback.
#     shutil.copy(input_path, output_path)    # ← YAHAN PROBLEM THI!
#     return output_path
#
# ⚠️  KYU BADLA (WHY WE CHANGED):
#     Twilio recording download karta hai .mp3 format mein.
#     Exotel bhi .mp3 bhejta hai.
#
#     Purana code kya karta tha:
#       - file.mp3 ko copy karo
#       - Copy ka naam badlo → file_converted.wav
#       - Return karo "yeh WAV hai" bolke
#
#     Problem: File ke andar ka data .mp3 hi rehta tha!
#     Sirf naam badla, format nahi badla.
#
#     Jab Faster-Whisper is "fake WAV" ko padtha:
#       RuntimeError: FLAC or WAV file expected, got format: MPEG
#       → Transcription fail → Pipeline crash
#       → Farmer ko hardcoded "dhaan ki patti" wala answer milta
#         chahe usne kuch bhi poocha ho (beemar gaay, loan, kuch bhi)
#
#     Fix: Real ffmpeg command chalao jo actually format convert kare:
#       - .mp3 → actual PCM WAV (16kHz, mono) — jo Whisper chahta hai
#       - Agar ffmpeg nahi hai toh warning do aur copy fallback use karo
# =============================================================================

# ✅ NAYA CODE — Real ffmpeg transcoding
def convert_audio_format(input_path: str, target_format: str = "wav") -> str:
    """
    Transcodes audio file to 16kHz mono WAV using ffmpeg.
    Twilio/Exotel .mp3 → PCM WAV jo Faster-Whisper padh sake.
    """
    import subprocess  # nosec B404

    base, ext = os.path.splitext(input_path)
    if ext.lower() == f".{target_format}":
        return input_path

    output_path = f"{base}_converted.{target_format}"

    try:
        subprocess.run(  # nosec B603 B607
            [
                "ffmpeg", "-y",          # Overwrite output if exists
                "-i", input_path,        # Input file
                "-ar", "16000",          # 16kHz sample rate (Whisper requirement)
                "-ac", "1",              # Mono channel
                "-f", target_format,     # Output format
                output_path
            ],
            check=True,
            capture_output=True,
            timeout=30                   # 30-second timeout for large files
        )
        return output_path
    except FileNotFoundError:
        # ffmpeg not installed — warn and fall back (development only)
        import logging
        logging.getLogger(__name__).warning(
            "ffmpeg not found. Falling back to raw file copy (dev mode only). "
            "Install ffmpeg for production use."
        )
        shutil.copy(input_path, output_path)
        return output_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg failed to transcode {input_path}: {e.stderr.decode('utf-8', errors='replace')}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ffmpeg transcoding timed out for {input_path}") from e


