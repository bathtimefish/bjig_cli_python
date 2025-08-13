# AsyncSerialMonitor実装完了ドキュメント

**作成日**: 2025-07-13  
**目的**: AsyncSerialMonitorモジュールの実装内容と技術仕様の記録

## 1. 実装概要

### 完成したモジュール構成
BraveJIGルーター実機テスト用のイベントドリブンシリアル通信モジュールを`./scripts`に実装完了。

```
scripts/
├── __init__.py                    # パッケージ初期化・エクスポート
├── async_serial_monitor.py        # メインクラス（400行超の完全実装）
├── exceptions.py                  # 6つのカスタム例外クラス
├── README.md                      # 詳細使用方法・API仕様書
├── examples/
│   ├── basic_usage.py             # 基本使用例（シグナルハンドリング付き）
│   └── brave_jig_test.py          # BraveJIGプロトコル解析・テスト例
└── tests/
    └── test_async_serial_monitor.py # 包括的ユニットテスト
```

## 2. 技術アーキテクチャ

### 2.1 マルチスレッド設計
```
External Program
    ↕ (Event Callbacks / Command API)
AsyncSerialMonitor
    ├── Monitor Thread      # データ受信ループ
    ├── Send Thread         # コマンド送信ループ  
    ├── ThreadPoolExecutor  # コールバック実行（4ワーカー）
    └── Queue              # スレッド間通信
         ↕
    pyserial → BraveJIG Router
```

### 2.2 主要技術要素
- **pyserial**: ハードウェアシリアル通信
- **threading**: 非同期処理（Monitor/Send専用スレッド）
- **concurrent.futures.ThreadPoolExecutor**: コールバック並列実行
- **queue.Queue**: スレッドセーフなデータ受け渡し
- **logging**: デバッグ・トレース機能

## 3. 核心機能実装

### 3.1 非同期データ受信
```python
def _monitor_loop(self):
    while not self._stop_event.is_set():
        if self._serial.in_waiting > 0:
            data = self._serial.read(self._serial.in_waiting)
            # ThreadPoolExecutorでコールバック実行
            if self._data_callback:
                self._executor.submit(self._data_callback, data)
```

**特徴**:
- **継続監視**: `serial.in_waiting`による非ブロッキング受信
- **並列コールバック**: ThreadPoolExecutorで外部プログラムの処理をメインスレッドと分離
- **統計管理**: 受信バイト数の自動カウント

### 3.2 スレッドセーフ送信
```python
def send(self, data: bytes) -> bool:
    self._send_queue.put(data, timeout=1.0)

def _send_loop(self):
    while not self._stop_event.is_set():
        data = self._send_queue.get(timeout=0.1)
        bytes_written = self._serial.write(data)
        self._serial.flush()  # 即座送信保証
```

**特徴**:
- **キューイング**: Queueによる送信データのバッファリング
- **即座送信**: `flush()`による確実な送信完了
- **エラー分離**: 送信エラーは受信処理に影響しない

### 3.3 エラーハンドリング階層
```python
# 6段階のカスタム例外
AsyncSerialMonitorError          # ベース例外
├── SerialConnectionError        # 接続関連
├── SerialTimeoutError          # タイムアウト
├── SerialWriteError           # 送信エラー
├── MonitorNotStartedError     # 状態エラー
└── MonitorAlreadyStartedError # 重複開始
```

## 4. BraveJIG特化機能

### 4.1 最適化されたデフォルト設定
```python
DEFAULT_PORT = '/dev/ttyUSB0'      # → '/dev/tty.usbmodem0000000000002'に更新要
DEFAULT_BAUDRATE = 38400           # BraveJIG仕様準拠
DEFAULT_TIMEOUT = 10.0            # 長めのタイムアウト
```

### 4.2 BraveJIGプロトコル解析（examples/brave_jig_test.py）
- **アップリンク通知解析**: リトルエンディアン対応
- **ダウンリンクレスポンス解析**: Result値の意味変換
- **JIG INFOレスポンス解析**: CMD別データ構造対応
- **エラー通知解析**: エラー理由の日本語説明

```python
def _parse_uplink_notification(self, data: bytes) -> dict:
    data_length = struct.unpack('<H', data[2:4])[0]
    unix_time = struct.unpack('<L', data[4:8])[0]
    device_id = struct.unpack('<Q', data[8:16])[0]
    sensor_id = struct.unpack('<H', data[16:18])[0]
    # ... 完全なプロトコル解析
```

## 5. API設計思想

### 5.1 使いやすさ重視
```python
# 最小限のコードで動作開始
with AsyncSerialMonitor() as monitor:
    monitor.set_data_callback(lambda data: print(data.hex()))
    monitor.start_monitoring()
    monitor.send(b'\x01\x02\x03')
```

### 5.2 エラー安全性
- **コンテキストマネージャー**: 自動リソース管理
- **状態チェック**: 不正な状態遷移の防止
- **例外の詳細化**: 問題特定の容易さ

### 5.3 拡張性
- **コールバック分離**: データ/エラー/接続状態の独立処理
- **統計情報**: パフォーマンス監視機能
- **ログ機能**: デバッグサポート

## 6. 実装上の重要な設計判断

### 6.1 ThreadPoolExecutor採用理由
- **デッドロック回避**: コールバック実行をメインスレッドから分離
- **並列処理**: 複数コールバックの同時実行可能
- **リソース制限**: 最大4ワーカーでメモリ使用量制御

### 6.2 Queue-based送信アーキテクチャ
- **スレッド安全性**: 複数スレッドからの同時送信要求対応
- **順序保証**: FIFOによる送信順序の維持
- **バックプレッシャー**: キュー満杯時のタイムアウト制御

### 6.3 pyserial設定最適化
```python
write_timeout=self.timeout  # 送信タイムアウト設定
self._serial.flush()        # バッファ強制フラッシュ
```

## 7. テスト戦略

### 7.1 ユニットテスト網羅性
- **Mock使用**: 実ハードウェア不要のテスト環境
- **例外パターン**: 全エラーケースの検証
- **スレッド安全性**: 並行処理の動作確認
- **状態遷移**: ライフサイクル全体のテスト

### 7.2 統合テスト準備
```python
@unittest.skip("Requires actual hardware")
def test_real_hardware_connection(self):
    # 実機テスト用フレームワーク
```

## 8. BraveJIG実機テスト準備完了事項

### 8.1 実装完了機能
✅ **非同期データ受信**: 10秒間隔アップリンク通知の連続受信対応  
✅ **コマンド送信**: JIG INFOリクエスト・ダウンリンクリクエスト送信  
✅ **プロトコル解析**: BraveJIG全プロトコルの解析・表示  
✅ **エラーハンドリング**: 接続断・タイムアウト等の自動回復  
✅ **統計監視**: 通信量・パケット数の監視  

### 8.2 実機接続設定
```python
# 実機用設定（要確認）
PORT = '/dev/tty.usbmodem0000000000002'  # macOS USB CDC デバイス
BAUDRATE = 38400                          # BraveJIG仕様
TIMEOUT = 10.0                           # 十分な待機時間
```

## 9. 次段階への準備状況

### 9.1 実機テストの実行準備完了
- **ハードウェア非依存**: モックによる事前テスト可能
- **プロトコル対応**: BraveJIG全コマンドの送受信対応
- **デバッグ支援**: 詳細ログ・統計・エラー分類

### 9.2 今後の拡張可能性
- **複数デバイス対応**: 複数AsyncSerialMonitorの並列運用
- **設定ファイル**: 外部設定によるパラメータ調整
- **GUI統合**: tkinter等によるリアルタイム監視画面

## 10. 確認が必要な事項

### 10.1 実機環境設定
- **デバイスパス確認**: `/dev/tty.usbmodem0000000000002`の実在性
- **権限設定**: シリアルポートアクセス権限
- **BraveJIGルーター状態**: ペアリング済みモジュールの有無

### 10.2 プロトコル仕様の実機検証
- **エンディアン処理**: リトルエンディアン実装の動作確認
- **Data Length計算**: 実際のパケットサイズとの整合性
- **タイミング制御**: 10秒間隔アップリンクの実測

このAsyncSerialMonitor実装により、BraveJIGルーター実機テストの技術基盤が完成しました。外部プログラムはシリアル通信の複雑さを意識せず、イベントドリブンでBraveJIGとの通信が可能になります。