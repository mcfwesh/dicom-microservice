import os
import uuid
import json
from pathlib import Path
from typing import Dict
import random


from fastapi import FastAPI, UploadFile, File, HTTPException, Query
import pydicom
from pydicom.tag import Tag

from src.utils import (
    is_valid_dicom_file,
    get_file_path,
    calculate_file_hash,
    dicom_upload,
)

app = FastAPI(
    title="DICOM Microservice API",
    description="A service for uploading, querying, and converting DICOM files.",
    version="0.0.0",
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
FILE_HASH_MAP = {}
HASH_MAP_PATH = UPLOAD_DIR / "hash_map.json"

# Load the hash map from file if it exists
if HASH_MAP_PATH.exists():
    try:
        with open(HASH_MAP_PATH, "r") as f:
            FILE_HASH_MAP = json.load(f)
    except json.JSONDecodeError:
        FILE_HASH_MAP = {}


@app.get("/healthz")
async def health() -> Dict[str, str]:
    return {"status": "OK"}


@app.post("/dicom/upload")
async def process_dicom(
    file: UploadFile = File(..., description="DICOM file to process"),
    tag: str = Query(
        ...,
        description="DICOM tag in format 'XXXX,XXXX' to extract (e.g., '0010,0010' for Patient Name)",
    ),
):
    """Uploads DICOM file, detects duplicates, extracts specified tag, and returns PNG conversion"""

    # Upload and validate the DICOM file
    try:
        file_content = await file.read()

        file_hash = calculate_file_hash(file_content)

        # Check if this file has been uploaded before
        existing_file_id = None
        if file_hash in FILE_HASH_MAP:
            existing_file_id = FILE_HASH_MAP[file_hash]
            existing_file_path = get_file_path(existing_file_id, UPLOAD_DIR)
            if not existing_file_path.exists():
                existing_file_id = None

        # If this is a duplicate and the file exists, use the existing file_id
        if existing_file_id:
            file_id = existing_file_id
            file_path = get_file_path(file_id, UPLOAD_DIR)
        else:
            file_id = str(uuid.uuid4())

            file_path = get_file_path(file_id, UPLOAD_DIR)

            with open(file_path, "wb") as f:
                f.write(file_content)

            # Verify that the uploaded file is a valid DICOM file
            if not is_valid_dicom_file(file_path):
                os.unlink(file_path)
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded file is not a valid DICOM file",
                )

            FILE_HASH_MAP[file_hash] = file_id
            with open(HASH_MAP_PATH, "w") as f:
                json.dump(FILE_HASH_MAP, f)

        dicom_dataset = pydicom.dcmread(file_path)

        response_data = {
            "file_id": file_id,
            "filename": file.filename,
            "success": True,
            "is_duplicate": existing_file_id is not None,
        }

        return dicom_upload(file_id, tag, dicom_dataset, response_data)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing DICOM file: {str(e)}"
        )


@app.post("/random_file")
async def process_existing_file(
    tag: str = Query(
        ...,
        description="DICOM tag in format 'XXXX,XXXX' to extract (e.g., '0010,0010' for Patient Name)",
    ),
):
    """Selects a random DICOM file from uploads directory, extracts the specified tag, and returns PNG conversion"""

    try:
        if len(list(UPLOAD_DIR.iterdir())) == 0:
            raise HTTPException(
                status_code=404, detail="No DICOM files found in uploads directory"
            )

        file_path = [
            f for f in UPLOAD_DIR.iterdir() if f.is_file() and f.name != "hash_map.json"
        ]

        dicom_file = random.choice(file_path)

        if not dicom_file:
            raise HTTPException(
                status_code=404, detail="No DICOM files found in uploads directory"
            )
        dicom_dataset = pydicom.dcmread(dicom_file)
        file_id = dicom_file.name.replace(".dcm", "")

        response_data = {
            "file_id": file_id,
            "success": True,
        }
        return dicom_upload(file_id, tag, dicom_dataset, response_data)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing DICOM file: {str(e)}"
        )
