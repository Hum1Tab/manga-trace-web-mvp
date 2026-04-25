# MangaTrace Web MVP

[English](README.md) | 日本語

MangaTrace Web MVP は、FastAPI + SQLite + Pillow で作った最小構成のプロトタイプです。ユーザーごと・閲覧ごとに異なる、低視認のフォレンジックウォーターマーク入り漫画画像を配信します。

このMVPの目的は、**画像を絶対に保存できないようにすることではありません**。ブラウザに画像が表示された時点で、DevTools、スクリーンショット、画面録画、スマホ撮影などでコピーされる可能性があります。目的は、ブラウザへ返す画像を最初から短い追跡用 payload 付きの透かし入り画像にして、後からDB上の閲覧記録に照合できるようにすることです。

## このMVPでできること

- デモユーザーでログインする。
- デモ漫画ページ一覧を表示する。
- ページを開くたびに `view_id` を作成する。
- その閲覧に対して `payload_id`、`auth_tag`、`seed` を生成する。
- SQLite に対応関係を保存する。
- 公開されていないベース画像から、透かし入り画像を生成する。
- ブラウザには `/api/views/{view_id}/image` だけを返す。
- ローカル検証用の抽出CLIを含む。

## このMVPでまだやらないこと

- スクリーンショットやDevTools保存を完全に防ぐこと。
- 本番用アカウント管理。
- 課金、DRM、CDN、S3/R2、Redis、管理画面。
- 本格的なブラインド抽出、ECC、本番レベルの埋め込みマスク選択。
- 法務判断や本番運用。現状のまま本番投入するものではありません。

## リポジトリ構成

```text
manga_trace_web_mvp/
  backend/app/
    main.py        FastAPIアプリとAPIルート
    db.py          SQLiteスキーマと接続ヘルパー
    watermark.py   透かし埋め込み/抽出ロジック
    security.py    パスワードハッシュとHMACヘルパー
    config.py      パスと環境変数設定
  frontend/
    login.html
    viewer.html
  scripts/
    init_demo.py   デモDBとデモページを作成
  tools/
    extract_saved_image.py
  docs/
    WEB_MVP_NOTES.md
    PUBLIC_RELEASE_CHECKLIST.md
  data/
    .gitkeep       実行時DB/画像はローカル生成され、gitでは無視されます
```

## セットアップ

```bash
git clone https://github.com/YOUR_NAME/manga-trace-web-mvp.git
cd manga-trace-web-mvp
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

依存関係を入れて、デモデータを初期化します。

```bash
pip install -r requirements.txt
python scripts/init_demo.py
```

サーバーを起動します。

```bash
uvicorn backend.app.main:app --reload
```

ブラウザで開きます。

```text
http://127.0.0.1:8000/
```

デモログイン:

```text
demo@example.com
password
```

## 環境変数

必要なら `.env.example` を `.env` にコピーします。

```bash
cp .env.example .env
```

ローカル以外で使う前に、必ず本物の長いシークレットを設定してください。

```text
MANGA_TRACE_SECRET=replace-with-a-long-random-secret
```

環境変数が未設定の場合、開発用シークレットにフォールバックします。これはローカルテストでのみ許容されます。

## Web上の流れ

```text
ユーザーがログイン
  ↓
フロントエンドが page_id を付けて POST /api/views を呼ぶ
  ↓
サーバーが view_id, payload_id, auth_tag, seed を作る
  ↓
サーバーが対応関係を SQLite に保存
  ↓
フロントエンドが /api/views/{view_id}/image を表示
  ↓
サーバーが内部ベース画像を読み、透かし入りWebPを返す
```

原本・ベース画像は静的ファイルとして公開しません。ブラウザ上の画像を保存されても、保存されるのは透かし入り画像です。

## API

```http
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
GET  /api/pages
POST /api/views
GET  /api/views/{view_id}/image
GET  /api/views/{view_id}  # MVP用デバッグエンドポイント。本番では削除
```

## 保存した画像をローカルで抽出する

現時点のMVP抽出器は non-blind 方式です。元のベース画像と view seed が必要です。seed はローカル検証のためにデバッグエンドポイントだけで露出しています。

例:

```bash
python tools/extract_saved_image.py data/pages/page_001/base.png saved_watermarked.webp --seed SEED_FROM_DEBUG_JSON
```

## GitHub公開前チェックリスト

公開前に確認してください。

- `.env` をgitに入れない。
- `data/app.db` をgitに入れない。
- 実際の漫画ページをコミットしない。
- 実ユーザーデータをコミットしない。
- 抽出調査ケースや調査結果をコミットしない。
- GitHubリポジトリ作成後、README内の `YOUR_NAME` を自分のユーザー名に置き換える。

公開手順:

```bash
git init
git add .
git commit -m "Initial MangaTrace Web MVP"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/manga-trace-web-mvp.git
git push -u origin main
```

## 本番化前の注意

実運用する前に、最低限これを行ってください。

- ユーザー向けAPIから `debug_payload_id`、`debug_auth_tag`、seed露出を削除する。
- 抽出ツールを管理者専用にする。
- HTTPSを使う。
- ローカルSQLiteではなくPostgreSQLなどを使う。
- レート制限と監査ログを追加する。
- ベース画像は非公開オブジェクトストレージに置く。
- ユーザー固有画像には `Cache-Control: no-store, private` を付ける。
- 無断転載対策として追跡用情報が埋め込まれる可能性を、利用規約・プライバシー文面で明示する。
- 抽出結果は断定ではなく、信頼度付きの候補として扱う。

## ライセンス

MIT License。詳しくは [LICENSE](LICENSE) を見てください。
