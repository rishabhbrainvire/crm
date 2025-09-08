import frappe

import os
import base64
import frappe
import requests
from urllib.parse import urlparse, unquote
from werkzeug.utils import secure_filename

@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_image(image: str = None, file: str = None, base64_data: str = None):
    """
    Save an image into app's public/barkisse-images folder.
    Can accept:
    - image: URL string
    - file: uploaded file (multipart/form-data)
    - base64_data: base64 encoded image string
    """

    try:
        # Path inside your app's public/barkisse-images
        public_path = os.path.join(
            frappe.get_app_path("crm"), "public", "barkisse-images"
        )
        os.makedirs(public_path, exist_ok=True)

        filename = None
        file_path = None

        # 1. If image URL is provided
        if image:
            parsed_url = urlparse(image)
            filename = os.path.basename(parsed_url.path)
            filename = unquote(filename) or "downloaded_image.jpg"

            response = requests.get(image, stream=True, timeout=15)
            response.raise_for_status()

            file_path = os.path.join(public_path, filename)
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

        # 2. If file is uploaded (form-data)
        elif frappe.request and "file" in frappe.request.files:
            uploaded_file = frappe.request.files["file"]
            filename = secure_filename(uploaded_file.filename) or "uploaded_image.jpg"

            file_path = os.path.join(public_path, filename)
            uploaded_file.save(file_path)

        # 3. If base64 data is provided
        elif base64_data:
            header, encoded = base64_data.split(",", 1) if "," in base64_data else (None, base64_data)
            decoded = base64.b64decode(encoded)

            # try to guess extension
            ext = "jpg"
            if header and "png" in header:
                ext = "png"
            elif header and "gif" in header:
                ext = "gif"

            filename = f"base64_image.{ext}"
            file_path = os.path.join(public_path, filename)

            with open(file_path, "wb") as f:
                f.write(decoded)

        else:
            return {"status": "error", "message": "No valid image input provided"}

        return {
            "status": "success",
            "filename": filename,
            "url": f"/assets/crm/barkisse-images/{filename}"
        }

    except Exception as e:
        frappe.log_error(message=str(e), title="Image Upload Error")
        return {"status": "error", "message": str(e)}
