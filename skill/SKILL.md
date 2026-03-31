---
name: wls
description: "Use when the user wants to browse directories, view images/videos/files visually, check directory structure, or says 'wlsで見せて', 'wlsで開いて', 'ファイルを見たい', 'ディレクトリ構造を見たい'. Also triggers when user generates images/videos and wants to preview them, or needs a visual file browser alongside their terminal work."
user-invocable: true
version: "1.0.0"
---

# wls — Web-based File Browser

wls はブラウザで動く Finder ライクなファイルブラウザ。cmux のブラウザペインと組み合わせて、Claude Code の隣でファイル閲覧・画像/動画プレビューができる。

## セットアップ確認

wls を使う前に、まず以下を確認:

1. **wls の場所を特定** — `WLS_DIR` を探す:
   ```bash
   # skill の symlink 元からプロジェクトルートを推定
   WLS_DIR="$(dirname "$(readlink -f ~/.claude/skills/wls/SKILL.md)")"
   WLS_DIR="$(dirname "$WLS_DIR")"  # skill/ の親 = プロジェクトルート
   ```

2. **サーバーが起動しているか確認**:
   ```bash
   curl -s http://localhost:8234/api/ls?dir=~ > /dev/null 2>&1
   ```

3. **起動していなければ起動** (バックグラウンド):
   ```bash
   "$WLS_DIR/start.sh" &
   ```

## 使い方

### ディレクトリを見せる

cmux のブラウザペインで指定ディレクトリを開く:

```bash
# URL にパスを直接指定できる
cmux browser open "http://localhost:8234/Users/suzukishin/some/directory"
```

既にブラウザペインが開いている場合は、そのペインで navigate する:

```bash
cmux browser SURFACE_REF navigate "http://localhost:8234/path/to/dir"
```

### 画像・動画を見せる

ファイルを直接 URL で開ける:

```bash
# 画像をブラウザで直接表示
cmux browser open "http://localhost:8234/path/to/image.png"
```

ただし、wls の UI 上でプレビューペイン付きで見せたい場合は、**親ディレクトリを開く**のがよい。ユーザーがファイルをクリックすればプレビューペインに表示される。

```bash
# 画像があるディレクトリを開く → ユーザーがクリックでプレビュー
cmux browser open "http://localhost:8234/path/to/directory"
```

### ディレクトリ構造を確認する

wls にはツリー展開機能（▶ トグル）があるので、ディレクトリを開けばユーザーが自分で階層を掘っていける。

## 典型的なワークフロー

1. ユーザー: 「画像を生成して、wls で見せて」
2. 画像を生成する
3. wls サーバーが起動しているか確認、なければ起動
4. cmux でブラウザペインを開き、画像のあるディレクトリを表示

```bash
# 例: output/ に画像を生成した後
cmux browser open "http://localhost:8234/Users/suzukishin/project/output"
```

## ポート

デフォルトポートは `8234`。変更している場合はユーザーに確認すること。

## 注意点

- wls は macOS 専用（Finder API を使用）
- サーバーは localhost のみにバインドされるため外部からのアクセスはない
- cmux 環境外でも、普通のブラウザで `http://localhost:8234` を開けば使える
