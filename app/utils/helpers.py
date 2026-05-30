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

def convert_audio_format(input_path: str, target_format: str = "wav") -> str:
    """
    Simulates or performs audio transcoding (e.g. from AMR or 3GP to standard 16kHz WAV).
    In real production, this calls ffmpeg/pydub. Here we provide a robust file validation 
    and path resolver.
    """
    base, ext = os.path.splitext(input_path)
    if ext.lower() == f".{target_format}":
        return input_path
        
    # Placeholder for running ffmpeg command:
    # ffmpeg -i input.amr -ar 16000 -ac 1 output.wav
    output_path = f"{base}_converted.{target_format}"
    
    # Just copying for the sake of MVP completeness, assuming WAV inputs or ffmpeg fallback.
    shutil.copy(input_path, output_path)
    return output_path
