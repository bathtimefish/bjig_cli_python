#!/usr/bin/env python3
import argparse
import sys
import logging
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.bjig_commander import BraveJIGCommander, CommandResult

def main():
    # メインのArgumentParserオブジェクトを作成
    parser = argparse.ArgumentParser(
        description='シリアル通信でデバイスを制御するプログラム',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
main.py --port /dev/ttyACM0 --baud 38400 router start
main.py --port /dev/ttyACM0 --baud 38400 router stop
main.py --port /dev/ttyACM0 --baud 38400 router get-version
main.py --port /dev/ttyACM0 --baud 38400 router get-device-id
main.py --port /dev/ttyACM0 --baud 38400 router get-device-id 0
main.py --port /dev/ttyACM0 --baud 38400 router get-scan-mode
main.py --port /dev/ttyACM0 --baud 38400 router set-scan-mode 1
main.py --port /dev/ttyACM0 --baud 38400 router remove-device-id
main.py --port /dev/ttyACM0 --baud 38400 router remove-device-id 0
main.py --port /dev/ttyACM0 --baud 38400 router keep-alive
main.py --port /dev/ttyACM0 --baud 38400 router dfu --file "./newfw.bin"
main.py --port /dev/ttyACM0 --baud 38400 module instant-uplink --module-id "001122334455667788"
main.py --port /dev/ttyUSB0 --baud 38400 module get-parameter --module-id "001122334455667788"
main.py --port /dev/ttyACM0 --baud 38400 module set-parameter --sensor-id "0121" --module-id "001122334455667788" --data "{\"scanMode\": 0}"
main.py --port /dev/ttyACM0 --baud 38400 module restart --module-id "001122334455667788"
main.py --port /dev/ttyACM0 --baud 38400 module sensor-dfu --sensor-id "0121" --module-id "001122334455667788" --file "./newfw.bin"
main.py --port /dev/ttyACM0 --baud 38400 monitor
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

    # module get-parameter サブコマンド
    get_params_parser = module_subparsers.add_parser(
        'get-parameter',
        help='モジュールのパラメータを取得'
    )
    get_params_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )

    # module set-parameter サブコマンド
    set_params_parser = module_subparsers.add_parser(
        'set-parameter',
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
        '--data',
        required=True,
        help='設定する値 (JSON文字列)'
    )

    # module instant-uplink サブコマンド
    instant_uplink_parser = module_subparsers.add_parser(
        'instant-uplink',
        help='モジュールの即時Uplinkを要求'
    )
    instant_uplink_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )

    # module restart サブコマンド
    restart_parser = module_subparsers.add_parser(
        'restart',
        help='モジュールを再起動'
    )
    restart_parser.add_argument(
        '--module-id',
        required=True,
        help='モジュールID'
    )

    # module sensor-dfu サブコマンド
    module_dfu_parser = module_subparsers.add_parser(
        'sensor-dfu',
        help='モジュールのセンサーDFU (Device Firmware Update) を実行'
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
        # DFU時はボーレート38400必須
        if args.baud != 38400:
            print("❌ エラー: DFUを実行するにはボーレートは 38400 である必要があります。--baud 38400 を指定してください。")
            return
        execute_router_dfu(args.port, args.baud, args.file)

def handle_monitor_command(args):
    """モニターコマンドを処理"""
    print("モニター開始")
    execute_monitor_command(args.port, args.baud)

def handle_module_command(args):
    """モジュールコマンドを処理"""
    print(f"モジュールアクション: {args.module_action}")

    if args.module_action == 'get-parameter':
        print(f"センサーID: {getattr(args, 'sensor_id', 'N/A')}")
        print(f"モジュールID: {args.module_id}")
        execute_module_command(args.port, args.baud, getattr(args, 'sensor_id', None), args.module_id, 'get-parameter')

    elif args.module_action == 'set-parameter':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        print(f"設定値: {args.data}")
        execute_module_command(args.port, args.baud, args.sensor_id, args.module_id, 'set-parameter', data=args.data)

    elif args.module_action == 'instant-uplink':
        print(f"モジュールID: {args.module_id}")
        execute_module_command(args.port, args.baud, None, args.module_id, 'instant-uplink')

    elif args.module_action == 'restart':
        print(f"モジュールID: {args.module_id}")
        execute_module_command(args.port, args.baud, None, args.module_id, 'device-restart')

    elif args.module_action == 'sensor-dfu':
        print(f"センサーID: {args.sensor_id}")
        print(f"モジュールID: {args.module_id}")
        print(f"ファームウェアファイル: {args.file}")
        # DFU時はボーレート38400必須
        if args.baud != 38400:
            print("❌ エラー: センサーDFUを実行するにはボーレートは 38400 である必要があります。--baud 38400 を指定してください。")
            return
        execute_module_command(args.port, args.baud, args.sensor_id, args.module_id, 'sensor-dfu', firmware_file=args.file)

def execute_module_command(port: str, baud: int, sensor_id: str, module_id: str, command: str, **kwargs):
    """
    汎用モジュールコマンド実行
    
    センサーIDに基づいて適切なモジュールハンドラーに処理を委譲
    
    Args:
        port: シリアルポート
        baud: ボーレート
        sensor_id: センサーID (モジュール種別を識別)
        module_id: モジュールID
        command: 実行コマンド
        **kwargs: コマンド固有の追加パラメータ
    """
    import json
    
    try:
        # センサーIDに基づいてモジュール種別を判定
        # get-parameterの場合は照度センサー(0121)をデフォルトとする
        if (sensor_id and sensor_id.upper() == "0121") or (sensor_id is None and command == 'get-parameter'):
            # 照度センサーモジュール
            from module.illuminance.illuminance_handler import IlluminanceHandler
            handler = IlluminanceHandler()
            
            # センサーIDが指定されている場合のみ妥当性チェック
            if sensor_id and not handler.validate_sensor_id(sensor_id):
                error_output = {"error": f"Invalid sensor ID: {sensor_id}. Expected: 0121", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            if not handler.validate_module_id(module_id):
                error_output = {"error": f"Invalid module ID format: {module_id}. Expected 16 hex digits.", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            # get-parameterの場合はセンサーIDを0121にデフォルト設定
            effective_sensor_id = sensor_id if sensor_id else "0121"
            
            # コマンド実行
            if command == 'get-parameter':
                result = handler.get_parameter(port, baud, effective_sensor_id, module_id)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif command == 'set-parameter':
                data = kwargs.get('data')
                if not data:
                    error_output = {"error": "Missing parameter data for set-parameter command", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                result = handler.set_parameter(port, baud, effective_sensor_id, module_id, data)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif command == 'device-restart':
                result = handler.device_restart(port, baud, module_id)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif command == 'sensor-dfu':
                firmware_file = kwargs.get('firmware_file')
                if not firmware_file:
                    error_output = {"error": "Missing firmware file for sensor-dfu command", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                result = handler.sensor_dfu(port, baud, effective_sensor_id, module_id, firmware_file)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif command == 'instant-uplink':
                result = handler.instant_uplink(port, baud, module_id)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                supported_commands = handler.get_supported_commands()
                error_output = {
                    "error": f"Unsupported command: {command}",
                    "supported_commands": list(supported_commands.keys()),
                    "success": False
                }
                print(json.dumps(error_output, ensure_ascii=False))
        else:
            # 未知のセンサーID または センサーIDなし
            if sensor_id is None and command in ['instant-uplink', 'device-restart']:
                # センサーIDが不要なコマンドは照度モジュールとして処理
                from module.illuminance.illuminance_handler import IlluminanceHandler
                handler = IlluminanceHandler()
                
                if not handler.validate_module_id(module_id):
                    error_output = {"error": f"Invalid module ID format: {module_id}. Expected 16 hex digits.", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                if command == 'instant-uplink':
                    result = handler.instant_uplink(port, baud, module_id)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                elif command == 'device-restart':
                    result = handler.device_restart(port, baud, module_id)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                error_output = {
                    "error": f"Unsupported sensor ID: {sensor_id}. Currently supported: 0121 (illuminance)",
                    "success": False
                }
                print(json.dumps(error_output, ensure_ascii=False))
                
    except Exception as e:
        error_output = {"error": f"Module command execution failed: {str(e)}", "success": False}
        print(json.dumps(error_output, ensure_ascii=False))

def execute_router_start(port, baud):
    """ルーター開始コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_start()
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_stop(port, baud):
    """ルーター停止コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_stop()
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_get_version(port, baud):
    """ルーターバージョン取得コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_get_version()
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_get_device_id(port, baud, device_index):
    """デバイスID取得コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_get_device_id(device_index)
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_get_scan_mode(port, baud):
    """スキャンモード取得コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_get_scan_mode()
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_set_scan_mode(port, baud, mode):
    """スキャンモード設定コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_set_scan_mode(mode)
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_remove_device_id(port, baud, device_index):
    """デバイスID削除コマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_remove_device_id(device_index)
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_keep_alive(port, baud):
    """キープアライブコマンドを実行"""
    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_keep_alive()
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_router_dfu(port, baud, firmware_file):
    """DFUコマンドを実行"""
    # ファイル存在チェック
    import os
    if not os.path.exists(firmware_file):
        print(f"❌ エラー: ファイル '{firmware_file}' が見つかりません")
        return

    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.router_dfu(firmware_file)
            if result.success:
                response = result.response
                print(response.to_json())
            else:
                print(f"❌ エラー: {result.error}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")

def execute_monitor_command(port, baud):
    """モニターコマンドを実行"""
    print(f"\nモニターを開始中...")
    print(f"接続先: {port} (ボーレート: {baud})")

    try:
        with BraveJIGCommander(port, baud) as commander:
            result = commander.start_monitoring()
            if result.success:
                print("モニタリング開始...")
                print("リアルタイム監視中... (Ctrl+Cで停止)")
                
                # Keep monitoring until interrupted
                import signal
                import time
                
                def signal_handler(signum, frame):
                    print("\n監視を停止しています...")
                    raise KeyboardInterrupt
                
                signal.signal(signal.SIGINT, signal_handler)
                
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("完了しました。")
            else:
                print(f"エラー: {result.error}")
    except Exception as e:
        print(f"接続エラー: {e}")

if __name__ == '__main__':
    sys.exit(main())
