# DICOM Microservice

## Features

- Upload DICOM files with duplicate detection
- Extract tag values from DICOM files
- Convert DICOM images to PNG format
- Process random existing DICOM files

## Installation

```bash
# Create virtual environment
python -m venv .pockethealth-venv
source .pockethealth-venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Service

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be available at http://localhost:8000

## Testing Endpoints

Navigate to http://localhost:8000/docs in your browser to access the interactive API documentation. You can:

- Test all endpoints directly from the browser
- Upload DICOM files via the UI
- View images along with response headers and bodies
