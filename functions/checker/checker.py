"""更新判定ロジック — Last-Modified/ETag比較 -> SHA-256フォールバック"""


def determine_update_status(
    fetch_result: dict,
    previous: dict | None,
) -> dict:
    if previous is None:
        return {"status": "updated", "method": "first_check"}

    if fetch_result.get("last_modified") and previous.get("last_modified"):
        changed = fetch_result["last_modified"] != previous["last_modified"]
        return {
            "status": "updated" if changed else "not_updated",
            "method": "last_modified",
        }

    if fetch_result.get("etag") and previous.get("etag"):
        changed = fetch_result["etag"] != previous["etag"]
        return {
            "status": "updated" if changed else "not_updated",
            "method": "etag",
        }

    changed = fetch_result.get("content_hash") != previous.get("content_hash")
    return {
        "status": "updated" if changed else "not_updated",
        "method": "content_hash",
    }
