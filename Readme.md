# BraveJIG CLI Python (Prototyping)

## DFU (Device Firmware Update) 仕様の要点

- センサーDFUは4ブロック方式で送信します。
	- Seq `0x0000`: header (hardwareID=0x0000 + 0xFF padding)
	- Seq `0x0001`: `dfuDataLength`(4B, LE) + ファーム最初の234B
	- Seq `0x0002..`: 継続データ 238B チャンク
	- Seq `0xFFFF`: 残りのバイトをそのまま送信
- `dfuDataLength` は配布 `.bin` の総サイズ（末尾4BのCRCを含む）をリトルエンディアンで格納します。
- 最終ブロックに追加CRCを付与しません（`.bin` 末尾に既に含まれているため）。

## DFU 実行時のボーレート

- BraveJIG の DFU は必ず `38400` bps を使用してください。
- CLI でも DFU 実行時に `--baud 38400` を強制します。

## 使い方（例）

```
python src/main.py --port /dev/ttyACM0 --baud 38400 router dfu --file ./router-fw.bin
python src/main.py --port /dev/ttyACM0 --baud 38400 module sensor-dfu --sensor-id 0121 --module-id 0011223344556677 --file ./module-fw.bin
```

## 明日以降の開発メモ

- DFU 可視化ログ
	- センサーDFUの第2ブロック送信時に、`dfuDataLength` をログ出力します（リトルエンディアン、`block[21:25]`）。
	- モニタ側でも将来的に `dfuDataLength` のデコード・表示を検討（`src/monitor/`）。

- 共通ビルダーの単一ソース化
	- センサーDFUのブロック組み立ては `module/dfu_common.py` の `build_sensor_dfu_blocks(...)` を唯一の真実とする。
	- 仕様変更があればこのビルダーを更新し、モジュール側の呼び出しのみで反映されるよう維持。

- ハードウェア検証のTips
	- DFU完了後はモジュールが自動再起動します。30–60秒待機後、`get-parameter` でFWバージョンを確認。
	- 通信が不安定な場合はケーブル・ポート・給電を確認し、再試行。

- テスト
	- `test/test_dfu_common_blocks.py` で第2ブロックの `dfuDataLength` と最終ブロック内容（追加CRC無し）を検証しています。
	- 追加の境界ケース（極小/極大サイズ、238B整列、CRC不一致の可視化）も今後追加予定。

- コーディング規約・注意
	- DFU関連の `import` は可能な限りモジュール冒頭に集約（`sensor_dfu.py` 済）。
	- DFU時のボーレートは `38400` に固定。CLIでも強制されます。

- 既知の今後の改善候補
	- 送受信のリトライ戦略とタイムアウトの段階制御（ネットワーク品質に応じた調整）。
	- 進捗UI: ブロック数に基づく進捗率表示の改善（ETA計算や残り時間推定）。
	- ログ整備: `--verbose` でDFUヘッダや時刻の詳細表示を切替。