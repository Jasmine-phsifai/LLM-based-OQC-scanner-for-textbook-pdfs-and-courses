"""Run an explicit live diagnostic against public Bilibili endpoints."""

from __future__ import annotations


def diagnose_bilibili_api() -> None:
    """Print connectivity and metadata diagnostics for fixed public videos."""
    import re
    import subprocess

    from curl_cffi.requests import Session

    session = Session(impersonate="chrome")
    session.get("https://www.bilibili.com/", timeout=15)
    response = session.get(
        "https://api.bilibili.com/x/frontend/finger/spi",
        timeout=15,
    )
    data = response.json()["data"]
    session.cookies.set("buvid3", data["b_3"], domain=".bilibili.com")
    session.cookies.set("buvid4", data["b_4"], domain=".bilibili.com")

    test_cases = [
        ("BV1zPD6BzEZy", "短视频1 (awesome-design-md)"),
    ]
    for bvid, label in test_cases:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        response = session.get(api_url, timeout=15)
        info = response.json()
        print(f"\n=== {label} ===")
        print(f"Code: {info.get('code')}")
        if info.get("code") != 0:
            print(f"Error: {info.get('message')}")
            continue

        video = info["data"]
        print(f"Title: {video.get('title')}")
        print(f"Duration: {video.get('duration')}s")
        print(f"Parts: {video.get('videos')}")
        for part in video.get("pages", [])[:5]:
            print(f"  P{part['page']}: {part['part']} ({part['duration']}s)")
        print(f"  Main CID: {video.get('cid')}")
        statistics = video.get("stat", {})
        print(f"  AID: {video.get('aid')}")
        print(
            "  Views: "
            f"{statistics.get('view')}, Danmakus: {statistics.get('danmaku')}, "
            f"Replies: {statistics.get('reply')}"
        )

    print("\n=== 短链接解析 ===")
    for short_url, label in [
        ("https://b23.tv/LmGncCM", "短视频2"),
        ("https://b23.tv/m1QoLsK", "长视频系列"),
    ]:
        result = subprocess.run(
            ["curl", "-sIL", "-o", "NUL", "-w", "%{url_effective}", short_url],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        final_url = result.stdout.strip()
        print(f"{label}: {final_url}")

        match = re.search(r"BV(\w+)", final_url)
        if match is None:
            continue
        bvid = "BV" + match.group(1)
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        response = session.get(api_url, timeout=15)
        info = response.json()
        if info.get("code") != 0:
            continue
        video = info["data"]
        print(f"  Title: {video.get('title')}")
        print(f"  Duration: {video.get('duration')}s, Parts: {video.get('videos')}")
        for part in video.get("pages", [])[:3]:
            print(f"    P{part['page']}: {part['part']} ({part['duration']}s)")
        statistics = video.get("stat", {})
        print(
            f"  Danmakus: {statistics.get('danmaku')}, "
            f"Replies: {statistics.get('reply')}"
        )


if __name__ == "__main__":
    diagnose_bilibili_api()
