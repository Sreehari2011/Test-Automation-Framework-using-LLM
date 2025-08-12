import re

def sanitize_identifier_for_method_name(raw_identifier_str, category_for_fallback="element"):
    """
    Sanitize a raw identifier string to be a valid Python method name part.
    Replaces non-alphanumeric characters with underscores, strips leading/trailing underscores,
    prepends underscore if starts with digit, and provides fallback name if empty.
    """
    if not raw_identifier_str:
        return f"unnamed_{str(category_for_fallback).lower().replace(' ', '_')}"
    sane_name = re.sub(r'\W+', '_', str(raw_identifier_str).lower())
    sane_name = sane_name.strip('_')
    if not sane_name:
        sane_name = f"unnamed_{str(category_for_fallback).lower().replace(' ', '_')}"
    if sane_name[0].isdigit():
        sane_name = '_' + sane_name
    return sane_name