"""Fetch Search Console / GA4 / WordPress data for the SEO research report.

Usage: python3 -m seo_report.fetch_data OUT_DIR [START_DATE] [END_DATE]
Writes JSON files into OUT_DIR. Dates default to the last 16 months
(Search Console keeps 16 months) ending 3 days ago (data lag).
"""
import datetime as dt
import json
import os
import sys

import requests

from seo_report import google_api as g

SITE = "https://lpppm.co.jp"


def wp_posts():
    out, page = [], 1
    while True:
        r = requests.get(
            f"{SITE}/wp-json/wp/v2/posts",
            params={"per_page": 100, "page": page,
                    "_fields": "id,link,title,date,modified,categories"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if page >= int(r.headers.get("x-wp-totalpages", 1)):
            break
        page += 1
    cats = requests.get(f"{SITE}/wp-json/wp/v2/categories",
                        params={"per_page": 100, "_fields": "id,name,slug"},
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()
    cat_map = {c["id"]: c["slug"] for c in cats}
    return [{
        "url": p["link"],
        "title": p["title"]["rendered"],
        "published": p["date"][:10],
        "modified": p["modified"][:10],
        "categories": [cat_map.get(c, str(c)) for c in p["categories"]],
    } for p in out]


def organic_filter():
    return {"filter": {"fieldName": "sessionDefaultChannelGroup",
                       "stringFilter": {"value": "Organic Search"}}}


def main():
    out_dir = sys.argv[1]
    end = sys.argv[3] if len(sys.argv) > 3 else (dt.date.today() - dt.timedelta(days=3)).isoformat()
    start = sys.argv[2] if len(sys.argv) > 2 else (
        dt.date.fromisoformat(end) - dt.timedelta(days=16 * 30)).isoformat()
    os.makedirs(out_dir, exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        print(f"  {name}: {len(obj) if hasattr(obj, '__len__') else ''}")

    print(f"period: {start} .. {end}")
    dump("meta.json", {"start": start, "end": end, "site": SITE,
                       "fetched_at": dt.datetime.now().isoformat(timespec="seconds")})

    print("WordPress posts")
    dump("posts.json", wp_posts())

    print("Search Console")
    dump("gsc_page.json", g.gsc_query(start, end, ["page"]))
    dump("gsc_page_date.json", g.gsc_query(start, end, ["page", "date"]))
    dump("gsc_page_query.json", g.gsc_query(start, end, ["page", "query"]))
    dump("gsc_query.json", g.gsc_query(start, end, ["query"]))
    dump("gsc_date.json", g.gsc_query(start, end, ["date"]))

    print("GA4 (organic search)")
    dump("ga4_landing.json", g.ga4_run_report(
        start, end, ["landingPage"],
        ["sessions", "engagedSessions", "engagementRate",
         "averageSessionDuration", "keyEvents"],
        dimension_filter=organic_filter()))
    dump("ga4_landing_month.json", g.ga4_run_report(
        start, end, ["landingPage", "yearMonth"], ["sessions"],
        dimension_filter=organic_filter()))
    dump("ga4_channel_month.json", g.ga4_run_report(
        start, end, ["sessionDefaultChannelGroup", "yearMonth"],
        ["sessions", "keyEvents"]))


if __name__ == "__main__":
    main()
