"""Minimal Google API client for Search Console and GA4 (service account auth).

Reads credentials from GOOGLE_APPLICATION_CREDENTIALS_B64 (base64 of the
service-account JSON). Only depends on pyjwt, cryptography and requests.
"""
import base64
import json
import os
import time

import jwt
import requests

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]

_token_cache = {"access_token": None, "expires_at": 0}


def load_credentials():
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_B64")
    if not raw:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS_B64 is not set")
    return json.loads(base64.b64decode(raw))


def get_access_token():
    now = int(time.time())
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    creds = load_credentials()
    assertion = jwt.encode(
        {
            "iss": creds["client_email"],
            "scope": " ".join(SCOPES),
            "aud": TOKEN_URI,
            "iat": now,
            "exp": now + 3600,
        },
        creds["private_key"],
        algorithm="RS256",
    )
    resp = requests.post(
        TOKEN_URI,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    _token_cache["access_token"] = body["access_token"]
    _token_cache["expires_at"] = now + body.get("expires_in", 3600)
    return body["access_token"]


def _headers():
    return {"Authorization": f"Bearer {get_access_token()}"}


# ---------- Search Console ----------

def gsc_site_url():
    return os.environ["GSC_SITE_URL"]


def gsc_query(start_date, end_date, dimensions, row_limit=25000,
              dimension_filter_groups=None, search_type="web"):
    """Fetch all rows of a Search Analytics query, paging through startRow."""
    url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
           f"{requests.utils.quote(gsc_site_url(), safe='')}/searchAnalytics/query")
    rows, start_row = [], 0
    while True:
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "startRow": start_row,
            "type": search_type,
        }
        if dimension_filter_groups:
            body["dimensionFilterGroups"] = dimension_filter_groups
        resp = requests.post(url, headers=_headers(), json=body, timeout=120)
        resp.raise_for_status()
        batch = resp.json().get("rows", [])
        rows.extend(batch)
        if len(batch) < row_limit:
            return rows
        start_row += row_limit


# ---------- GA4 ----------

def ga4_property_id():
    return os.environ["GA4_PROPERTY_ID"]


def ga4_run_report(start_date, end_date, dimensions, metrics,
                   dimension_filter=None, limit=100000):
    """Run a GA4 Data API report and return all rows as list of dicts."""
    url = (f"https://analyticsdata.googleapis.com/v1beta/properties/"
           f"{ga4_property_id()}:runReport")
    out, offset = [], 0
    while True:
        body = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "limit": limit,
            "offset": offset,
        }
        if dimension_filter:
            body["dimensionFilter"] = dimension_filter
        resp = requests.post(url, headers=_headers(), json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        for r in data.get("rows", []):
            row = {d: v["value"] for d, v in zip(dimensions, r["dimensionValues"])}
            row.update({m: v["value"] for m, v in zip(metrics, r["metricValues"])})
            out.append(row)
        total = int(data.get("rowCount", 0))
        offset += limit
        if offset >= total:
            return out
