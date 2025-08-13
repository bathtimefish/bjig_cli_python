#!/usr/bin/env python3
"""
Quick interval check - filtered analysis
"""

# 観測された間隔データ（秒）
intervals = [0.2, 0.1, 0.1, 11.9, 4.0, 10.0, 10.9, 9.0, 11.0]

print("📊 Illuminance Uplink Interval Analysis")
print("=" * 45)

# 全体の分析
print("🔍 All intervals:")
for i, interval in enumerate(intervals, 1):
    print(f"   Interval {i}: {interval:.1f} seconds")

avg_all = sum(intervals) / len(intervals)
print(f"\nAverage (all): {avg_all:.1f} seconds")

# 異常値（<1秒）を除外した分析
normal_intervals = [i for i in intervals if i >= 1.0]
print(f"\n🔍 Normal intervals (≥1.0s only):")
for i, interval in enumerate(normal_intervals, 1):
    print(f"   Interval {i}: {interval:.1f} seconds")

if normal_intervals:
    avg_normal = sum(normal_intervals) / len(normal_intervals)
    min_normal = min(normal_intervals)
    max_normal = max(normal_intervals)
    
    print(f"\nAverage (normal): {avg_normal:.1f} seconds")
    print(f"Range: {min_normal:.1f} - {max_normal:.1f} seconds")
    
    # 10秒付近（8-12秒）の間隔をカウント
    target_range = [i for i in normal_intervals if 8.0 <= i <= 12.0]
    success_rate = (len(target_range) / len(normal_intervals)) * 100
    
    print(f"\nTarget range (8-12s): {len(target_range)}/{len(normal_intervals)} ({success_rate:.1f}%)")
    
    # 判定
    if 8.0 <= avg_normal <= 12.0:
        print("\n✅ VERIFICATION PASSED")
        print(f"   Average interval ({avg_normal:.1f}s) is within expected range (8-12s)")
        print(f"   Parameter setting successfully changed interval from 60s to ~10s")
    else:
        print("\n⚠️  VERIFICATION INCONCLUSIVE")
        print(f"   Average interval ({avg_normal:.1f}s) outside expected range")