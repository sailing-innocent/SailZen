#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @file history_events_example.py
# @brief Example script to demonstrate History Events API usage
# @author sailing-innocent
# @date 2025-10-12
# @version 1.0
# ---------------------------------

import requests
import json
from datetime import datetime

# 配置API基础URL
BASE_URL = "http://localhost:4399/api/v1/history/event"


def print_response(title, response):
    """打印API响应"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    if response.status_code < 400:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")


def example_1_create_minimal_event():
    """示例1: 创建最小化事件（只有标题和描述）"""
    data = {
        "title": "测试事件",
        "description": "这是一个测试事件的描述"
    }
    response = requests.post(f"{BASE_URL}/", json=data)
    print_response("示例1: 创建最小化事件", response)
    return response.json().get('id') if response.status_code < 400 else None


def example_2_create_complete_event():
    """示例2: 创建完整的事件"""
    data = {
        "title": "中美从合作转向对抗",
        "description": "21世纪初至今，中美关系经历了从合作到竞争再到对抗的重大转变",
        "rar_tags": ["国际关系", "中美关系", "地缘政治"],
        "tags": ["international", "us-china", "geopolitics"],
        "start_time": "2010-01-01T00:00:00",
        "details": {
            "participants": ["中国", "美国"],
            "scope": "全球",
            "impact": "深远影响全球政治经济格局",
            "sources": ["新闻报道", "学术研究"]
        }
    }
    response = requests.post(f"{BASE_URL}/", json=data)
    print_response("示例2: 创建完整的事件", response)
    return response.json().get('id') if response.status_code < 400 else None


def example_3_create_child_event(parent_id):
    """示例3: 创建子事件"""
    data = {
        "title": "2025年关税战",
        "description": "2025年，中美贸易摩擦进一步升级，双方互征高额关税",
        "parent_event": parent_id,
        "rar_tags": ["贸易战", "关税"],
        "start_time": "2025-01-01T00:00:00",
        "end_time": "2025-12-31T23:59:59"
    }
    response = requests.post(f"{BASE_URL}/", json=data)
    print_response("示例3: 创建子事件", response)
    return response.json().get('id') if response.status_code < 400 else None


def example_4_create_detailed_event(parent_id):
    """示例4: 创建详细的具体事件"""
    data = {
        "title": "2025年10月11日 中方制裁稀土船舶，美方加征100%关税",
        "description": "2025年10月11日，中国宣布对稀土和相关船舶实施出口管制，美国随即宣布对中国商品加征100%关税作为回应",
        "parent_event": parent_id,
        "rar_tags": ["关税", "稀土", "制裁"],
        "tags": ["tariff", "rare-earth", "sanction"],
        "start_time": "2025-10-11T00:00:00",
        "end_time": "2025-10-11T23:59:59",
        "details": {
            "chinese_action": "对稀土和相关船舶实施出口管制",
            "us_action": "对中国商品加征100%关税",
            "impact": "全球供应链受到严重影响",
            "market_reaction": "股市波动加剧",
            "comments": "这是2025年最严重的贸易摩擦事件之一"
        }
    }
    response = requests.post(f"{BASE_URL}/", json=data)
    print_response("示例4: 创建详细的具体事件", response)
    return response.json().get('id') if response.status_code < 400 else None


def example_5_get_event(event_id):
    """示例5: 获取单个事件"""
    response = requests.get(f"{BASE_URL}/{event_id}")
    print_response(f"示例5: 获取事件 ID={event_id}", response)


def example_6_get_all_events():
    """示例6: 获取事件列表"""
    response = requests.get(f"{BASE_URL}?skip=0&limit=10")
    print_response("示例6: 获取事件列表", response)


def example_7_get_child_events(parent_id):
    """示例7: 获取子事件"""
    response = requests.get(f"{BASE_URL}/{parent_id}/children")
    print_response(f"示例7: 获取父事件 ID={parent_id} 的子事件", response)


def example_8_update_event(event_id):
    """示例8: 更新事件（补充信息）"""
    data = {
        "title": "测试事件（已更新）",
        "description": "这是更新后的描述",
        "rar_tags": ["测试", "更新"],
        "details": {
            "update_time": datetime.now().isoformat(),
            "update_reason": "补充详细信息"
        }
    }
    response = requests.put(f"{BASE_URL}/{event_id}", json=data)
    print_response(f"示例8: 更新事件 ID={event_id}", response)


def example_9_add_related_events(event_id, related_ids):
    """示例9: 添加相关事件"""
    # 先获取当前事件
    event = requests.get(f"{BASE_URL}/{event_id}").json()
    
    # 更新相关事件列表
    event['related_events'] = related_ids
    response = requests.put(f"{BASE_URL}/{event_id}", json=event)
    print_response(f"示例9: 为事件 ID={event_id} 添加相关事件", response)


def example_10_get_related_events(event_id):
    """示例10: 获取相关事件"""
    response = requests.get(f"{BASE_URL}/{event_id}/related")
    print_response(f"示例10: 获取事件 ID={event_id} 的相关事件", response)


def example_11_search_events(keyword):
    """示例11: 搜索事件"""
    response = requests.get(f"{BASE_URL}/search?keyword={keyword}&limit=5")
    print_response(f"示例11: 搜索关键词 '{keyword}'", response)


def example_12_filter_by_tags():
    """示例12: 按标签过滤"""
    response = requests.get(f"{BASE_URL}?tags=关税,贸易战&limit=10")
    print_response("示例12: 按标签过滤（关税,贸易战）", response)


def example_13_delete_event(event_id):
    """示例13: 删除事件"""
    response = requests.delete(f"{BASE_URL}/{event_id}")
    print_response(f"示例13: 删除事件 ID={event_id}", response)


def run_all_examples():
    """运行所有示例"""
    print("\n" + "="*60)
    print("History Events API 使用示例")
    print("="*60)
    
    # 创建事件
    print("\n【第一部分：创建事件】")
    event_id_1 = example_1_create_minimal_event()
    event_id_2 = example_2_create_complete_event()
    
    if not event_id_2:
        print("创建父事件失败，无法继续演示")
        return
    
    event_id_3 = example_3_create_child_event(event_id_2)
    
    if event_id_3:
        event_id_4 = example_4_create_detailed_event(event_id_3)
    
    # 查询事件
    print("\n【第二部分：查询事件】")
    if event_id_1:
        example_5_get_event(event_id_1)
    
    example_6_get_all_events()
    
    if event_id_2:
        example_7_get_child_events(event_id_2)
    
    # 更新事件
    print("\n【第三部分：更新事件】")
    if event_id_1:
        example_8_update_event(event_id_1)
    
    # 关联事件
    print("\n【第四部分：事件关联】")
    if event_id_1 and event_id_3:
        example_9_add_related_events(event_id_1, [event_id_3])
        example_10_get_related_events(event_id_1)
    
    # 搜索事件
    print("\n【第五部分：搜索事件】")
    example_11_search_events("关税")
    example_12_filter_by_tags()
    
    # 删除事件
    print("\n【第六部分：删除事件】")
    if event_id_1:
        example_13_delete_event(event_id_1)
    
    print("\n" + "="*60)
    print("所有示例执行完成！")
    print("="*60)


if __name__ == "__main__":
    try:
        run_all_examples()
    except requests.exceptions.ConnectionError:
        print("\n错误: 无法连接到服务器")
        print(f"请确保服务器正在运行: {BASE_URL}")
        print("可以使用以下命令启动服务器:")
        print("  python server.py --dev")
    except Exception as e:
        print(f"\n发生错误: {e}")

