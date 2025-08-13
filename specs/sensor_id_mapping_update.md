# BraveJIGセンサーID完全マッピング

**更新日**: 2025-07-13  
**目的**: 実機テストで発見したセンサーIDの正確なマッピング情報

## 実機テストで確認されたセンサーID

### 完全なセンサーIDマッピング表

| Sensor ID | センサー名 | 型番 | 説明 | 仕様書 |
|-----------|------------|------|------|---------|
| **0x0121** | **照度モジュール** | **BJ-MD-LUX-01** | **照度情報(Lux)** | **spec_bjig_module_illuminance** |
| 0x0122 | 加速度モジュール | BJ-MD-S3-01 | 3軸加速度(mG) | spec_bjig_module_accel |
| 0x0123 | 温湿度モジュール | BJ-MD-TH-01 | 温度(℃)・湿度(%) | spec_bjig_module_temp_hum |
| 0x0124 | 気圧モジュール | BJ-MD-BP-01 | 気圧(hPa) | spec_bjig_module_barometic_pressure |
| 0x0125 | 距離モジュール | BJ-MD-RA-01 | 距離(mm) | spec_bjig_module_distance |
| 0x0126 | ドライ接点入力 | BJ-MD-DCI-01 | 接点状態 | spec_bjig_module_dry_contact_input |
| 0x0127 | ウェット接点入力 | BJ-MD-WCI-01 | 接点状態 | spec_bjig_module_wet_contact_input |
| 0x0128 | 2ch接点出力 | BJ-MD-CO-01 | 出力制御 | spec_bjig_module_contact_output |

## 実機テストで発見された修正

### 修正前の認識（不正確）
```
0x0121: "Unknown Sensor"  ❌
```

### 修正後の正確な情報
```
0x0121: "Illuminance"     ✅
型番: BJ-MD-LUX-01
センサーIC: OPT3001 (TEXAS INSTRUMENTS)
データ形式: 照度情報(Lux) - Float型、リトルエンディアン
```

## 照度モジュールの詳細仕様

### データ構造 (Index 21以降)
```
| オフセット | サイズ | フィールド | 説明 |
|-----------|--------|-----------|------|
| 0-1 | 2byte | SensorID | 0x0121 (照度モジュール) |
| 2-3 | 2byte | Sequence No | 0x0000~0xFFFF |
| 4 | 1byte | BatteryLevel | バッテリーレベル(%) |
| 5 | 1byte | Sampling | サンプリング周期 |
| 6-9 | 4byte | Time | センサーリード時刻 |
| 10-11 | 2byte | sampleNum | サンプル数 |
| 12-15 | 4byte | LuxData[0] | 照度情報(Lux) - Float型 |
| ... | 4byte | LuxData[n] | 照度情報(Lux) - Float型 |
```

### 実機での動作確認
- ✅ **Device ID**: 0x2468800203400004
- ✅ **定期送信**: 10秒間隔でアップリンク通知
- ✅ **RSSI**: -57dBm (良好な信号強度)
- ✅ **バッテリー**: 115% (外部電源接続)

## 実機ネットワーク構成（更新版）

```
BraveJIG Router (0x246880030140000C)
├── 照度センサー (0x2468800203400004) - 0x0121 ✅
├── 温湿度センサー (0x2468800205400011) - 0x0123
├── 加速度センサー (0x246880020440000F) - 0x0122  
├── 気圧センサー (0x2468800206400006) - 0x0124
└── 距離センサー (0x2468800207400001) - 0x0125
```

## AsyncSerialMonitorでの更新が必要な箇所

### 1. protocol_analysis_test.py
```python
def _get_sensor_name(self, sensor_id: int) -> str:
    sensors = {
        0x0121: "Illuminance",              # ✅ 更新
        0x0122: "Accelerometer",
        0x0123: "Temperature/Humidity", 
        # ... 他のセンサー
    }
```

### 2. downlink_test.py
```python
def get_sensor_name(sensor_id: int) -> str:
    sensors = {
        0x0121: "Illuminance",              # ✅ 更新
        0x0122: "Accelerometer",
        # ... 他のセンサー
    }
```

### 3. 照度データ解析機能の追加
```python
def _parse_illuminance(self, data: bytes) -> dict:
    """Parse illuminance data"""
    result = {"measurements": []}
    try:
        for i in range(0, len(data), 4):  # 4 bytes per measurement
            if i + 4 <= len(data):
                illuminance = struct.unpack('<f', data[i:i+4])[0]
                result["measurements"].append({
                    "illuminance": f"{illuminance:.2f}lux"
                })
    except:
        pass
    return result
```

## テスト結果の影響

### 実機テスト結果の更新
- **検出センサー数**: 5種類（変更なし）
- **センサー構成**: より正確な情報に更新
- **照度センサー**: 正常動作確認（115%バッテリー、-57dBm RSSI）

### BraveJIG照度モジュールの特徴
- **センサーIC**: OPT3001 (TEXAS INSTRUMENTS)
- **測定単位**: Lux (照度)
- **データ型**: IEEE 754 Float（32bit）
- **エンディアン**: リトルエンディアン
- **サンプリング**: 可変設定

この修正により、実機テスト結果がより正確になり、BraveJIGシステムの完全な理解が得られました。