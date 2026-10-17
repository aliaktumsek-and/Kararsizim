import json


def read_json(request):
    """Return the parsed JSON object body of a request, or None when it is invalid."""
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None
