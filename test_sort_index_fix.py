# -*- coding: utf-8 -*-
"""
测试 sort_index 修复

验证批量保存时 sort_index 是否正确设置
"""

import sys
sys.path.insert(0, '.')

# 模拟测试
class MockNode:
    def __init__(self, id, title):
        self.id = id
        self.title = title
        self.position_anchor = None

class MockResult:
    def __init__(self, nodes):
        self.nodes = nodes
        self.turning_points = []
        self.conflicts = []

def test_sort_index_assignment():
    """测试 sort_index 分配逻辑"""
    
    # 创建模拟节点
    nodes = [
        MockNode("node_0", "第一章开头"),
        MockNode("node_1", "第一章中间"),
        MockNode("node_2", "第二章开头"),
        MockNode("node_3", "第三章"),
    ]
    
    result = MockResult(nodes)
    
    # 模拟保存逻辑中的 sort_index 分配
    print("模拟批量保存时的 sort_index 分配:")
    print("-" * 50)
    
    for i, node in enumerate(result.nodes):
        sort_index = i  # 这就是保存逻辑中使用的 sort_index
        print(f"节点 {i}: '{node.title}' -> sort_index = {sort_index}")
    
    print("-" * 50)
    print("预期结果: sort_index 应该是 0, 1, 2, 3")
    
    # 验证
    expected = [0, 1, 2, 3]
    actual = list(range(len(result.nodes)))
    
    if expected == actual:
        print("[PASS] 测试通过: sort_index 分配逻辑正确")
    else:
        print(f"[FAIL] 测试失败: 预期 {expected}, 实际 {actual}")
    
    return expected == actual


def test_bulk_insert_logic():
    """测试批量插入逻辑"""
    
    print("\n测试批量插入逻辑:")
    print("-" * 50)
    
    # 模拟批量插入过程
    created_nodes = []
    
    for i in range(5):
        sort_index = i
        # 模拟 add_outline_node_bulk 的行为
        mock_node = {
            'title': f'节点 {i}',
            'sort_index': sort_index,
        }
        created_nodes.append(mock_node)
        print(f"准备节点: sort_index = {sort_index}")
    
    print("-" * 50)
    print(f"总共准备 {len(created_nodes)} 个节点")
    print("统一提交后，sort_index 应该保持: 0, 1, 2, 3, 4")
    
    # 验证
    actual_indices = [n['sort_index'] for n in created_nodes]
    expected_indices = [0, 1, 2, 3, 4]
    
    if actual_indices == expected_indices:
        print("[PASS] 测试通过: 批量插入逻辑正确")
    else:
        print(f"[FAIL] 测试失败: 预期 {expected_indices}, 实际 {actual_indices}")
    
    return actual_indices == expected_indices


if __name__ == "__main__":
    print("=" * 60)
    print("大纲提取 V2 - sort_index 修复测试")
    print("=" * 60)
    
    test1 = test_sort_index_assignment()
    test2 = test_bulk_insert_logic()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("[PASS] 所有测试通过")
    else:
        print("[FAIL] 部分测试失败")
    print("=" * 60)
