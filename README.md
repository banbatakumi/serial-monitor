# Serial Monitor

Arduino / STM32 などのマイコンからのシリアルデータをリアルタイムで表示・グラフ化するデスクトップアプリです。

![GitHub Release](https://img.shields.io/github/v/release/banbatakumi/serial-monitor)
![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-black?logo=apple)
![Windows](https://img.shields.io/badge/Windows-x64-0078D4?logo=windows)

---

## 機能

- **リアルタイムグラフ** — 複数チャンネルを色分けして同時表示
- **4種類の受信モード** — プレーンテキスト / ラベル付きテキスト / CSV 数値 / バイナリパケット
- **統計解析** — 平均・標準偏差・最小/最大をチャンネルごとに集計
- **CSV エクスポート** — 受信データを CSV ファイルに書き出し
- **生データモード** — バッファリングなしで受信データをそのまま表示
- **ボーレート対応** — 9600 〜 921600 bps（250000 bps を含む）

---

## ダウンロード

[Releases ページ](https://github.com/banbatakumi/serial-monitor/releases/latest) から最新版をダウンロードしてください。

| プラットフォーム | ファイル |
|---|---|
| macOS (Apple Silicon) | `SerialMonitor-1.1.2-macOS.dmg` |
| Windows (x64) | `SerialMonitor-1.1.2-Windows.exe` |

### インストール方法

**macOS**: DMG を開いて `SerialMonitor.app` をアプリケーションフォルダにドラッグします。

**Windows**: インストーラー (`.exe`) を実行してウィザードに従います。

---

## 使い方

1. アプリを起動してポートとボーレートを選択
2. **接続** ボタンをクリック
3. **プロトコル設定** でデータ形式を選択
4. **グラフ** タブでリアルタイム波形を確認

---

## プロトコルモード

### プレーンテキスト

`printf` / `Serial.println` の出力をそのままコンソールに表示します。設定不要です。

```cpp
// Arduino の例
Serial.println("Hello, World!");
Serial.println(analogRead(A0));
```

---

### ラベル付きテキスト

`ラベル: 値` の形式を自動認識してグラフ表示します。設定不要です。

```c
// STM32 の例
printf("Theta: %.2f deg, Speed: %.2f rpm, Volt: %.2f V\n",
    theta, speed, volt);
```

```cpp
// Arduino の例 (ラベルと値の間に文字が混在していても OK)
Serial.print("Count1: "); Serial.print(cnt);
Serial.print(", Count2: "); Serial.println(cnt * 2);
```

チャンネル名はラベルから自動設定されます。

---

### CSV 数値データ

カンマ区切りの数値を受信してリアルタイムグラフに表示します。

```cpp
// Arduino の例 — 3チャンネル送信
float ax = /* 加速度X */;
float ay = /* 加速度Y */;
float az = /* 加速度Z */;
Serial.print(ax); Serial.print(",");
Serial.print(ay); Serial.print(",");
Serial.println(az);
```

**プロトコル設定**でチャンネル名を `ax, ay, az` のように登録すると、グラフの凡例に表示されます。

ヘッダ・フッタで囲む形式にも対応しています:

```cpp
// ヘッダ「S」フッタ「\n」の例
Serial.print("S");
Serial.print(value1); Serial.print(",");
Serial.println(value2);
```

---

### バイナリパケット

固定長のバイナリパケットを受信してデコードします。ノイズに強く、高速なデータ転送に向いています。

**パケット構造**: `[ヘッダ][ペイロード][フッタ]`

```cpp
// Arduino の例 — int16 × 3チャンネル (ヘッダ: 0xAA, フッタ: 0xFF)
struct Packet {
    uint8_t  header = 0xAA;
    int16_t  ax;
    int16_t  ay;
    int16_t  az;
    uint8_t  footer = 0xFF;
} __attribute__((packed));

Packet pkt;
pkt.ax = (int16_t)(accelX * 1000);
pkt.ay = (int16_t)(accelY * 1000);
pkt.az = (int16_t)(accelZ * 1000);
Serial.write((uint8_t*)&pkt, sizeof(pkt));
```

プロトコル設定でフィールドごとに型・スケール・エンディアンを指定できます。

---

## ソースからビルド

Python 3.12 と以下のパッケージが必要です。

```bash
pip install PyQt6 pyserial pyqtgraph numpy
python main.py
```

### macOS 向けアプリビルド (py2app)

```bash
pip install py2app
arch -arm64 python setup.py py2app
```

### Windows 向けインストーラービルド (PyInstaller + Inno Setup)

```bat
pip install pyinstaller
pyinstaller build_windows.spec
# Inno Setup がインストールされている場合
ISCC.exe /DMyAppVersion=1.1.2 installer.iss
```

GitHub Actions により、タグ push 時に両プラットフォームのビルドが自動実行されます。

---

## ライセンス

MIT License
