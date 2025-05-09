import io
import hashlib
from pathlib import Path
from typing import Tuple, Dict, Any

import pydicom
from pydicom import FileDataset
from pydicom.errors import InvalidDicomError
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydicom.tag import Tag
import numpy as np
from PIL import Image


def parse_dicom_tag(tag_string: str) -> Tuple[str, str]:
    tag_string_cleaned = tag_string.strip()
    parts = tag_string_cleaned.split(",")

    if len(parts) != 2:
        raise ValueError(
            "Tag string must contain exactly one comma inside parentheses."
        )

    group_str = parts[0].strip()
    element_str = parts[1].strip()

    try:
        group_int = int(group_str, 16)
        element_int = int(element_str, 16)
    except ValueError:
        raise ValueError(f"Invalid hex values in tag: '{group_str}', '{element_str}'.")

    return (group_int, element_int)


def get_file_path(file_id: str, upload_dir: Path) -> Path:
    return upload_dir / f"{file_id}.dcm"


def is_valid_dicom_file(file_path: Path) -> bool:
    try:
        pydicom.dcmread(file_path, stop_before_pixels=True)
        return True
    except (InvalidDicomError, OSError, IOError):
        return False
    except Exception:
        return False


def calculate_file_hash(file_content: bytes) -> str:
    hash_obj = hashlib.sha256()
    hash_obj.update(file_content)
    return hash_obj.hexdigest()


def dicom_value_to_header(elem):
    # Skip sequence elements and empty elements
    if elem.VR in ["SQ"] or elem.value is None:
        return None

    try:
        if hasattr(elem.value, "__iter__") and not isinstance(elem.value, str):
            value = ", ".join(str(x) for x in elem.value)
        else:
            value = str(elem.value)

        value = value.replace("\n", " ").replace("\r", "")

        return value.strip() if value and value.strip() else None
    except:
        return None


def convert_dicom_to_png(dicom_dataset) -> bytes:
    """
    Converts a DICOM dataset to a PNG image using a robust normalization approach.
    """
    try:
        pixel_array = dicom_dataset.pixel_array

        # Find min and max values, using nanmin/nanmax to handle any NaN values safely
        min_val = np.nanmin(pixel_array)
        max_val = np.nanmax(pixel_array)

        # Apply normalization only if we have valid finite values and a non-zero range
        if np.isfinite(min_val) and np.isfinite(max_val) and max_val > min_val:
            normalized_image = ((pixel_array - min_val) / (max_val - min_val)) * 255.0
        else:
            normalized_image = np.zeros_like(pixel_array)

        png_image = np.clip(normalized_image, 0, 255).astype(np.uint8)

        # Create a PIL (Pillow) Image object from the NumPy array
        image = Image.fromarray(png_image)

        byte_io = io.BytesIO()
        image.save(byte_io, format="PNG", optimize=True)
        byte_io.seek(0)

        return byte_io.getvalue()

    except AttributeError:
        raise ValueError("DICOM dataset doesn't contain pixel data")
    except Exception as e:
        raise ValueError(f"Error processing DICOM pixel data: {str(e)}")


def dicom_upload(
    file_id: str,
    tag: str,
    dicom_dataset: FileDataset,
    response_data: Dict[str, Any],
):
    """Processes DICOM data by extracting the specified tag and converting to PNG with appropriate metadata headers"""

    # Extract tag attribute
    try:
        group_int, element_int = parse_dicom_tag(tag)
        dicom_tag = Tag(group_int, element_int)

        element = dicom_dataset.get(dicom_tag)
        if element is None:
            if (
                dicom_tag.group == 0x0002
                and hasattr(dicom_dataset, "file_meta")
                and dicom_dataset.file_meta
            ):
                element = dicom_dataset.file_meta.get(dicom_tag)

        if element:
            response_data["tag_data"] = {
                "tag": str(element.tag),
                "keyword": element.keyword,
                "vr": element.VR,
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"Tag {tag} not found in DICOM file"
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid tag format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting tag: {str(e)}")

    # Convert to PNG if the file has pixel data
    if hasattr(dicom_dataset, "pixel_array"):
        try:
            png_data = convert_dicom_to_png(dicom_dataset)

            image_headers = {
                "Content-Disposition": f"inline; filename={file_id}.png",
                "X-DICOM-ID": file_id,
                "X-Tag": str(response_data["tag_data"]["tag"]),
                "X-Keyword": str(response_data["tag_data"]["keyword"]),
                "X-VR": str(response_data["tag_data"]["vr"]),
            }

            # Group 0x0028 contains image-specific attributes (Image Pixel module)
            # Group 0x0018 contains acquisition-related attributes (often image-related)
            # Group 0x0008 contains study/series information (patient, study descriptions)
            # Reference: https://dicom.innolitics.com/ciods
            image_related_groups = [0x0008, 0x0018, 0x0028]

            for elem in dicom_dataset:
                if elem.tag.group in image_related_groups:
                    value = dicom_value_to_header(elem)
                    if value:
                        header_name = (
                            f"X-DICOM-{elem.keyword}"
                            if hasattr(elem, "keyword") and elem.keyword
                            else f"X-DICOM-{elem.tag.group}-{elem.tag.element}"
                        )
                        image_headers[header_name] = value
            return StreamingResponse(
                io.BytesIO(png_data), media_type="image/png", headers=image_headers
            )
        except Exception as e:
            response_data["png_error"] = f"Error converting to PNG: {str(e)}"
    else:
        response_data["png_error"] = "DICOM file does not contain image data"

    return response_data
