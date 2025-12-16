# -*- coding: utf-8 -*-
# @file image.py
# @brief Utilities to Read Image, transform from image to bytes and vice versa
# @author sailing-innocent
# @date 2025-04-24
# @version 1.0
# ---------------------------------

from PIL import Image
from io import BytesIO
import numpy as np
import logging

from typing import Union, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------
# Image to Bytes
# ------------------------------------------------

def image_to_bytes(image: Union[Image.Image, np.ndarray], format: str = "PNG") -> bytes:
    """
    Convert an image to bytes.
    
    Args:
        image (Union[Image.Image, np.ndarray]): The image to convert.
        format (str): The format to save the image in. Default is "PNG".
        
    Returns:
        bytes: The image as bytes.
    """
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    
    with BytesIO() as output:
        image.save(output, format=format)
        return output.getvalue()
    

# ------------------------------------------------
# Bytes to Image
# ------------------------------------------------

def bytes_to_image(image_bytes: bytes) -> Image.Image:
    """
    Convert bytes to an image.
    
    Args:
        image_bytes (bytes): The bytes to convert.
        
    Returns:
        Image.Image: The image.
    """
    with BytesIO(image_bytes) as input_stream:
        image = Image.open(input_stream)
        image.load() # Force loading the image data before the stream is closed
        return image.convert("RGB")