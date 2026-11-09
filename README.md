# クラウドソーシング調査ツール

クラウドワークス／ココナラの公開情報を集めて、**案件・相場・競合・トレンド**をブラウザで分析する Web アプリです。
手動で集めた CSV（ランサーズなど他サイトのデータも可）の取り込みにも対応しています。

## できること

| タブ | 内容 |
|---|---|
| 収集 | キーワードでクラウドワークス（案件）／ココナラ（出品サービス）を検索して保存。ウォッチリストに登録して一括収集 |
| 案件 | 案件一覧（報酬形式・予算・契約数で絞り込み/並べ替え）、よく発注しているクライアント |
| 相場 | 出品価格・案件予算の分布（中央値・四分位・ヒストグラム） |
| 競合分析 | 出品者ランキング（出品数・平均価格・レビュー数・評価・期間内のレビュー増・推定売上）、サービス一覧 |
| トレンド | 収集のたびに記録される「検索結果件数」「価格中央値」の推移グラフ |
| 取込/出力 | CSV 取り込み（日本語ヘッダー可・UTF-8/Shift_JIS）、CSV 出力（Excel 対応） |

## セットアップと起動

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000 を開く
```

データは `data/research.db`（SQLite）に保存されます。

## コマンドライン / 定期実行

```bash
python -m app.cli collect crowdworks "Python" --pages 2
python -m app.cli collect coconala "ロゴ作成"
python -m app.cli watch add coconala "ロゴ作成"
python -m app.cli watch list
python -m app.cli watch run                       # ウォッチリストを一括収集
python -m app.cli import service mydata.csv --platform lancers --keyword 動画編集
```

トレンドやレビュー増加数（≒販売数の目安）を見るには、定期的に収集してください。cron の例（毎朝9時）:

```
0 9 * * * cd /path/to/Test && python -m app.cli watch run >> data/cron.log 2>&1
```

## 設定（環境変数）

| 変数 | 既定値 | 説明 |
|---|---|---|
| `FRT_DB_PATH` | `data/research.db` | 保存先 |
| `FRT_REQUEST_INTERVAL` | `5` | 同一サイトへのリクエスト間隔（秒） |
| `FRT_MAX_PAGES` | `5` | 1回の収集で取得する最大ページ数 |
| `FRT_USER_AGENT` | `FreelanceResearchTool/0.1 ...` | 送信する User-Agent |

## 利用上の注意

- 両サイトとも公式の公開 API はありません。本ツールはログイン不要の**公開検索ページ**だけを、`robots.txt` に従い、数秒間隔で少量取得します。
- 自動取得は各サイトの**利用規約**で制限されている場合があります。使う前に必ず規約を確認し、個人の調査目的・低頻度で利用してください。不安な場合は CSV 取り込み（手動収集）だけでも使えます。
- 取得したデータの再配布や、個人を特定する目的での利用はしないでください。
- サイトの画面構造が変わると取得できなくなります（`app/collectors/` のパーサーを修正してください）。
- 「推定売上」「レビュー増」はあくまで目安です（ココナラはレビューを書かない購入者もいます）。

## 構成

```
app/
  main.py            Web API（FastAPI）と画面配信
  cli.py             コマンドライン
  service.py         収集処理（Web/CLI 共通）
  collectors/        サイト別の取得・解析（base.py: robots.txt 遵守とレート制限）
  db.py              SQLite スキーマと保存
  analysis.py        相場・競合・トレンドの集計
  importer.py        CSV 取り込み・出力
  static/            画面（HTML/JS/CSS, Chart.js）
tests/               pytest（ネットワーク不要のサンプル HTML で検証）
```

テスト実行: `python -m pytest`
