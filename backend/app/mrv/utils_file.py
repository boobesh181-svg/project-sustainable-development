"""File utilities for MRV ingestion APIs."""

import os
import uuid
import math
from typing import Tuple, Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException


def save_upload(file: UploadFile, prefix: str = "mrv_", upload_dir: str = "uploads/mrv") -> str:
    """
    Save uploaded file with safe filename and return the relative path.
    
    Args:
        file: UploadFile object from FastAPI
        prefix: Prefix for filename (default: "mrv_")
        upload_dir: Directory to save files (default: "uploads/mrv")
    
    Returns:
        Relative file path for storage in database
    """
    # Ensure upload directory exists
    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Generate safe filename
    file_extension = Path(file.filename).suffix if file.filename else ""
    safe_filename = f"{prefix}{uuid.uuid4().hex[:8]}{file_extension}"
    file_path = upload_path / safe_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        return str(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


def compute_geotag_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute distance between two geotag coordinates using Haversine formula.
    
    Args:
        lat1, lon1: First coordinate (degrees)
        lat2, lon2: Second coordinate (degrees)
    
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in kilometers
    r = 6371.0
    
    return c * r


def validate_file_type(file: UploadFile, allowed_types: list[str]) -> bool:
    """
    Validate uploaded file type.
    
    Args:
        file: UploadFile object
        allowed_types: List of allowed file extensions (e.g., ['.pdf', '.jpg', '.png'])
    
    Returns:
        True if file type is allowed
    """
    if not file.filename:
        return False
    
    file_extension = Path(file.filename).suffix.lower()
    return file_extension in allowed_types


def get_file_size_mb(file: UploadFile) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file: UploadFile object
    
    Returns:
        File size in MB
    """
    file.file.seek(0, 2)  # Seek to end
    size_bytes = file.file.tell()
    file.file.seek(0)     # Reset to beginning
    return size_bytes / (1024 * 1024)


def validate_file_size(file: UploadFile, max_size_mb: float = 10.0) -> bool:
    """
    Validate file size doesn't exceed maximum.
    
    Args:
        file: UploadFile object
        max_size_mb: Maximum allowed size in MB
    
    Returns:
        True if file size is acceptable
    """
    return get_file_size_mb(file) <= max_size_mb
