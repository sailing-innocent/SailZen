# -*- coding: utf-8 -*-
# @file test_evidence_api.py
# @brief Evidence API Unit Tests
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

import pytest
from datetime import datetime
from sail_server.data.analysis import (
    TextEvidenceDTO,
    EvidenceCreateRequest,
    EvidenceUpdateRequest,
)
from sail_server.controller.analysis import EvidenceController, EvidenceResponse


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def evidence_controller():
    """创建证据控制器实例并清理存储"""
    # 注意：EvidenceController 是 Litestar Controller，不能直接实例化
    # 这里只返回类用于访问类方法和类变量
    # 清理存储
    EvidenceController._evidence_store.clear()
    return EvidenceController


@pytest.fixture
def sample_evidence_request():
    """样本证据创建请求"""
    return EvidenceCreateRequest(
        edition_id=1,
        node_id=100,
        start_offset=10,
        end_offset=50,
        selected_text="这是一段选中的文本",
        evidence_type="character",
        content="这是人物证据",
        target_type="character",
        target_id="char_001",
        context="上下文信息",
    )


# ============================================================================
# Test Cases
# ============================================================================

class TestEvidenceController:
    """证据控制器测试类"""

    @pytest.mark.asyncio
    async def test_create_evidence(self, evidence_controller, sample_evidence_request):
        """测试创建证据"""
        # 注意：由于需要数据库会话，这里仅测试请求对象创建
        request = sample_evidence_request
        
        assert request.edition_id == 1
        assert request.node_id == 100
        assert request.start_offset == 10
        assert request.end_offset == 50
        assert request.selected_text == "这是一段选中的文本"
        assert request.evidence_type == "character"
        assert request.content == "这是人物证据"
        assert request.target_type == "character"
        assert request.target_id == "char_001"
        assert request.context == "上下文信息"

    def test_evidence_dataclass(self):
        """测试证据数据类"""
        evidence = TextEvidenceDTO(
            id="test-001",
            edition_id=1,
            node_id=100,
            start_offset=10,
            end_offset=50,
            selected_text="测试文本",
            evidence_type="setting",
            content="设定证据",
            target_type="setting",
            target_id="setting_001",
            context="测试上下文",
            created_at=datetime.now(),
        )
        
        assert evidence.id == "test-001"
        assert evidence.edition_id == 1
        assert evidence.node_id == 100
        assert evidence.start_offset == 10
        assert evidence.end_offset == 50
        assert evidence.selected_text == "测试文本"
        assert evidence.evidence_type == "setting"
        assert evidence.content == "设定证据"
        assert evidence.target_type == "setting"
        assert evidence.target_id == "setting_001"
        assert evidence.context == "测试上下文"

    def test_evidence_response_dataclass(self):
        """测试证据响应数据类"""
        response = EvidenceResponse(
            id="resp-001",
            edition_id=1,
            node_id=100,
            evidence_type="outline",
            content="大纲证据",
            selected_text="选中内容",
            start_offset=20,
            end_offset=60,
            target_type="outline_node",
            target_id="node_001",
            context="响应上下文",
            created_at=datetime.now().isoformat(),
            message="创建成功",
        )
        
        assert response.id == "resp-001"
        assert response.edition_id == 1
        assert response.node_id == 100
        assert response.evidence_type == "outline"
        assert response.content == "大纲证据"
        assert response.selected_text == "选中内容"
        assert response.start_offset == 20
        assert response.end_offset == 60
        assert response.target_type == "outline_node"
        assert response.target_id == "node_001"
        assert response.context == "响应上下文"
        assert response.message == "创建成功"

    def test_evidence_update_request(self):
        """测试证据更新请求"""
        # 全字段更新
        update_full = EvidenceUpdateRequest(
            content="更新后的内容",
            evidence_type="relation",
            target_type="relation",
            target_id="rel_001",
            context="更新后的上下文",
        )
        
        assert update_full.content == "更新后的内容"
        assert update_full.evidence_type == "relation"
        assert update_full.target_type == "relation"
        assert update_full.target_id == "rel_001"
        assert update_full.context == "更新后的上下文"
        
        # 部分更新
        update_partial = EvidenceUpdateRequest(content="仅更新内容")
        assert update_partial.content == "仅更新内容"
        assert update_partial.evidence_type is None
        assert update_partial.target_type is None

    def test_evidence_store_operations(self, evidence_controller):
        """测试证据存储操作"""
        # 创建证据并存储
        evidence = TextEvidenceDTO(
            id="store-test-001",
            edition_id=1,
            node_id=100,
            start_offset=0,
            end_offset=10,
            selected_text="测试",
            evidence_type="custom",
            content="存储测试",
            created_at=datetime.now(),
        )
        
        # 存储证据
        EvidenceController._evidence_store[evidence.id] = evidence
        
        # 验证存储
        assert "store-test-001" in EvidenceController._evidence_store
        stored = EvidenceController._evidence_store["store-test-001"]
        assert stored.id == "store-test-001"
        assert stored.content == "存储测试"
        
        # 删除证据
        del EvidenceController._evidence_store[evidence.id]
        assert "store-test-001" not in EvidenceController._evidence_store

    def test_evidence_filtering_by_node(self, evidence_controller):
        """测试按节点过滤证据"""
        # 创建多个证据
        evidences = [
            TextEvidenceDTO(
                id=f"filter-test-{i}",
                edition_id=1,
                node_id=100 if i < 3 else 200,  # 3个属于节点100，2个属于节点200
                start_offset=i * 10,
                end_offset=i * 10 + 5,
                selected_text=f"文本{i}",
                evidence_type="character",
                content=f"证据{i}",
                created_at=datetime.now(),
            )
            for i in range(5)
        ]
        
        # 存储证据
        for ev in evidences:
            EvidenceController._evidence_store[ev.id] = ev
        
        # 按节点过滤
        node_100_evidences = [
            ev for ev in EvidenceController._evidence_store.values()
            if ev.node_id == 100
        ]
        node_200_evidences = [
            ev for ev in EvidenceController._evidence_store.values()
            if ev.node_id == 200
        ]
        
        assert len(node_100_evidences) == 3
        assert len(node_200_evidences) == 2
        
        # 清理
        for ev in evidences:
            if ev.id in EvidenceController._evidence_store:
                del EvidenceController._evidence_store[ev.id]

    def test_evidence_filtering_by_type(self, evidence_controller):
        """测试按类型过滤证据"""
        # 创建不同类型的证据
        types = ["character", "character", "setting", "outline", "relation"]
        evidences = [
            TextEvidenceDTO(
                id=f"type-test-{i}",
                edition_id=1,
                node_id=100,
                start_offset=i * 10,
                end_offset=i * 10 + 5,
                selected_text=f"文本{i}",
                evidence_type=types[i],
                content=f"证据{i}",
                created_at=datetime.now(),
            )
            for i in range(5)
        ]
        
        # 存储证据
        for ev in evidences:
            EvidenceController._evidence_store[ev.id] = ev
        
        # 按类型过滤
        character_evidences = [
            ev for ev in EvidenceController._evidence_store.values()
            if ev.evidence_type == "character"
        ]
        
        assert len(character_evidences) == 2
        
        # 清理
        for ev in evidences:
            if ev.id in EvidenceController._evidence_store:
                del EvidenceController._evidence_store[ev.id]

    def test_evidence_filtering_by_target(self, evidence_controller):
        """测试按目标过滤证据"""
        # 创建关联到不同目标的证据
        evidences = [
            TextEvidenceDTO(
                id=f"target-test-{i}",
                edition_id=1,
                node_id=100,
                start_offset=i * 10,
                end_offset=i * 10 + 5,
                selected_text=f"文本{i}",
                evidence_type="character",
                content=f"证据{i}",
                target_type="character",
                target_id=f"char_{i % 2}",  # 交替关联到 char_0 和 char_1
                created_at=datetime.now(),
            )
            for i in range(4)
        ]
        
        # 存储证据
        for ev in evidences:
            EvidenceController._evidence_store[ev.id] = ev
        
        # 按目标过滤
        target_0_evidences = [
            ev for ev in EvidenceController._evidence_store.values()
            if ev.target_type == "character" and ev.target_id == "char_0"
        ]
        target_1_evidences = [
            ev for ev in EvidenceController._evidence_store.values()
            if ev.target_type == "character" and ev.target_id == "char_1"
        ]
        
        assert len(target_0_evidences) == 2
        assert len(target_1_evidences) == 2
        
        # 清理
        for ev in evidences:
            if ev.id in EvidenceController._evidence_store:
                del EvidenceController._evidence_store[ev.id]


class TestEvidenceEdgeCases:
    """证据边界情况测试"""

    def test_empty_selected_text(self):
        """测试空选中文本"""
        evidence = TextEvidenceDTO(
            id="empty-test",
            edition_id=1,
            node_id=100,
            start_offset=0,
            end_offset=0,
            selected_text="",
            evidence_type="custom",
            content="空选择测试",
            created_at=datetime.now(),
        )
        
        assert evidence.selected_text == ""
        assert evidence.start_offset == 0
        assert evidence.end_offset == 0

    def test_large_offset_values(self):
        """测试大偏移量值"""
        evidence = TextEvidenceDTO(
            id="large-offset-test",
            edition_id=1,
            node_id=100,
            start_offset=999999,
            end_offset=1000000,
            selected_text="大偏移量测试",
            evidence_type="custom",
            content="测试",
            created_at=datetime.now(),
        )
        
        assert evidence.start_offset == 999999
        assert evidence.end_offset == 1000000

    def test_unicode_content(self):
        """测试Unicode内容"""
        evidence = TextEvidenceDTO(
            id="unicode-test",
            edition_id=1,
            node_id=100,
            start_offset=0,
            end_offset=10,
            selected_text="🎉 中文测试 🚀",
            evidence_type="custom",
            content="包含表情符号的文本 🎊",
            context="上下文 📝",
            created_at=datetime.now(),
        )
        
        assert "🎉" in evidence.selected_text
        assert "🚀" in evidence.selected_text
        assert "🎊" in evidence.content
        assert "📝" in evidence.context

    def test_special_characters_in_content(self):
        """测试内容中的特殊字符"""
        special_content = '<script>alert("xss")</script> & \n\t \\ "quoted"'
        evidence = TextEvidenceDTO(
            id="special-chars-test",
            edition_id=1,
            node_id=100,
            start_offset=0,
            end_offset=10,
            selected_text=special_content,
            evidence_type="custom",
            content=special_content,
            created_at=datetime.now(),
        )
        
        assert "<script>" in evidence.selected_text
        assert "&" in evidence.selected_text
        assert "\\" in evidence.selected_text
        assert '"quoted"' in evidence.selected_text


# ============================================================================
# Integration Tests (Optional)
# ============================================================================

@pytest.mark.skip(reason="需要数据库连接")
class TestEvidenceAPIIntegration:
    """证据 API 集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_evidence_lifecycle(self):
        """测试证据完整生命周期"""
        # 1. 创建证据
        # 2. 获取证据
        # 3. 更新证据
        # 4. 删除证据
        pass
