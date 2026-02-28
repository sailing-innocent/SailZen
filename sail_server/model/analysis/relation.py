# -*- coding: utf-8 -*-
# @file relation.py
# @brief Relation Graph Business Logic
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

from typing import Dict, Any, List
from sqlalchemy.orm import Session

from sail_server.model.analysis.character import Character, CharacterRelation


def get_relation_graph_impl(db: Session, edition_id: int) -> Dict[str, Any]:
    """获取版本的关系图数据
    
    Args:
        db: 数据库会话
        edition_id: 版本ID
        
    Returns:
        关系图数据，包含 nodes 和 edges
    """
    # 获取该版本的所有人物
    characters = db.query(Character).filter(Character.edition_id == edition_id).all()
    
    # 构建节点列表
    nodes = []
    character_ids = set()
    for char in characters:
        character_ids.add(char.id)
        nodes.append({
            "id": f"character_{char.id}",
            "type": "character",
            "label": char.canonical_name,
            "data": {
                "id": char.id,
                "name": char.canonical_name,
                "role_type": char.role_type,
            }
        })
    
    # 获取人物之间的关系
    relations = db.query(CharacterRelation).filter(
        CharacterRelation.edition_id == edition_id
    ).all()
    
    # 构建边列表
    edges = []
    for rel in relations:
        # 只包含两个端点都在当前版本人物中的关系
        if rel.source_character_id in character_ids and rel.target_character_id in character_ids:
            edges.append({
                "id": f"relation_{rel.id}",
                "source": f"character_{rel.source_character_id}",
                "target": f"character_{rel.target_character_id}",
                "type": rel.relation_type,
                "label": rel.relation_type,
                "data": {
                    "id": rel.id,
                    "relation_type": rel.relation_type,
                    "description": rel.description,
                    "strength": rel.strength,
                }
            })
    
    return {
        "nodes": nodes,
        "edges": edges,
    }
