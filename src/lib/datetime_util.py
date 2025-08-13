"""
BraveJIG Protocol 日時処理ユーティリティ

このモジュールは、BraveJIGプロトコル通信で必要な日時処理を統一的に提供します。
全ての時刻データはリトルエンディアン形式で4バイトのバイト配列として処理されます。

Key features:
- Unix時間とJST時間の生成・変換
- リトルエンディアン4バイト配列との相互変換
- プロトコル層での時刻処理の統一化
- タイムゾーン処理の正確性確保

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
import time
from datetime import datetime, timezone, timedelta
from typing import Union


# JST timezone (UTC+9)
JST = timezone(timedelta(hours=9))


def get_current_unix_time() -> int:
    """
    現在のUnix時間（エポック秒）を取得
    
    Returns:
        int: 現在時刻のUnix時間（秒）
    """
    return int(time.time())


def get_current_jst_time() -> int:
    """
    現在のJST時間を取得
    
    BraveJIGプロトコルでは、JST時間はUnix時間 + 9時間として扱われます。
    
    Returns:
        int: 現在時刻のJST時間（Unix時間 + 9時間）
    """
    return int(time.time()) + 9 * 3600


def get_current_unix_time_bytes() -> bytes:
    """
    現在のUnix時間のバイト配列を取得
    
    現在の日時をUnix時間（エポック秒）に変換し、
    4バイトのリトルエンディアン形式バイト配列として返します。
    
    Returns:
        bytes: 現在時刻のUnix時間（4バイト、リトルエンディアン）
        
    Example:
        >>> data = get_current_unix_time_bytes()
        >>> len(data)
        4
        >>> isinstance(data, bytes)
        True
    """
    unix_time = get_current_unix_time()
    return struct.pack('<L', unix_time)


def get_current_jst_time_bytes() -> bytes:
    """
    現在のJST時間のバイト配列を取得
    
    現在の日時をJST（日本標準時）に変換し、
    4バイトのリトルエンディアン形式バイト配列として返します。
    
    BraveJIGプロトコルでは、JST時間はUnix時間 + 9時間として扱われます。
    
    Returns:
        bytes: 現在時刻のJST時間（4バイト、リトルエンディアン）
        
    Example:
        >>> data = get_current_jst_time_bytes()
        >>> len(data)
        4
        >>> isinstance(data, bytes)
        True
    """
    jst_time = get_current_jst_time()
    return struct.pack('<L', jst_time)


def unix_time_from_bytes(data: bytes) -> int:
    """
    Unix時間のバイト配列を整数値に変換
    
    4バイトのリトルエンディアン形式バイト配列を受け取り、
    Unix時間の整数値に変換して返します。
    
    Args:
        data (bytes): Unix時間のバイト配列（4バイト、リトルエンディアン）
        
    Returns:
        int: Unix時間の整数値（エポック秒）
        
    Raises:
        ValueError: データが4バイトでない場合
        struct.error: バイト配列の形式が正しくない場合
        
    Example:
        >>> time_bytes = struct.pack('<L', 1640995200)  # 2022-01-01 00:00:00 UTC
        >>> unix_time_from_bytes(time_bytes)
        1640995200
    """
    if len(data) != 4:
        raise ValueError(f"Unix time data must be 4 bytes, got {len(data)}")
    
    try:
        return struct.unpack('<L', data)[0]
    except struct.error as e:
        raise struct.error(f"Invalid byte format for Unix time: {e}")


def jst_time_from_bytes(data: bytes) -> int:
    """
    JST時間のバイト配列を整数値に変換
    
    4バイトのリトルエンディアン形式バイト配列を受け取り、
    JST時間の整数値に変換して返します。
    
    Args:
        data (bytes): JST時間のバイト配列（4バイト、リトルエンディアン）
        
    Returns:
        int: JST時間の整数値（Unix時間 + 9時間相当）
        
    Raises:
        ValueError: データが4バイトでない場合
        struct.error: バイト配列の形式が正しくない場合
        
    Example:
        >>> jst_bytes = struct.pack('<L', 1640995200 + 9*3600)  # 2022-01-01 09:00:00 JST
        >>> jst_time_from_bytes(jst_bytes)
        1641027600
    """
    if len(data) != 4:
        raise ValueError(f"JST time data must be 4 bytes, got {len(data)}")
    
    try:
        return struct.unpack('<L', data)[0]
    except struct.error as e:
        raise struct.error(f"Invalid byte format for JST time: {e}")


def unix_time_to_datetime(unix_time: Union[int, bytes]) -> datetime:
    """
    Unix時間をdatetimeオブジェクトに変換
    
    Args:
        unix_time: Unix時間（整数またはバイト配列）
        
    Returns:
        datetime: UTC時刻のdatetimeオブジェクト
        
    Example:
        >>> dt = unix_time_to_datetime(1640995200)
        >>> dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        '2022-01-01 00:00:00 UTC'
    """
    if isinstance(unix_time, bytes):
        unix_time = unix_time_from_bytes(unix_time)
    
    return datetime.fromtimestamp(unix_time, tz=timezone.utc)


def jst_time_to_datetime(jst_time: Union[int, bytes]) -> datetime:
    """
    JST時間をdatetimeオブジェクトに変換
    
    Args:
        jst_time: JST時間（整数またはバイト配列）
        
    Returns:
        datetime: JST時刻のdatetimeオブジェクト
        
    Example:
        >>> dt = jst_time_to_datetime(1641027600)  # Unix時間 + 9時間
        >>> dt.strftime('%Y-%m-%d %H:%M:%S JST')
        '2022-01-01 09:00:00 JST'
    """
    if isinstance(jst_time, bytes):
        jst_time = jst_time_from_bytes(jst_time)
    
    # JST時間はUnix時間 + 9時間なので、9時間を引いてからJSTタイムゾーンで変換
    utc_time = jst_time - 9 * 3600
    return datetime.fromtimestamp(utc_time, tz=JST)


def format_time_for_display(unix_time: Union[int, bytes], 
                          timezone_name: str = 'UTC') -> str:
    """
    時刻を表示用文字列にフォーマット
    
    Args:
        unix_time: Unix時間（整数またはバイト配列）
        timezone_name: タイムゾーン名（'UTC' または 'JST'）
        
    Returns:
        str: フォーマットされた時刻文字列
        
    Example:
        >>> format_time_for_display(1640995200, 'UTC')
        '2022-01-01 00:00:00 UTC'
        >>> format_time_for_display(1641027600, 'JST')
        '2022-01-01 09:00:00 JST'
    """
    if isinstance(unix_time, bytes):
        unix_time = unix_time_from_bytes(unix_time)
    
    if timezone_name.upper() == 'JST':
        dt = datetime.fromtimestamp(unix_time - 9 * 3600, tz=JST)
        return dt.strftime('%Y-%m-%d %H:%M:%S JST')
    else:
        dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def validate_time_bytes(data: bytes) -> bool:
    """
    時刻バイト配列の妥当性を検証
    
    Args:
        data: 検証する時刻バイト配列
        
    Returns:
        bool: バイト配列が有効な場合True
        
    Example:
        >>> validate_time_bytes(b'\\x00\\x01\\x02\\x03')
        True
        >>> validate_time_bytes(b'\\x00\\x01\\x02')
        False
    """
    try:
        if len(data) != 4:
            return False
        
        # リトルエンディアン形式で正常にアンパックできるかチェック
        struct.unpack('<L', data)
        return True
    except (struct.error, TypeError):
        return False


# プロトコル互換性のための便利関数
def create_protocol_time_fields() -> tuple[int, int]:
    """
    BraveJIGプロトコル用の時刻フィールドを作成
    
    Returns:
        tuple[int, int]: (local_time_jst, unix_time) のタプル
        
    Example:
        >>> local_time, unix_time = create_protocol_time_fields()
        >>> isinstance(local_time, int)
        True
        >>> isinstance(unix_time, int)
        True
        >>> local_time > unix_time  # JST時間の方が大きい
        True
    """
    unix_time = get_current_unix_time()
    jst_time = get_current_jst_time()
    return jst_time, unix_time


# 後方互換性のためのエイリアス（既存コードとの互換性維持）
get_unix_time_bytes = get_current_unix_time_bytes
get_jst_time_bytes = get_current_jst_time_bytes

def unix_time_to_readable(unix_time: int) -> str:
    """
    Unix時間を読みやすい形式の文字列に変換
    
    Args:
        unix_time: Unix時間（整数）
        
    Returns:
        str: YYYY-MM-DD HH:MM:SS 形式の文字列
        
    Example:
        >>> unix_time_to_readable(1640995200)
        '2022-01-01 00:00:00'
    """
    dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d %H:%M:%S')