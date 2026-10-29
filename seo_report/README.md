# seo_report

lpppm.co.jp のSEO記事リサーチ用ツール。Search Console / GA4 のデータを取得し、記事を分類してHTMLレポートを生成する。

## 必要な環境変数
- `GOOGLE_APPLICATION_CREDENTIALS_B64` … サービスアカウントJSONをbase64にしたもの
- `GSC_SITE_URL` … 例 `https://lpppm.co.jp/`
- `GA4_PROPERTY_ID` … 例 `514468685`

## 使い方
```bash
python3 -m seo_report.fetch_data   DATA_DIR            # データ取得（既定: 直近16か月）
python3 -m seo_report.analyze      DATA_DIR            # 分類 → analysis.json
python3 -m seo_report.build_report DATA_DIR out.html   # HTMLレポート生成
```

## ファイル
- `google_api.py` … サービスアカウント認証と Search Console / GA4 Data API の薄いクライアント
- `fetch_data.py` … WordPress REST・Search Console・GA4 からJSONを保存
- `analyze.py` … 記事の5分類、カニバリゼーション、キーワードギャップの算出
- `build_report.py` / `report_template.html` … レポート生成
- `tracking/ga4-contact-tracking.html` … 問い合わせ計測用のサイト設置コード
