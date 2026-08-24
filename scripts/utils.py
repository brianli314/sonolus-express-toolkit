import zipfile
import os

def localize(value, locale="en"):
    if isinstance(value, list):
        return [localize(item, locale) for item in value]

    elif isinstance(value, dict):
        if "title" in value:
            return {
                **value,
                "title": localize(value["title"], locale)
            }
    elif not isinstance (value, str):
        return value
    return {locale: "" if value is None else str(value)}

def extract_scp(scp, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(scp, 'r') as zip_ref:
        zip_ref.extractall(out_dir)
        print(f"Extracted all files to: {out_dir}")