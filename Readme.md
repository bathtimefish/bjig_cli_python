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