#!/usr/bin/env python3
import argparse
import sys

def main():
    # メインのArgumentParserオブジェクトを作成
    parser = argparse.ArgumentParser(
        description='シリアル通信でデバイスを制御するプログラム',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  %(prog)s --port /dev/ttyACM0 --baud 9600 router start
  %(prog)s --port /dev/ttyACM0 --baud 9600 router stop
  %(prog)s --port /dev/ttyACM0 --baud 9600 router get-version
  %(prog)s --port /dev/ttyACM0 --baud 9600 router get-device-id
  %(prog)s --port /dev/ttyACM0 --baud 9600 router get-device-id 0
  %(prog)s --port /dev/ttyACM0 --baud 9600 router get-scan-mode
  %(prog)s --port /dev/ttyACM0 --baud 9600 router set-scan-mode 1
  %(prog)s --port /dev/ttyACM0 --baud 9600 router remove-device-id
  %(prog)s --port /dev/ttyACM0 --baud 9600 router remove-device-id 0
  %(prog)s --port /dev/ttyACM0 --baud 9600 router keep-alive
  %(prog)s --port /dev/ttyACM0 --baud 9600 router dfu --file "./newfw.bin"
  %(prog)s -p /dev/ttyUSB0 -b 38400 module get-params --sensor-id "0121" --module-id "001122334455667788"
  %(prog)s --port COM3 --baud 9600 module set-params --sensor-id "0121" --module-id "001122334455667788" --value '{\"scanMode\": 0}'
  %(prog)s --port /dev/ttyACM0 --baud 9600 module get-data --sensor-id "0121" --module-id "001122334455667788"
  %(prog)s --port /dev/ttyACM0 --baud 9600 module set-data --sensor-id "0121" --module-id "001122334455667788" --value '{\"signal\": 1, \"outTime\": 1000}'
  %(prog)s --port /dev/ttyACM0 --baud 9600 module restart --sensor-id "0121" --module-id "001122334455667788"
  %(prog)s --port /dev/ttyACM0 --baud 9600 module dfu --sensor-id "0121" --module-id "001122334455667788" --file "./newfw.bin"
  %(prog)s --port /dev/ttyACM0 --baud 9600 monitor
        '''
    )

    # 共通のオプション引数を追加
    parser.add_argument(
        '--port', '-p',
        required=True,
        help='シリアルポートのパス (例: /dev/ttyACM0, COM3)'
    )

    parser.add_argument(
        '--baud', '-b',
        type=int,
        default=38400,
        help='ボーレート (デフォルト: 38400)'
    )

    # サブコマンドを追加
    subparsers = parser.add_subparsers(
        dest='device',
        help='制御するデバイスのタイプ',
        required=True
    )

    # routerサブコマンド
    router_parser = subparsers.add_parser(
        'router',
        help='ルーターの制御'
    )
    router_subparsers = router_parser.add_subparsers(
        dest='router_action',
        help='ルーターのアクション',
        required=True
    )

    # router start
    router_start_parser = router_subparsers.add_parser(
        'start',
        help='ルーターを開始'
    )

    # router stop
    router_stop_parser = router_subparsers.add_parser(
        'stop',
        help='ルーターを停止'
    )

    # router get-version
    router_get_version_parser = router_subparsers.add_parser(
        'get-version',
        help='ルーターのバージョン情報を取得'
    )

    # router get-device-id
    router_get_device_id_parser = router_subparsers.add_parser(
        'get-device-id',
        help='デバイスIDを取得'
    )
    router_get_device_id_parser.add_argument(
        'device_index',
        nargs='?',
        type=int,
        help='デバイスインデックス (オプション)'
    )

    # router get-scan-mode
    router_get_scan_mode_parser = router_subparsers.add_parser(
        'get-scan-mode',
        help='スキャンモードを取得'
    )

    # router set-scan-mode
    router_set_scan_mode_parser = router_subparsers.add_parser(
        'set-scan-mode',
        help='スキャンモードを設定'
    )
    router_set_scan_mode_parser.add_argument(
        'mode',
        type=int,
        help='スキャンモード (数値)'
    )

    # router remove-device-id
    router_remove_device_id_parser = router_subparsers.add_parser(
        'remove-device-id',
        help='デバイスIDを削除'
    )
    router_remove_device_id_parser.add_argument(
        'device_index',
        nargs='?',
        type=int,
        help='デバイスインデックス (オプション)'
    )

    # router keep-alive
    router_keep_alive_parser = router_subparsers.add_parser(
        'keep-alive',
        help='キープアライブ信号を送信'
    )

    # router dfu
    router_dfu_parser = router_subparsers.add_parser(
        'dfu',
        help='DFU (Device Firmware Update) を実行'
    )
    router_dfu_parser.add_argument(
        '--file',
        required=True,
        help='ファームウェアファイルのパス'
    )

    # moduleサブコマンド
    module_parser = subparsers.add_parser(
        'module',
        help='モジュールの制御'
    )
    module_subparsers = module_parser.add_subparsers(
        dest='module_action',
        help='モジュールのアクション',
        required=True
    )

    # module get-params サブコマンド
    get_params_parser = module_subparsers.add_parser(
        'get-params',
        help='モジュールのパラメータを取得'
    )
    get_params_parser.add_argument(
        '--sensor-id',
        required=True,
        help='センサーID'
    )
    get_params_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )

    # module set-params サブコマンド
    set_params_parser = module_subparsers.add_parser(
        'set-params',
        help='モジュールのパラメータを設定'
    )
    set_params_parser.add_argument(
        '--sensor-id',
        required=True,
        help='センサーID'
    )
    set_params_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )
    set_params_parser.add_argument(
        '--value',
        required=True,
        help='設定する値 (JSON文字列も可)'
    )

    # module get-data サブコマンド
    get_data_parser = module_subparsers.add_parser(
        'get-data',
        help='モジュールのデータを取得'
    )
    get_data_parser.add_argument(
        '--sensor-id',
        required=True,
        help='センサーID'
    )
    get_data_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )

    # module set-data サブコマンド
    set_data_parser = module_subparsers.add_parser(
        'set-data',
        help='モジュールのデータを設定'
    )
    set_data_parser.add_argument(
        '--sensor-id',
        required=True,
        help='センサーID'
    )
    set_data_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )
    set_data_parser.add_argument(
        '--value',
        required=True,
        help='設定するデータ (JSON文字列)'
    )

    # module restart サブコマンド
    restart_parser = module_subparsers.add_parser(
        'restart',
        help='モジュールを再起動'
    )
    restart_parser.add_argument(
        '--sensor-id',
        required=True,
        help='センサーID'
    )
    restart_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )

    # module dfu サブコマンド
    module_dfu_parser = module_subparsers.add_parser(
        'dfu',
        help='モジュールのDFU (Device Firmware Update) を実行'
    )
    module_dfu_parser.add_argument(
        '--sensor-id',
        required=True,
        help='センサーID'
    )
    module_dfu_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )
    module_dfu_parser.add_argument(
        '--file',
        required=True,
        help='ファームウェアファイルのパス'
    )

    # monitorサブコマンド
    monitor_parser = subparsers.add_parser(
        'monitor',
        help='モニターの制御'
    )
    # monitorにはactionなし（コマンドのみ）

    # 引数を解析
    try:
        args = parser.parse_args()
    except SystemExit:
        return 1

    # 解析された引数を表示
    print(f"シリアルポート: {args.port}")
    print(f"ボーレート: {args.baud}")
    print(f"デバイス: {args.device}")

    # デバイスタイプに応じて処理を分岐
    if args.device == 'router':
        handle_router_command(args)
    elif args.device == 'module':
        handle_module_command(args)
    elif args.device == 'monitor':
        handle_monitor_command(args)

    return 0

def handle_router_command(args):
    """ルーターコマンドを処理"""
    print(f"ルーターアクション: {args.router_action}")

    if args.router_action == 'start':
        execute_router_start(args.port, args.baud)
    elif args.router_action == 'stop':
        execute_router_stop(args.port, args.baud)
    elif args.router_action == 'get-version':
        execute_router_get_version(args.port, args.baud)
    elif args.router_action == 'get-device-id':
        execute_router_get_device_id(args.port, args.baud, args.device_index)
    elif args.router_action == 'get-scan-mode':
        execute_router_get_scan_mode(args.port, args.baud)
    elif args.router_action == 'set-scan-mode':
        execute_router_set_scan_mode(args.port, args.baud, args.mode)
    elif args.router_action == 'remove-device-id':
        execute_router_remove_device_id(args.port, args.baud, args.device_index)
    elif args.router_action == 'keep-alive':
        execute_router_keep_alive(args.port, args.baud)
    elif args.router_action == 'dfu':
        execute_router_dfu(args.port, args.baud, args.file)

def handle_monitor_command(args):
    """モニターコマンドを処理"""
    print("モニター開始")
    execute_monitor_command(args.port, args.baud)

def handle_module_command(args):
    """モジュールコマンドを処理"""
    print(f"モジュールアクション: {args.module_action}")

    if args.module_action == 'get-params':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        execute_module_get_params(args.port, args.baud, args.sensor_id, args.module_id)

    elif args.module_action == 'set-params':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        print(f"設定値: {args.value}")
        execute_module_set_params(args.port, args.baud, args.sensor_id, args.module_id, args.value)

    elif args.module_action == 'get-data':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        execute_module_get_data(args.port, args.baud, args.sensor_id, args.module_id)

    elif args.module_action == 'set-data':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        print(f"設定データ: {args.value}")
        execute_module_set_data(args.port, args.baud, args.sensor_id, args.module_id, args.value)

    elif args.module_action == 'restart':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        execute_module_restart(args.port, args.baud, args.sensor_id, args.module_id)

    elif args.module_action == 'dfu':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        print(f"ファームウェアファイル: {args.file}")
        execute_module_dfu(args.port, args.baud, args.sensor_id, args.module_id, args.file)

def execute_router_start(port, baud):
    """ルーター開始コマンドを実行"""
    print(f"\nルーターを開始中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print("ルーターを開始しています...")
    print("完了しました。")

def execute_router_stop(port, baud):
    """ルーター停止コマンドを実行"""
    print(f"\nルーターを停止中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print("ルーターを停止しています...")
    print("完了しました。")

def execute_router_get_version(port, baud):
    """ルーターバージョン取得コマンドを実行"""
    print(f"\nルーターのバージョン情報を取得中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print("バージョン: v2.1.3")  # 例
    print("完了しました。")

def execute_router_get_device_id(port, baud, device_index):
    """デバイスID取得コマンドを実行"""
    print(f"\nデバイスIDを取得中...")
    print(f"接続先: {port} (ボーレート: {baud})")

    if device_index is not None:
        print(f"対象デバイスインデックス: {device_index}")
        print(f"デバイス{device_index}のID: ABC123DEF456")  # 例
    else:
        print("全デバイスのIDを取得中...")
        print("デバイス0: ABC123DEF456")
        print("デバイス1: GHI789JKL012")

    print("完了しました。")

def execute_router_get_scan_mode(port, baud):
    """スキャンモード取得コマンドを実行"""
    print(f"\nスキャンモードを取得中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print("現在のスキャンモード: 1")  # 例
    print("完了しました。")

def execute_router_set_scan_mode(port, baud, mode):
    """スキャンモード設定コマンドを実行"""
    print(f"\nスキャンモードを設定中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"設定するモード: {mode}")
    print(f"スキャンモードを{mode}に設定しました")
    print("完了しました。")

def execute_router_remove_device_id(port, baud, device_index):
    """デバイスID削除コマンドを実行"""
    print(f"\nデバイスIDを削除中...")
    print(f"接続先: {port} (ボーレート: {baud})")

    if device_index is not None:
        print(f"対象デバイスインデックス: {device_index}")
        print(f"デバイス{device_index}のIDを削除しました")
    else:
        print("全デバイスのIDを削除中...")
        print("全デバイスIDを削除しました")

    print("完了しました。")

def execute_router_keep_alive(port, baud):
    """キープアライブコマンドを実行"""
    print(f"\nキープアライブ信号を送信中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print("キープアライブ信号を送信しました")
    print("完了しました。")

def execute_router_dfu(port, baud, firmware_file):
    """DFUコマンドを実行"""
    print(f"\nDFU (Device Firmware Update) を実行中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"ファームウェアファイル: {firmware_file}")

    # ファイル存在チェック
    import os
    if not os.path.exists(firmware_file):
        print(f"エラー: ファイル '{firmware_file}' が見つかりません")
        return

    print("DFUモードに切り替え中...")
    print("ファームウェア転送中...")
    print("DFU完了 - デバイスを再起動してください")
    print("完了しました。")

def execute_monitor_command(port, baud):
    """モニターコマンドを実行"""
    print(f"\nモニターを開始中...")
    print(f"接続先: {port} (ボーレート: {baud})")

    # ここに実際のモニタリング処理を書く
    print("モニタリング開始...")
    print("リアルタイム監視中... (Ctrl+Cで停止)")
    print("完了しました。")

def execute_module_get_params(port, baud, sensor_id, module_id):
    """モジュールのパラメータ取得を実行"""
    print(f"\nモジュール {module_id} のパラメータを取得中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"対象センサー: {sensor_id}")

    # ここに実際のシリアル通信処理を書く
    # 例: シリアル通信でget-paramsコマンドを送信
    print("パラメータ取得コマンドを送信中...")
    print("応答を待機中...")
    print("パラメータ取得完了")

def execute_module_set_params(port, baud, sensor_id, module_id, value):
    """モジュールのパラメータ設定を実行"""
    print(f"\nモジュール {module_id} のパラメータを設定中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"対象センサー: {sensor_id}")
    print(f"設定値: {value}")

    # JSON文字列かどうかを判定
    import json
    try:
        # JSON文字列の場合はパース可能
        json_value = json.loads(value)
        print(f"JSON形式で解釈: {json_value}")
        print(f"データ型: {type(json_value)}")
    except json.JSONDecodeError:
        # 通常の文字列の場合
        print(f"文字列として処理: {value}")

    # ここに実際のシリアル通信処理を書く
    print("パラメータ設定コマンドを送信中...")
    print("設定完了")

def execute_module_get_data(port, baud, sensor_id, module_id):
    """モジュールのデータ取得を実行"""
    print(f"\nモジュール {module_id} のデータを取得中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"対象センサー: {sensor_id}")

    # ここに実際のシリアル通信処理を書く
    print("データ取得コマンドを送信中...")
    print("応答を待機中...")
    print("取得したデータ: {\"temperature\": 25.3, \"humidity\": 60.2}")  # 例
    print("データ取得完了")

def execute_module_set_data(port, baud, sensor_id, module_id, value):
    """モジュールのデータ設定を実行"""
    print(f"\nモジュール {module_id} のデータを設定中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"対象センサー: {sensor_id}")
    print(f"設定データ: {value}")

    # JSON文字列かどうかを判定
    import json
    try:
        # JSON文字列の場合はパース可能
        json_value = json.loads(value)
        print(f"JSON形式で解釈: {json_value}")
        print(f"データ型: {type(json_value)}")

        # 例: signalとoutTimeの値を確認
        if 'signal' in json_value:
            print(f"シグナル値: {json_value['signal']}")
        if 'outTime' in json_value:
            print(f"出力時間: {json_value['outTime']}ms")

    except json.JSONDecodeError:
        # 通常の文字列の場合
        print(f"文字列として処理: {value}")

    # ここに実際のシリアル通信処理を書く
    print("データ設定コマンドを送信中...")
    print("設定完了")

def execute_module_restart(port, baud, sensor_id, module_id):
    """モジュールの再起動を実行"""
    print(f"\nモジュール {module_id} を再起動中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"対象センサー: {sensor_id}")

    # ここに実際のシリアル通信処理を書く
    print("再起動コマンドを送信中...")
    print("モジュールを再起動しています...")
    print("再起動完了")

def execute_module_dfu(port, baud, sensor_id, module_id, firmware_file):
    """モジュールのDFUを実行"""
    print(f"\nモジュール {module_id} のDFU (Device Firmware Update) を実行中...")
    print(f"接続先: {port} (ボーレート: {baud})")
    print(f"対象センサー: {sensor_id}")
    print(f"ファームウェアファイル: {firmware_file}")

    # ファイル存在チェック
    import os
    if not os.path.exists(firmware_file):
        print(f"エラー: ファイル '{firmware_file}' が見つかりません")
        return

    print("モジュールをDFUモードに切り替え中...")
    print("ファームウェア転送中...")
    print("DFU完了 - モジュールを再起動してください")
    print("完了しました。")

def execute_module_status(port, baud, module_id):
    """モジュールのステータス確認を実行"""
    target = module_id if module_id else "全モジュール"
    print(f"\n{target} のステータスを確認中...")
    print(f"接続先: {port} (ボーレート: {baud})")

    # ここに実際のシリアル通信処理を書く
    print("ステータス確認完了")

if __name__ == '__main__':
    sys.exit(main())
