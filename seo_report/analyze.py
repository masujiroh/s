"""Classify SEO articles from the fetched data and write analysis.json.

Usage: python3 -m seo_report.analyze DATA_DIR
"""
import datetime as dt
import json
import os
import sys
from urllib.parse import urlparse

import pandas as pd

RECENT_DAYS = 90  # "recent" window for trend comparison


def load(data_dir, name):
    with open(os.path.join(data_dir, name), encoding="utf-8") as f:
        return json.load(f)


def norm_path(url):
    p = urlparse(url).path
    return p if p.endswith("/") else p + "/"


TENANT_WORDS = ["してくれない", "直してくれない", "消費者センター", "退去費用", "退去 費用", "敷金 返っ",
                "敷金 返還", "騒音 隣", "更新料 払", "入居者 相談", "借主", "部屋 水漏れ", "うるさい",
                "管理会社 対応 遅い", "管理会社 対応してくれない", "強制執行 され", "家賃 払えない",
                "代位弁済 された", "代位弁済 その後", "ブラックリスト"]
OWNER_WORDS = ["オーナー", "大家", "管理委託", "管理会社 変更", "管理会社 乗り換え", "賃貸経営", "アパート経営",
               "マンション経営", "サブリース", "利回り", "空室", "値上げ 通知", "立ち退き", "管理手数料",
               "管理費 相場", "集金代行", "自主管理", "委託", "経費", "節税", "入居審査", "募集", "滞納 対応"]


def audience(top_queries):
    """Estimate who the article attracts: share of impressions from tenant-like vs owner-like queries."""
    tenant = owner = total = 0
    for q in top_queries:
        total += q["impressions"]
        if any(w in q["query"] for w in TENANT_WORDS):
            tenant += q["impressions"]
        elif any(w in q["query"] for w in OWNER_WORDS):
            owner += q["impressions"]
    if total == 0:
        return "unknown", 0.0
    t_share = tenant / total
    if t_share >= 0.4:
        return "tenant", round(t_share, 2)
    if owner / total >= 0.3:
        return "owner", round(t_share, 2)
    return "mixed", round(t_share, 2)


def classify(row):
    """Return (bucket, reason). Rules in priority order, on the recent 90-day window."""
    pos, impr, ctr, clicks = row.position_r, row.impressions_r, row.ctr_r, row.clicks_r
    age = row.age_days
    if age < 60:
        return "new", "公開60日未満。評価が定まるまで様子見"
    if clicks >= 100:
        return "grow", f"直近90日{clicks:.0f}クリック（{pos:.1f}位）。上位3位入りとCV導線強化で伸ばす"
    if impr >= 5000:
        return "rewrite", f"表示{impr:,.0f}回に対し{clicks:.0f}クリック（{pos:.1f}位・CTR{ctr*100:.1f}%）。需要は大きく、順位・タイトル改善の効果が最も出やすい"
    if impr >= 1000:
        return "rewrite", f"表示{impr:,.0f}回・{pos:.1f}位。内容拡充と内部リンクで上位を狙う"
    if age >= 120 and clicks < 15:
        return "merge", f"公開{age // 30}か月で直近90日{clicks:.0f}クリック・表示{impr:.0f}回。類似記事への統合か方向転換を検討"
    return "keep", f"表示{impr:.0f}回・{clicks:.0f}クリック（{pos:.1f}位）。現状維持しつつ推移を見る"


def main():
    data_dir = sys.argv[1]
    meta = load(data_dir, "meta.json")
    end = dt.date.fromisoformat(meta["end"])
    recent_start = (end - dt.timedelta(days=RECENT_DAYS - 1)).isoformat()
    prev_start = (end - dt.timedelta(days=2 * RECENT_DAYS - 1)).isoformat()
    prev_end = (end - dt.timedelta(days=RECENT_DAYS)).isoformat()

    posts = pd.DataFrame(load(data_dir, "posts.json"))
    posts["path"] = posts.url.map(norm_path)
    tips = posts[posts.categories.apply(lambda c: "tips" in c)].copy()
    tip_paths = set(tips.path)

    pd_ = pd.DataFrame([{"path": norm_path(r["keys"][0]), "date": r["keys"][1],
                         **{k: r[k] for k in ("clicks", "impressions", "position")}}
                        for r in load(data_dir, "gsc_page_date.json")])

    def window(df, s, e):
        w = df[(df.date >= s) & (df.date <= e)]
        g = w.groupby("path").apply(lambda x: pd.Series({
            "clicks": x.clicks.sum(), "impressions": x.impressions.sum(),
            "position": (x.position * x.impressions).sum() / max(x.impressions.sum(), 1)}))
        g["ctr"] = g.clicks / g.impressions.replace(0, 1)
        return g

    full = window(pd_, meta["start"], meta["end"])
    recent = window(pd_, recent_start, meta["end"]).add_suffix("_r")
    prev = window(pd_, prev_start, prev_end).add_suffix("_p")

    # page x query → top queries + striking-distance keywords
    pq = pd.DataFrame([{"path": norm_path(r["keys"][0]), "query": r["keys"][1],
                        **{k: r[k] for k in ("clicks", "impressions", "position")}}
                       for r in load(data_dir, "gsc_page_query.json")])
    # URL variants (query strings, anchors) collapse onto one path → re-aggregate
    pq["pos_w"] = pq.position * pq.impressions
    pq = pq.groupby(["path", "query"], as_index=False).agg(
        clicks=("clicks", "sum"), impressions=("impressions", "sum"), pos_w=("pos_w", "sum"))
    pq["position"] = pq.pos_w / pq.impressions.replace(0, 1)
    pq = pq.drop(columns="pos_w")

    ga = pd.DataFrame(load(data_dir, "ga4_landing.json"))
    if len(ga):
        ga["path"] = ga.landingPage.map(lambda p: norm_path("https://x" + p.split("?")[0]))
        for c in ("sessions", "engagedSessions", "engagementRate", "averageSessionDuration", "keyEvents"):
            ga[c] = pd.to_numeric(ga[c], errors="coerce")
        ga = ga.groupby("path").agg(sessions=("sessions", "sum"), engaged=("engagedSessions", "sum"),
                                    duration=("averageSessionDuration", "mean"))
        ga["engagement_rate"] = ga.engaged / ga.sessions.replace(0, 1)

    df = tips.set_index("path").join(full).join(recent).join(prev).join(ga if len(ga) else None)
    df = df.fillna({c: 0 for c in df.columns if df[c].dtype != object})
    df["age_days"] = (end - pd.to_datetime(df.published).dt.date).map(lambda d: d.days)
    df["clicks_per_month"] = df.clicks / (df.age_days.clip(lower=1) / 30.4)
    df["clicks_trend"] = (df.clicks_r - df.clicks_p) / df.clicks_p.replace(0, 1)
    buckets = df.apply(classify, axis=1)
    df["bucket"] = [b for b, _ in buckets]
    df["reason"] = [r for _, r in buckets]

    articles = []
    for path, r in df.sort_values("clicks_r", ascending=False).iterrows():
        q = pq[pq.path == path].sort_values("impressions", ascending=False)
        top = q.head(8)
        striking = q[(q.position > 4) & (q.position <= 20) & (q.impressions >= 50)].head(5)
        aud, t_share = audience([{"query": x.query, "impressions": int(x.impressions)} for x in q.head(30).itertuples()])
        articles.append({
            "audience": aud, "tenant_share": t_share,
            "path": path, "url": r.url, "title": r.title, "published": r.published,
            "modified": r.modified, "age_days": int(r.age_days),
            "clicks": int(r.clicks), "impressions": int(r.impressions),
            "ctr": round(float(r.ctr), 4), "position": round(float(r.position), 1),
            "clicks_r": int(r.clicks_r), "impressions_r": int(r.impressions_r),
            "ctr_r": round(float(r.ctr_r), 4), "position_r": round(float(r.position_r), 1),
            "clicks_p": int(r.clicks_p), "position_p": round(float(r.position_p), 1),
            "clicks_trend": round(float(r.clicks_trend), 3),
            "clicks_per_month": round(float(r.clicks_per_month), 1),
            "sessions": int(r.get("sessions", 0) or 0),
            "engagement_rate": round(float(r.get("engagement_rate", 0) or 0), 3),
            "duration": round(float(r.get("duration", 0) or 0)),
            "bucket": r.bucket, "reason": r.reason,
            "top_queries": [{"query": x.query, "clicks": int(x.clicks), "impressions": int(x.impressions),
                             "position": round(float(x.position), 1)} for x in top.itertuples()],
            "striking": [{"query": x.query, "impressions": int(x.impressions),
                          "position": round(float(x.position), 1)} for x in striking.itertuples()],
        })

    # cannibalization: query where >=2 tips articles both have >=25% of impressions
    tq = pq[pq.path.isin(tip_paths)]
    cann = []
    for query, grp in tq.groupby("query"):
        tot = grp.impressions.sum()
        if tot < 100 or len(grp) < 2:
            continue
        g = grp.sort_values("impressions", ascending=False)
        if g.impressions.iloc[1] / tot >= 0.25:
            cann.append({"query": query, "impressions": int(tot),
                         "pages": [{"path": x.path, "impressions": int(x.impressions),
                                    "position": round(float(x.position), 1)} for x in g.head(3).itertuples()]})
    cann.sort(key=lambda c: -c["impressions"])

    # keyword gaps: queries with demand where the site only ranks weakly (page 2+)
    best = pq.sort_values("impressions", ascending=False).drop_duplicates("query")
    agg = pq.groupby("query").agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"),
                                  position=("position", "min"))
    gaps = agg.join(best.set_index("query").path.rename("landing"))
    gaps = gaps[(gaps.impressions >= 150) & (gaps.position > 12)].sort_values("impressions", ascending=False)
    noise = gaps.index.str.contains(r"lpp|エルピーピー|プロパティ|フェア|代々木|\d{2,}", case=False, regex=True)
    new_topics = gaps[~noise].head(40)

    # monthly site totals
    gd = pd.DataFrame([{"date": r["keys"][0], **{k: r[k] for k in ("clicks", "impressions")}}
                       for r in load(data_dir, "gsc_date.json")])
    gd["month"] = gd.date.str[:7]
    monthly = gd.groupby("month").agg(clicks=("clicks", "sum"), impressions=("impressions", "sum")).reset_index()
    published = tips.groupby(tips.published.str[:7]).size()
    monthly["articles_published"] = monthly.month.map(published).fillna(0).astype(int)

    # monthly clicks per article (for sparklines)
    pm = pd_[pd_.path.isin(tip_paths)].copy()
    pm["month"] = pm.date.str[:7]
    per_month = pm.groupby(["path", "month"]).clicks.sum().unstack(fill_value=0)
    months = list(monthly.month)
    for a in articles:
        a["monthly_clicks"] = [int(per_month.loc[a["path"], m]) if a["path"] in per_month.index and m in per_month.columns else 0 for m in months]

    summary = {k: int((df.bucket == k).sum()) for k in ("grow", "rewrite", "keep", "merge", "new")}
    out = {
        "meta": {**meta, "recent_start": recent_start, "prev_start": prev_start, "prev_end": prev_end,
                 "months": months, "article_count": len(df)},
        "summary": summary,
        "monthly": monthly.to_dict(orient="records"),
        "articles": articles,
        "cannibalization": cann[:15],
        "new_topics": [{"query": q, "impressions": int(r.impressions), "clicks": int(r.clicks),
                        "position": round(float(r.position), 1), "landing": r.landing}
                       for q, r in new_topics.iterrows()],
    }
    with open(os.path.join(data_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("summary:", summary)
    print(df[["title", "clicks_r", "impressions_r", "position_r", "bucket"]]
          .sort_values("clicks_r", ascending=False).to_string(max_colwidth=38))


if __name__ == "__main__":
    main()
