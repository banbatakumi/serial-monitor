# Serial Monitor — Claude 開発引き継ぎドキュメント

> このファイルは次のセッションで Claude がスムーズに開発を再開できるよう作成した。
> 最終更新: v1.1.5 (2026-05-15)

---

## プロジェクト概要

Arduino / STM32 などのマイコンからのシリアル通信を受信・表示・解析する macOS デスクトップアプリ。

- **言語**: Python 3.12 (arm64)
- **GUI**: PyQt6 + pyqtgraph
- **シリアル**: pyserial
- **パッケージング**: py2app（PyInstaller ではない — 後述の理由を参照）
- **GitHub**: https://github.com/banbatakumi/serial-monitor

---

## ディレクトリ構成

```
serial-monitor/
├── main.py                  # エントリポイント (QApplication + MainWindow)
├── setup.py                 # py2app 設定 (バージョン管理もここ)
├── requirements.txt         # PyQt6, pyserial, pyqtgraph, numpy
├── icon.icns                # アプリアイコン (Downloads/Icon.png から変換済み)
├── rthook_bundle_init.py    # 過去の PyInstaller 用フック (現在は未使用)
├── serial_monitor.spec      # 過去の PyInstaller spec (現在は未使用)
├── build_app.sh             # 古いビルドスクリプト (現在は未使用)
└── src/
    ├── serial_worker.py     # QThread でシリアル受信
    ├── protocol_parser.py   # 3モードのプロトコル解析
    ├── data_store.py        # 時系列データ蓄積 + 統計 + CSV エクスポート
    └── ui/
        ├── main_window.py   # メインウィンドウ (ツールバー・タブ管理)
        ├── console_widget.py    # テキストコンソール表示
        ├── graph_widget.py      # リアルタイムグラフ (pyqtgraph)
        ├── analysis_widget.py   # 解析タブ (統計テーブル + グラフ + CSV出力)
        └── settings_dialog.py   # プロトコル設定ダイアログ
```

---

## アーキテクチャ / データフロー

```
シリアルポート
    │ bytes
    ▼
SerialWorker (QThread)
    │ data_received(bytes) シグナル
    ▼
ProtocolParser.feed(bytes)
    │ text_line_received(str)   ─────────────────────────────────────► ConsoleWidget
    │ structured_received(float, list[float])
    ▼
MainWindow._on_structured()
    ├─ DataStore.add_sample()          ← 常に即時保存 (データロスなし)
    └─ [生データモード OFF] _pending_samples に追加
       [生データモード ON]  RealtimeGraphWidget.add_sample() を即時呼び出し

QTimer (_display_timer, デフォルト 50ms)
    └─ _flush_pending() → ConsoleWidget / RealtimeGraphWidget を更新
```

---

## プロトコルモード (ProtocolConfig.mode)

| mode | 説明 | 設定 |
|------|------|------|
| `"plain"` | printf / Serial.println をそのまま表示 | なし |
| `"structured"` | CSV 数値データ (カンマ区切り) | separator, channels, header(任意), footer(任意) |
| `"binary"` | ヘッダ+固定長ペイロード+フッタ | header(HEX), footer(HEX), binary_fields |

### BinaryField

```python
@dataclass
class BinaryField:
    name: str = ""
    ftype: str = "int16"   # uint8/int8/uint16/int16/uint32/int32/float32
    scale: float = 1.0     # actual_value = raw / scale
    endian: str = "big"    # "big" or "little"
    graph: bool = True     # グラフに表示するか
```

### バイナリパース処理 (protocol_parser.py)

1. バッファからヘッダバイト列を検索
2. `payload_size = sum(FIELD_TYPES[f.ftype][1] for f in binary_fields)` バイト読み取り
3. フッタ位置を検証 → 不一致なら1バイトスキップしてリトライ
4. `struct.unpack_from(endian_char + fmt, payload, offset)` でデコード
5. `text_line_received` と `structured_received` を両方 emit

---

## 主要クラス・シグナル一覧

### SerialWorker (QThread)
- シグナル: `data_received(bytes)`, `error_occurred(str)`, `disconnected()`
- メソッド: `connect(port, baud)→bool`, `disconnect()`, `send(bytes)`
- `run()`: `in_waiting > 0` のとき `read()` → emit、なければ `msleep(5)`

### ProtocolParser (QObject)
- シグナル: `text_line_received(str)`, `structured_received(float, list)`
- メソッド: `feed(bytes)`, `set_config(ProtocolConfig)`, `reset()`

### DataStore
- `add_sample(timestamp, values, channel_names)` — 常にメインスレッドから呼ぶ
- `all_stats()` → `dict[str, {count, mean, std, min, max}]`
- `export_csv(path)` — 全チャンネルを time_s, ch1, ch2... で書き出し
- 最大 100,000 サンプル/チャンネル (deque で自動破棄)

### RealtimeGraphWidget
- チャンネルカラー: `COLORS` リスト (8色、循環)
- チェックボックスに `■ チャンネル名` を各色で表示
- `set_channels(names)` → `add_sample(ts, values, names)`
- 表示サンプル数スピナー + 一時停止ボタン + クリアボタン

### MainWindow
- ツールバー行1: ポート, ボーレート, 接続, プロトコル設定, 接続状態
- ツールバー行2: 更新周期スピナー (10–5000 ms), **生データ**チェックボックス
- 生データ ON: `_on_text_line`/`_on_structured` から直接 UI 更新 (バッファ無視)
- 生データ OFF: `_pending_*` に蓄積 → `_flush_pending()` で定期更新

---

## 開発環境

```
/Users/banbatakumi/GitHub/serial-monitor/
├── .venv/          ← 通常開発用 (PyQt6, pyserial, pyqtgraph, numpy, PyInstaller)
└── .venv_py2app/   ← ビルド専用 (py2app のみ、PyInstaller なし)
```

**必ず `arch -arm64` を付けて実行する** (Rosetta 経由だと arm64 Qt ライブラリと衝突)

```bash
# 開発実行
arch -arm64 .venv/bin/python main.py

# インポートテスト
arch -arm64 .venv/bin/python -c "from src.ui.main_window import MainWindow; print('OK')"
```

---

## ビルド手順 (Windows — PyInstaller + Inno Setup)

Windows ビルドは GitHub Actions が自動で行う。ローカルでテストしたい場合は Windows 環境で:

```bat
pip install PyQt6 pyserial pyqtgraph numpy pyinstaller
pyinstaller build_windows.spec
# Inno Setup がインストールされていれば:
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.0.7 installer.iss
```

- **`build_windows.spec`**: PyInstaller 設定 (Qt6 プラグイン・pyqtgraph を collect_all で収録)
- **`installer.iss`**: Inno Setup スクリプト → `dist/SerialMonitor-X.X.X-Windows.exe` を生成
- **アイコン**: CI が `icon.icns` → `icon.ico` に自動変換 (icnsutils + Pillow)
- **注意**: `serial.tools.list_ports_posix` は除外、`list_ports_windows` を使用

---

## ビルド手順 (py2app)

```bash
# 1. バージョンを setup.py の CFBundleVersion / CFBundleShortVersionString で上げる

# 2. ビルド (ビルド専用 venv を使う)
rm -rf build dist
arch -arm64 .venv_py2app/bin/python setup.py py2app

# 3. DMG 作成
hdiutil create -volname "SerialMonitor" \
  -srcfolder dist/SerialMonitor.app \
  -ov -format UDZO \
  dist/SerialMonitor-X.X.X-macOS.dmg

# 4. コミット → タグ → プッシュ → リリース
git add -A && git commit -m "chore: bump version to X.X.X"
git push
git tag vX.X.X && git push origin vX.X.X
arch -arm64 gh release create vX.X.X dist/SerialMonitor-X.X.X-macOS.dmg \
  --title "vX.X.X - ..." --notes "..."
```

---

## なぜ PyInstaller ではなく py2app か (重要)

macOS 26 (Sequoia 以降) の **PAC (Pointer Authentication Code)** 検証により、PyInstaller でビルドしたアプリが即クラッシュする。

**原因の連鎖:**
1. PyInstaller bootloader は NSApplicationMain を呼ばずに Python を起動
2. `QtCore.abi3.so` の static initializer (`_GLOBAL__sub_I_qdarwinpermissionplugin_location.mm`) が `CFBundleGetMainBundle()` を呼ぶ
3. CFBundle が未初期化 → NULL を返す
4. `__CFCheckCFInfoPACSignature(NULL + 8)` → PAC 検証失敗 → **SIGILL でクラッシュ**

**py2app の解決:**
- Universal Binary スタブが先に `NSApplicationMain` を呼び CFBundle を初期化
- その後 Python が起動するので QtCore の static initializer が安全に実行される

**→ PyInstaller ベースの解決策は現時点では存在しない。py2app 固定。**

---

## GitHub Actions による自動ビルド / リリース

`.github/workflows/build.yml` が以下を自動化:

| ジョブ | ランナー | 処理 |
|--------|---------|------|
| `prepare` | ubuntu-latest | バージョン抽出 + `icon.icns` → `icon.ico` 変換 |
| `build-macos` | macos-14 (arm64) | py2app ビルド + DMG 作成 |
| `build-windows` | windows-latest | PyInstaller + Inno Setup インストーラー作成 |
| `release` | ubuntu-latest | **タグ push 時のみ** GitHub Release (draft) を作成 |

**リリースの流れ:**
1. `setup.py` の `CFBundleVersion` を上げる
2. `git tag vX.X.X && git push origin vX.X.X` でタグを push
3. Actions が自動ビルド → Draft Release を作成
4. GitHub の Release ページでノートを編集して Publish

---

## 配布について

- `.dmg`: macOS Apple Silicon 向け (Intel 非対応)
- `.exe` インストーラー: Windows x64 向け (PyInstaller + Inno Setup)
- どちらも GitHub Releases から配布

---

## 現在のバージョン履歴

| バージョン | 主な変更 |
|-----------|---------|
| v1.0.0 | 初回リリース (Rosetta クラッシュあり) |
| v1.0.1–1.0.2 | PyInstaller + rthook 試行 → CFBundle クラッシュ継続 |
| v1.0.3 | py2app に移行 → 起動成功 |
| v1.0.4 | アプリアイコン追加、250000 baud 追加、更新周期スピナー追加 |
| v1.0.6 | 設定ダイアログ UI 刷新 (プレーンテキスト設定を整理、エンディアン説明追加) |
| v1.0.7 | ツールバー2行化 (幅~650px対応)、チャンネル色 ■ 表示、生データモード追加 |
| v1.1.0 | Windows 対応 (PyInstaller + Inno Setup)、GitHub Actions 自動ビルド |
| v1.1.1 | グラフ: チャンネルごとのスケール倍率、X軸を0以上に制限 |
| v1.1.2 | ラベル付きテキストモード追加 ("Key: value" を自動解析) |
| v1.1.3 | グラフ: 時間ウィンドウ指定、追従ボタンをわかりやすく改善 |

---

## 今後実装できそうな機能

- シリアルポートの自動接続 / 再接続
- ログの自動保存 (タイムスタンプ付きファイル名)
- グラフのズーム・パン操作の改善
- 複数チャンネルのスケール個別設定
- 受信バイト数・レートの表示
- Intel Mac (x86_64) / Universal Binary 対応
| v1.1.4 | X軸を相対時間表示、テキストモード統合、自動再接続、USB優先選択 |
| v1.1.5 | 追従ボタンのトグルバグ修正、解析タイムスタンプ修正 |
