# -*- coding: utf-8 -*-
# @file evidence.py
# @brief Text Evidence Management Business Logic
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    TextEvidenceData, AnalysisTaskData, AnalysisResultData,
)
from sail_server.data.analysis import TextEvidence as TextEvidenceORM
from sail_server.data.text import DocumentNode


# ============================================================================
# Text Evidence Operations
# ============================================================================

def add_text_evidence_impl(
    db: Session,
    edition_id: int,
    node_id: int,
    target_type: str,
    target_id: int,
    start_char: Optional[int] = None,
    end_char: Optional[int] = None,
    text_snippet: Optional[str] = None,
    context_before: Optional[str] = None,
    context_after: Optional[str] = None,
    evidence_type: str = "explicit",
    confidence: Optional[float] = None,
    source: str = "manual"
) -> TextEvidenceData:
    """添加文本证据"""
    evidence = TextEvidenceORM(
        edition_id=edition_id,
        node_id=node_id,
        target_type=target_type,
        target_id=target_id,
        start_char=start_char,
        end_char=end_char,
        text_snippet=text_snippet,
        context_before=context_before,
        context_after=context_after,
        evidence_type=evidence_type,
        confidence=confidence,
        source=source,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    
    return TextEvidenceData.read_from_orm(evidence)


def get_evidence_for_target_impl(
    db: Session, 
    target_type: str, 
    target_id: int
) -> List[TextEvidenceData]:
    """获取目标的所有证据"""
    evidences = db.query(TextEvidenceORM).filter(
        TextEvidenceORM.target_type == target_type,
        TextEvidenceORM.target_id == target_id
    ).order_by(TextEvidenceORM.node_id, TextEvidenceORM.start_char).all()
    
    return [TextEvidenceData.read_from_orm(e) for e in evidences]


def get_evidence_for_node_impl(db: Session, node_id: int) -> List[TextEvidenceData]:
    """获取章节的所有证据"""
    evidences = db.query(TextEvidenceORM).filter(
        TextEvidenceORM.node_id == node_id
    ).order_by(TextEvidenceORM.start_char).all()
    
    return [TextEvidenceData.read_from_orm(e) for e in evidences]


def delete_text_evidence_impl(db: Session, evidence_id: int) -> bool:
    """删除文本证据"""
    evidence = db.query(TextEvidenceORM).filter(TextEvidenceORM.id == evidence_id).first()
    if not evidence:
        return False
    
    db.delete(evidence)
    db.commit()
    return True


def get_chapter_annotations_impl(db: Session, node_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """获取章节的所有标注（按类型分组）"""
    evidences = db.query(TextEvidenceORM).filter(
        TextEvidenceORM.node_id == node_id
    ).order_by(TextEvidenceORM.start_char).all()
    
    result: Dict[str, List[Dict[str, Any]]] = {}
    
    for evidence in evidences:
        if evidence.target_type not in result:
            result[evidence.target_type] = []
        
        result[evidence.target_type].append({
            "id": evidence.id,
            "target_id": evidence.target_id,
            "start_char": evidence.start_char,
            "end_char": evidence.end_char,
            "text_snippet": evidence.text_snippet,
            "evidence_type": evidence.evidence_type,
            "confidence": float(evidence.confidence) if evidence.confidence else None,
        })
    
    return result


# ============================================================================
# Analysis Task Operations
# ============================================================================

def create_analysis_task_impl(db: Session, data: AnalysisTaskData) -> AnalysisTaskData:
    """创建分析任务"""
    task = data.create_orm()
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return AnalysisTaskData.read_from_orm(task)


def get_analysis_task_impl(db: Session, task_id: int) -> Optional[AnalysisTaskData]:
    """获取分析任务"""
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if not task:
        return None
    
    result_count = db.query(func.count(AnalysisResult.id)).filter(
        AnalysisResult.task_id == task_id
    ).scalar() or 0
    
    return AnalysisTaskData.read_from_orm(task, result_count)


def get_tasks_by_edition_impl(
    db: Session, 
    edition_id: int,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> List[AnalysisTaskData]:
    """获取版本的分析任务列表"""
    query = db.query(AnalysisTask).filter(AnalysisTask.edition_id == edition_id)
    
    if status:
        query = query.filter(AnalysisTask.status == status)
    
    if task_type:
        query = query.filter(AnalysisTask.task_type == task_type)
    
    tasks = query.order_by(AnalysisTask.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for task in tasks:
        result_count = db.query(func.count(AnalysisResult.id)).filter(
            AnalysisResult.task_id == task.id
        ).scalar() or 0
        result.append(AnalysisTaskData.read_from_orm(task, result_count))
    
    return result


def get_pending_tasks_impl(db: Session, limit: int = 10) -> List[AnalysisTaskData]:
    """获取待执行的任务"""
    tasks = db.query(AnalysisTask).filter(
        AnalysisTask.status == 'pending'
    ).order_by(AnalysisTask.priority.desc(), AnalysisTask.created_at).limit(limit).all()
    
    return [AnalysisTaskData.read_from_orm(task) for task in tasks]


def update_task_status_impl(
    db: Session, 
    task_id: int, 
    status: str,
    error_message: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None
) -> bool:
    """更新任务状态"""
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if not task:
        return False
    
    task.status = status
    
    if status == 'running':
        from datetime import datetime
        task.started_at = datetime.utcnow()
    elif status in ('completed', 'failed'):
        from datetime import datetime
        task.completed_at = datetime.utcnow()
    
    if error_message is not None:
        task.error_message = error_message
    
    if result_summary is not None:
        task.result_summary = result_summary
    
    db.commit()
    return True


def cancel_task_impl(db: Session, task_id: int) -> bool:
    """取消任务"""
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if not task:
        return False
    
    if task.status not in ('pending', 'running'):
        return False
    
    task.status = 'cancelled'
    db.commit()
    return True


# ============================================================================
# Analysis Result Operations
# ============================================================================

def save_analysis_results_impl(
    db: Session, 
    task_id: int, 
    results: List[Dict[str, Any]]
) -> List[AnalysisResultData]:
    """保存分析结果"""
    saved = []
    
    for result_data in results:
        result = AnalysisResult(
            task_id=task_id,
            result_type=result_data.get('result_type', 'unknown'),
            result_data=result_data.get('data', {}),
            confidence=result_data.get('confidence'),
        )
        db.add(result)
        db.flush()
        saved.append(AnalysisResultData.read_from_orm(result))
    
    db.commit()
    return saved


def get_task_results_impl(
    db: Session, 
    task_id: int,
    review_status: Optional[str] = None
) -> List[AnalysisResultData]:
    """获取任务的分析结果"""
    query = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id)
    
    if review_status:
        query = query.filter(AnalysisResult.review_status == review_status)
    
    results = query.order_by(AnalysisResult.created_at).all()
    
    return [AnalysisResultData.read_from_orm(r) for r in results]


def approve_result_impl(db: Session, result_id: int, reviewer: str) -> bool:
    """批准分析结果"""
    result = db.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
    if not result:
        return False
    
    from datetime import datetime
    result.review_status = 'approved'
    result.reviewer = reviewer
    result.reviewed_at = datetime.utcnow()
    
    db.commit()
    return True


def reject_result_impl(db: Session, result_id: int, reviewer: str, notes: Optional[str] = None) -> bool:
    """拒绝分析结果"""
    result = db.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
    if not result:
        return False
    
    from datetime import datetime
    result.review_status = 'rejected'
    result.reviewer = reviewer
    result.reviewed_at = datetime.utcnow()
    result.review_notes = notes
    
    db.commit()
    return True


def modify_result_impl(
    db: Session, 
    result_id: int, 
    modified_data: Dict[str, Any],
    reviewer: str
) -> Optional[AnalysisResultData]:
    """修改并应用分析结果"""
    result = db.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
    if not result:
        return None
    
    from datetime import datetime
    result.result_data = modified_data
    result.review_status = 'modified'
    result.reviewer = reviewer
    result.reviewed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(result)
    
    return AnalysisResultData.read_from_orm(result)


def apply_result_impl(db: Session, result_id: int) -> bool:
    """将结果应用到主表"""
    result = db.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
    if not result:
        return False
    
    if result.review_status not in ('approved', 'modified'):
        return False
    
    if result.applied:
        return False
    
    # TODO: 根据 result_type 将数据写入对应的主表
    # 这里需要根据具体的 result_type 实现不同的应用逻辑
    
    from datetime import datetime
    result.applied = True
    result.applied_at = datetime.utcnow()
    
    db.commit()
    return True


def apply_all_approved_impl(db: Session, task_id: int) -> Dict[str, int]:
    """批量应用所有已批准的结果"""
    results = db.query(AnalysisResult).filter(
        AnalysisResult.task_id == task_id,
        AnalysisResult.review_status.in_(['approved', 'modified']),
        AnalysisResult.applied == False
    ).all()
    
    applied_count = 0
    failed_count = 0
    
    for result in results:
        try:
            if apply_result_impl(db, result.id):
                applied_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1
    
    return {
        "applied": applied_count,
        "failed": failed_count,
        "total": len(results),
    }


# ============================================================================
# Statistics
# ============================================================================

def get_analysis_stats_impl(db: Session, edition_id: int) -> Dict[str, Any]:
    """获取分析统计信息"""
    # 任务统计
    task_stats = db.query(
        AnalysisTask.status,
        func.count(AnalysisTask.id)
    ).filter(
        AnalysisTask.edition_id == edition_id
    ).group_by(AnalysisTask.status).all()
    
    # 结果统计
    result_stats = db.query(
        AnalysisResult.review_status,
        func.count(AnalysisResult.id)
    ).join(AnalysisTask).filter(
        AnalysisTask.edition_id == edition_id
    ).group_by(AnalysisResult.review_status).all()
    
    # 证据统计
    evidence_stats = db.query(
        TextEvidenceORM.target_type,
        func.count(TextEvidenceORM.id)
    ).filter(
        TextEvidenceORM.edition_id == edition_id
    ).group_by(TextEvidenceORM.target_type).all()
    
    return {
        "tasks": {s[0]: s[1] for s in task_stats},
        "results": {s[0]: s[1] for s in result_stats},
        "evidence": {s[0]: s[1] for s in evidence_stats},
    }
