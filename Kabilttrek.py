#!/usr/bin/env python3

import requests
import os
import sys
from datetime import datetime

CHANNEL_API_URL = "https://core-api.kablowebtv.com/api/channels"
TOKEN_API_URL   = "https://core-api.kablowebtv.com/api/auth/token"
OUTPUT_FILE     = "kablo_tv.m3u"

STATIC_TOKEN = os.environ.get(
    "KABLO_TOKEN",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbnYiOiJMSVZFIiwiaXBiIjoiMCIsImNnZCI6IjA5M2Q3MjBhLTUwMmMtNDFlZC1hODBmLTJiODE2OTg0ZmI5NSIsImNzaCI6IlRSS1NUIiwiZGN0IjoiM0VGNzUiLCJkaSI6ImE2OTliODNmLTgyNmItNGQ5OS05MzYxLWM4YTMxMzIxOGQ0NiIsInNnZCI6Ijg5NzQxZmVjLTFkMzMtNGMwMC1hZmNkLTNmZGFmZTBiNmEyZCIsInNwZ2QiOiIxNTJiZDUzOS02MjIwLTQ0MjctYTkxNS1iZjRiZDA2OGQ3ZTgiLCJpY2giOiIwIiwiaWRtIjoiMCIsImlhIjoiOjpmZmZmOjEwLjAuMC4yMDYiLCJhcHYiOiIxLjAuMCIsImFibiI6IjEwMDAiLCJuYmYiOjE3NDUxNTI4MjUsImV4cCI6MTc0NTE1Mjg4NSwiaWF0IjoxNzQ1MTUyODI1fQ.OSlafRMxef4EjHG5t6TqfAQC7y05IiQjwwgf6yMUS9E"
)

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

SKIP_CATEGORIES = {"Bilgilendirme"}


def get_auth_headers(token: str) -> dict:
    return {**BASE_HEADERS, "Authorization": f"Bearer {token}"}


def refresh_token(old_token: str) -> str:
    try:
        resp = requests.post(
            TOKEN_API_URL,
            headers=get_auth_headers(old_token),
            json={"refreshToken": old_token},
            timeout=15,
        )
        if resp.ok:
            new_token = resp.json().get("Data", {}).get("Token")
            if new_token:
                print(f"[{_now()}] token refreshed")
                return new_token
    except Exception as e:
        print(f"[{_now()}] token refresh failed: {e}")
    return old_token


def fetch_channels(token: str) -> list:
    resp = requests.get(
        CHANNEL_API_URL,
        headers=get_auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("IsSucceeded"):
        raise ValueError(f"API error: {data.get('Message', 'unknown')}")

    channels = data.get("Data", {}).get("AllChannels")
    if not channels:
        raise ValueError("Channel list is empty.")

    return channels


def build_m3u(channels: list) -> str:
    lines = ["#EXTM3U"]
    count = 0

    for ch in channels:
        name = ch.get("Name", "").strip()
        stream_url = ch.get("StreamData", {}).get("HlsStreamUrl", "").strip()
        if not name or not stream_url:
            continue

        categories = ch.get("Categories") or [{}]
        group = (categories[0].get("Name") or "General").strip()
        if group in SKIP_CATEGORIES:
            continue

        ch_id = ch.get("Id", "")
        logo  = ch.get("PrimaryLogoImageUrl", "")

        lines.append(
            f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{name}" '
            f'tvg-logo="{logo}" group-title="{group}",{name}'
        )
        lines.append(stream_url)
        count += 1

    print(f"[{_now()}] {count} channels added.")
    return "\n".join(lines) + "\n"


def save(content: str, path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[{_now()}] saved to '{path}'")


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def main():
    token = refresh_token(STATIC_TOKEN)

    try:
        channels = fetch_channels(token)
    except Exception as e:
        print(f"[{_now()}] first attempt failed ({e}), retrying with refreshed token...")
        token = refresh_token(token)
        channels = fetch_channels(token)

    save(build_m3u(channels), OUTPUT_FILE)
    print(f"[{_now()}] done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = f"[{datetime.utcnow().isoformat()}] ERROR: {exc}"
        print(msg, file=sys.stderr)
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        sys.exit(1)
