# BraveJIG CLI Testing Framework

包括的なテスト環境とフレームワークドキュメント

## 概要

BraveJIG CLIプロジェクトの完全なテスト戦略を実装。以下の4つのテストレベルをサポート：

1. **単体テスト** - モックを使用したコンポーネント単体テスト
2. **統合テスト** - Socatを使用したリアルタイム通信監視統合テスト
3. **実機テスト** - 実際のハードウェアでの自動テスト
4. **パフォーマンステスト** - 応答時間と負荷テスト

## ディレクトリ構造

```
tests/
├── README_TESTING_FRAMEWORK.md    # このファイル
├── test_framework/                 # テストフレームワーク基盤
│   ├── __init__.py
│   ├── mock_router.py             # モックルーター実装
│   ├── test_utilities.py          # テストユーティリティ
│   └── assertions.py              # 専用アサーション
├── integration/                    # 統合テスト環境
│   ├── __init__.py
│   └── socat_test_environment.py  # Socatテスト環境
├── hardware/                      # 実機テスト
│   └── test_helpers.py            # 実機テストヘルパー
├── test_scenarios/                 # テストシナリオ定義
│   └── illuminance_scenarios.py   # 照度モジュールシナリオ
├── examples/                       # テスト実装例
│   ├── example_unit_tests.py      # 単体テスト例
│   └── example_integration_tests.py # 統合テスト例
└── [existing files...]            # 既存のテストファイル
    ├── README.md                  # 既存のsocat環境ドキュメント
    ├── setup_test_environment.sh
    ├── cleanup_test_environment.sh
    ├── test_runner.py
    └── serial_monitor.py
```

## 1. 単体テスト（Unit Tests）

### 特徴

- **モック使用**: `MockBraveJIGRouter`で実機なしテスト
- **高速実行**: レスポンス制御可能
- **包括的カバレッジ**: エラーケース含む全パターンテスト
- **専用アサーション**: BraveJIG固有の検証機能

### 使用方法

```python
from tests.test_framework import MockBraveJIGRouter, BraveJIGTestCase
from module.illuminance import IlluminanceModule

class MyUnitTest(BraveJIGTestCase):
    def setUp(self):
        super().setUp()
        self.mock_router = MockBraveJIGRouter()
        self.module = IlluminanceModule("2468800203400004")
        
    def test_parameter_get(self):
        # モック応答設定
        self.mock_router.simulate_sensor_uplink(0x2468800203400004, "parameter_info")
        
        # コマンド実行
        send_cb, recv_cb = self.test_utils.create_mock_callbacks(self.mock_router)
        result = self.module.get_parameter(send_cb, recv_cb)
        
        # BraveJIG専用アサーション
        self.assertCommandSuccess(result)
        self.assertParameterInfo(result["parameter_info"])
```

### 実行

```bash
# 単体テスト実行
python -m pytest tests/examples/example_unit_tests.py -v

# または直接実行
python tests/examples/example_unit_tests.py
```

## 2. 統合テスト（Integration Tests）

### Socatベース統合テスト環境

**特徴**:
- **リアルタイム監視**: 物理JIGルーターとの通信を2系統で監視
- **プロトコル解析**: パケットレベルでの詳細な通信ログ
- **自動テストシーケンス**: 複数コマンドの連続実行と検証
- **エラー注入**: 異常系テストのサポート

**アーキテクチャ**:
```
物理JIGルーター (/dev/ttyACM0)
            |
            | (socat multiplexer)
            |
    +-------+-------+
    |               |
Monitor PTY     CLI PTY
(/tmp/bjig_monitor) (/tmp/bjig_cli)
    |               |
Protocol Monitor   CLI Commands
(Real-time analysis) (Automated execution)
```

### 使用方法

```python
from tests.integration import IntegratedTestRunner, SocatTestConfig

# 設定
config = SocatTestConfig(
    physical_device="/dev/ttyACM0",
    baudrate=38400
)

runner = IntegratedTestRunner(config)

# 環境セットアップ
runner.setup_environment()

# テスト実行（リアルタイム監視付き）
result = runner.run_test_sequence("Basic Tests", [
    {"name": "Get Version", "args": ["router", "get-version"]},
    {"name": "Get Parameters", "args": ["module", "get-parameter", "--module-id", "2468800203400004"]}
])

# クリーンアップ
runner.cleanup_environment()
```

### 実行

```bash
# 統合テスト実行
python tests/examples/example_integration_tests.py socat

# または既存の環境使用
./tests/setup_test_environment.sh /dev/ttyACM0 38400
python tests/examples/example_integration_tests.py
./tests/cleanup_test_environment.sh
```

## 3. 実機テスト（Hardware Tests）

### 特徴

- **自動デバイス検出**: BraveJIGルーターの自動発見
- **接続性検証**: ルーター通信の事前確認
- **リトライ機能**: 不安定な接続への対応
- **包括的レポート**: HTML/JSON/テキスト形式でのレポート生成

### 使用方法

```python
from tests.hardware.test_helpers import HardwareTestRunner, HardwareTestConfig

# 設定（ポート自動検出）
config = HardwareTestConfig(
    baudrate=38400,
    command_timeout=45.0,
    retry_count=2
)

runner = HardwareTestRunner(config)

# 環境セットアップ（デバイス自動検出）
setup_result = runner.setup_test_environment()

# 定義済みテストスイート実行
results = runner.run_hardware_tests("illuminance_basic")

# レポート生成
runner.command_runner.generate_test_report(results, "html")
```

### 定義済みテストスイート

- `router_basic`: ルーター基本機能テスト
- `illuminance_basic`: 照度モジュール基本テスト
- `illuminance_advanced`: パラメータ設定・検証テスト
- `default`: 最小限の健全性チェック

### 実行

```bash
# 実機テスト実行
python tests/examples/example_integration_tests.py hardware

# 特定のテストスイート
python tests/hardware/test_helpers.py --suite illuminance_advanced
```

## 4. テストシナリオとデータ

### シナリオベーステスト

包括的なテストシナリオを定義済み：

```python
from tests.test_scenarios.illuminance_scenarios import IlluminanceTestScenarios

# 全シナリオ取得
scenarios = IlluminanceTestScenarios.get_all_scenarios()
# {
#   "unit": [...],           # 単体テストシナリオ
#   "integration": [...],    # 統合テストシナリオ  
#   "error": [...],         # エラーケース
#   "performance": [...]     # パフォーマンステスト
# }

# 実機テスト用シーケンス
hardware_sequences = IlluminanceTestScenarios.get_hardware_test_sequences()
```

### テストデータ生成

```python
from tests.test_scenarios.illuminance_scenarios import IlluminanceTestData

# 有効なパラメータセット
valid_params = IlluminanceTestData.get_valid_parameters()

# パラメータバリエーション（境界値テスト用）
variations = IlluminanceTestData.get_parameter_variations()

# 無効なパラメータ（エラーケース）
invalid_cases = IlluminanceTestData.get_invalid_parameters()

# モックセンサーデータ
sensor_data = IlluminanceTestData.get_mock_sensor_data()
```

## 5. 専用アサーション

BraveJIG固有の検証を簡単に：

```python
from tests.test_framework import BraveJIGAssertions

# デバイスID検証
BraveJIGAssertions.assert_valid_device_id("2468800203400004")

# センサーID検証（照度センサー）
BraveJIGAssertions.assert_illuminance_sensor_id(0x0121)

# コマンド応答検証
BraveJIGAssertions.assert_command_success(result)

# パケット構造検証
BraveJIGAssertions.assert_packet_structure(packet, expected_type=0x00)

# 応答時間検証
BraveJIGAssertions.assert_response_time(duration, max_time=10.0)

# パラメータ検証
BraveJIGAssertions.assert_parameter_validation(validation_result)
```

## 6. 実行環境セットアップ

### 必要なソフトウェア

```bash
# macOS
brew install socat

# Ubuntu/Debian
sudo apt-get install socat

# Python dependencies
pip install pyserial pytest
```

### デバイス権限設定

```bash
# Linux
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyACM0

# macOS
sudo chmod 666 /dev/cu.usbmodem*
```

### テスト環境の確認

```bash
# デバイス検出テスト
python -c "
from tests.hardware.test_helpers import SerialDeviceDetector
devices = SerialDeviceDetector.detect_bjig_routers()
for d in devices:
    print(f'{d[\"port\"]}: {d[\"description\"]}')
"

# 接続性テスト
python -c "
from tests.hardware.test_helpers import SerialDeviceDetector
result = SerialDeviceDetector.test_router_connectivity('/dev/ttyACM0')
print(f'Connection: {result[\"connected\"]}')
"
```

## 7. 継続的インテグレーション

### GitHub Actions設定例

```yaml
name: BraveJIG CLI Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest
      - name: Run unit tests
        run: |
          python -m pytest tests/examples/example_unit_tests.py -v
  
  # 実機テストは別のワークフロー（手動実行）として設定
```

### ローカル開発での推奨フロー

```bash
# 1. 開発中: 単体テスト（高速）
python tests/examples/example_unit_tests.py

# 2. 機能完成: 統合テスト（実機確認）
python tests/examples/example_integration_tests.py hardware

# 3. リリース前: 包括テスト
python tests/examples/example_integration_tests.py socat
```

## 8. テストレポートとログ

### 出力ファイル

```
/tmp/bjig_test_results/          # 統合テスト結果
├── packet_log_20250810_143022.json
├── test_results_20250810_143022.json
└── ...

/tmp/bjig_hardware_test_results/  # 実機テスト結果
├── test_report_20250810_143500.html
├── test_report_20250810_143500.json
├── test_report_20250810_143500.txt
└── ...
```

### レポート例

**HTML レポート**: ブラウザで確認可能なビジュアルレポート
**JSON レポート**: 詳細なテストデータ（CI/CD連携用）
**テキスト レポート**: コマンドライン表示用サマリー

## 9. トラブルシューティング

### よくある問題

**デバイスが見つからない**
```bash
# デバイス確認
ls -la /dev/tty*
system_profiler SPUSBDataType | grep -A5 -B5 "Serial"  # macOS
```

**権限エラー**
```bash
sudo chmod 666 /dev/ttyACM0
sudo usermod -a -G dialout $USER  # Linux
```

**Socatプロセスが残っている**
```bash
pkill -f socat
rm -f /tmp/bjig_*
```

**テストタイムアウト**
- ネットワーク遅延: timeout値を増加
- ルーター応答遅延: retry_count増加
- 大量データ: chunk サイズ調整

### デバッグ方法

```python
# ログレベル設定
import logging
logging.basicConfig(level=logging.DEBUG)

# パケットログ確認
packet_log = mock_router.get_packet_log()
for packet in packet_log:
    print(f"{packet['direction']}: {packet['raw_data']}")

# 詳細タイミング測定
test_utils.timing.start_timing("operation")
# ... テスト実行 ...
duration = test_utils.timing.end_timing("operation")
```

## 10. 今後の拡張

### 新しいモジュールのテスト追加

1. **テストシナリオ作成**
   ```python
   # tests/test_scenarios/your_module_scenarios.py
   class YourModuleTestScenarios:
       @staticmethod
       def get_unit_test_scenarios():
           # シナリオ定義
   ```

2. **モック応答追加**
   ```python
   # tests/test_framework/mock_router.py
   def _setup_your_module_responses(self, device):
       # モック応答設定
   ```

3. **テスト実装**
   ```python
   # tests/examples/your_module_tests.py
   class YourModuleUnitTests(BraveJIGTestCase):
       # テスト実装
   ```

### パフォーマンス監視強化

- メモリ使用量監視
- CPU使用率測定
- ネットワーク帯域測定
- 長時間安定性テスト

### 自動化強化

- 定期的な健全性チェック
- 回帰テスト自動実行
- パフォーマンス劣化検出
- テスト結果の可視化ダッシュボード

---

## まとめ

この包括的テストフレームワークにより、BraveJIG CLIの品質保証が大幅に向上します：

- **開発効率**: モックによる高速テスト
- **品質保証**: 実機での包括的検証  
- **デバッグ支援**: リアルタイム通信監視
- **自動化**: CI/CD統合と継続的テスト

各テストレベルを適切に使い分けることで、効率的かつ確実な品質保証が実現できます。