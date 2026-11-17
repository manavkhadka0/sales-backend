import re
from typing import Any, Set


def is_oil_bottle(product_name: str) -> bool:
    """
    Check if the product is an oil bottle.
    Excludes sachets, shampoo, facewash, lotion, and cream.
    Includes products mentioning baldness, hairfall, dandruff, oil, or yachu.
    """
    if not product_name:
        return False
    name = product_name.lower().strip()
    if any(
        k in name
        for k in [
            "sachet",
            "shampoo",
            "facewash",
            "face wash",
            "lotion",
            "cream",
        ]
    ):
        return False
    if any(k in name for k in ["baldness", "hairfall", "dandruff", "oil", "yachu"]):
        return True
    return False


def sanitize_sheet_title(name: Any, existing_titles: Set[str]) -> str:
    """
    Sanitizes sheet titles for openpyxl / Excel compatibility:
    - Maximum 31 characters.
    - Strips invalid characters: \\ / ? * : [ ]
    - Avoids duplicate sheet titles (case-insensitive).
    """
    raw_name = str(name).strip() if name else "Unassigned"
    # Replace illegal Excel sheet title characters with a hyphen
    clean_name = re.sub(r"[\\/*?:\[\]]", "-", raw_name).strip()
    if not clean_name:
        clean_name = "Unassigned"

    # Truncate to maximum 28 chars to leave headroom for collision counters
    base_title = clean_name[:28].strip()
    candidate = base_title or "Franchise"
    counter = 1

    lower_titles = {t.lower() for t in existing_titles}
    while candidate.lower() in lower_titles:
        suffix = f"_{counter}"
        avail_len = 31 - len(suffix)
        candidate = f"{base_title[:avail_len]}{suffix}"
        counter += 1

    existing_titles.add(candidate)
    return candidate
