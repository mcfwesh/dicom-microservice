"""
Data models for the DICOM Microservice API.

This module defines Pydantic models for request and response data structures
used in the API. Pydantic provides data validation and serialization.
"""

# Third-party imports
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class DicomUploadResponse(BaseModel):
    """
    Response model for a successful DICOM file upload.

    Attributes:
        file_id (str): The unique identifier assigned to the uploaded DICOM file.
        success (bool): Indicator of successful upload operation.
        filename (str): The original filename of the uploaded DICOM file.
    """

    file_id: str = Field(
        ..., description="Unique identifier for the uploaded DICOM file"
    )
    success: bool = Field(
        True, description="Indicates whether the upload was successful"
    )
    filename: str = Field(
        ..., description="Original filename of the uploaded DICOM file"
    )


class DicomAttributeResponse(BaseModel):
    """
    Response model for a DICOM attribute query.

    Attributes:
        tag (str): The DICOM tag that was queried (e.g., "0010,0010").
        value (Any): The value of the requested DICOM attribute.
        vr (str): Value Representation - the DICOM data type of the attribute.
    """

    tag: str = Field(
        ..., description="DICOM tag in format 'group,element' (e.g., '0010,0010')"
    )
    value: Any = Field(..., description="Value of the requested DICOM attribute")
    vr: str = Field(..., description="Value Representation (DICOM data type)")
