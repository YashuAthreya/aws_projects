# app/request_utils.py

from fastapi import Request


async def parse_json_or_form(request: Request) -> dict:
    """Parse a request body as JSON or as multipart/urlencoded form data.

    Repeated form fields ending in "[]" are collapsed into lists, matching
    the shape the frontend forms already send.
    """
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}

    form_data = await request.form()
    data: dict = {}
    for key, value in form_data.multi_items():
        clean_key = key[:-2] if key.endswith("[]") else key
        if clean_key in data:
            if not isinstance(data[clean_key], list):
                data[clean_key] = [data[clean_key]]
            data[clean_key].append(value)
        else:
            data[clean_key] = value

    return data
