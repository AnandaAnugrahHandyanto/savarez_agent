#!/usr/bin/env python3
"""
事故场景模拟器
基于JDBC Connection reset事故报告生成模拟的巡检数据
"""

import json


def generate_accident_scenario():
    """
    生成模拟的巡检数据
    
    Returns:
        dict: 模拟的巡检数据，包含Oracle和JVM检查结果
    """
    # 模拟Oracle检查数据
    oracle_data = {
        "service": "oracle",
        "timestamp": "2026-05-28T11:00:00Z",
        "status": "critical",
        "database": "MESDB",
        "checks": {
            "tablespace": [
                {
                    "name": "MES_DATA",
                    "status": "ok",
                    "size_mb": 51200,
                    "used_mb": 35840,
                    "usage_percent": 70.0,
                    "autoextend": True
                }
            ],
            "slow_sql": {
                "status": "ok",
                "count": 2,
                "threshold_seconds": 3,
                "top_sql": []
            },
            "lock_wait": {
                "status": "ok",
                "blocked_sessions": 0,
                "max_wait_seconds": 0,
                "details": []
            },
            "sessions": {
                "status": "critical",
                "active": 1400,
                "inactive": 50,
                "total": 1450,
                "max_sessions": 500,
                "usage_percent": 290.0
            },
            "archive_log": {
                "status": "ok",
                "used_percent": 45.0,
                "space_remaining_gb": 120.5
            }
        },
        "exit_code": 2
    }
    
    # 模拟JVM检查数据
    jvm_data = {
        "service": "jvm",
        "timestamp": "2026-05-28T11:00:00Z",
        "status": "critical",
        "application": "MES-App",
        "checks": {
            "thread_dump": {
                "status": "critical",
                "total_threads": 1450,
                "blocked_threads": 1400,
                "waiting_threads": 50,
                "runnable_threads": 0,
                "top_blocked_methods": [
                    {
                        "method": "java.net.InetAddress.getLocalHost",
                        "count": 1400,
                        "state": "BLOCKED"
                    }
                ]
            },
            "heap_memory": {
                "status": "ok",
                "used_mb": 2048,
                "max_mb": 4096,
                "usage_percent": 50.0
            },
            "gc_activity": {
                "status": "ok",
                "gc_count": 150,
                "gc_time_ms": 4500
            }
        },
        "exit_code": 2
    }
    
    # 模拟网络检查数据
    network_data = {
        "service": "network",
        "timestamp": "2026-05-28T11:00:00Z",
        "status": "critical",
        "checks": {
            "dns_resolution": {
                "status": "critical",
                "resolution_time_ms": 5000,
                "timeout_count": 1400,
                "error_message": "DNS resolution timeout"
            },
            "connection_reset": {
                "status": "critical",
                "error_type": "JDBC Connection reset",
                "count": 1400,
                "affected_nodes": "cluster-wide"
            }
        },
        "exit_code": 2
    }
    
    return {
        "oracle": oracle_data,
        "jvm": jvm_data,
        "network": network_data,
        "accident_summary": {
            "time": "2026-05-28 11:00",
            "scope": "集群大规模爆发（非单节点）",
            "symptom": "JDBC Connection reset",
            "trigger": "发布代码时触发",
            "history": "2026-05-26 15点曾发生单节点问题，原因为DNS服务器问题"
        }
    }


if __name__ == "__main__":
    # 测试生成的数据
    data = generate_accident_scenario()
    print(json.dumps(data, indent=2, ensure_ascii=False))
