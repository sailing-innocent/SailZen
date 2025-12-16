# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage
# @author sailing-innocent
# @date 2025-04-24
# @version 1.0
# ---------------------------------

from sail_server.data.health import Weight, WeightData
from datetime import datetime
from sqlalchemy import func
from sqlalchemy import func, cast, Float


def read_from_weight(weight: Weight):
    # print(f"Reading weight: {weight.htime.timestamp()}")
    # if weight is None:
    #     return None
    return WeightData(
        id=weight.id,
        value=weight.value,
        htime=weight.htime.timestamp(),
    )


def create_weight_impl(db, weight_create: WeightData):
    weight = Weight(
        value=weight_create.value,
        htime=datetime.fromtimestamp(weight_create.htime),
        tag=weight_create.tag,
        description=weight_create.description,
    )
    db.add(weight)
    db.commit()
    db.refresh(weight)
    return read_from_weight(weight)


def read_weight_impl(db, weight_record_id: int = -1, _tag: str = None):
    q = db.query(Weight)
    if _tag is not None:
        q = q.filter(Weight.tag == _tag)
    if weight_record_id != -1:
        q = q.filter(Weight.id == weight_record_id)
    weight = q.first()
    return read_from_weight(weight) if weight else None


def read_weights_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    start_time: float = None,  # timestamp in seconds
    end_time: float = None,  # timestamp in seconds
    _tag: str = "raw",
):
    query = db.query(Weight)
    if _tag is not None:
        query = query.filter(Weight.tag == _tag)
    if start_time != None:
        query = query.filter(Weight.htime >= datetime.fromtimestamp(start_time))
    if end_time != None:
        query = query.filter(Weight.htime <= datetime.fromtimestamp(end_time))
    weights = query.order_by(Weight.htime).offset(skip)
    if limit != -1:
        weights = weights.limit(limit)
    weights = weights.all()
    res = [read_from_weight(weight) for weight in weights]
    return res


def read_weights_avg_impl(
    db,
    start_time: float = None,  # timestamp in seconds
    end_time: float = None,  # timestamp in seconds
    _tag: str = "raw",
):
    query = db.query(func.avg(cast(Weight.value, Float)))
    if _tag is not None:
        query = query.filter(Weight.tag == _tag)
    if start_time != None:
        query = query.filter(Weight.htime >= datetime.fromtimestamp(start_time))
    if end_time != None:
        query = query.filter(Weight.htime <= datetime.fromtimestamp(end_time))

    return query.scalar()


def update_weight_impl(db, id, weight: WeightData):
    weight_rec = db.query(Weight).filter(Weight.id == id).first()
    if weight_rec is None:
        return None
    weight_rec.value = weight.value
    weight_rec.htime = datetime.fromtimestamp(weight.htime)
    weight_rec.tag = weight.tag
    weight_rec.description = weight.description
    db.commit()
    return read_weight_impl(db, id)


def delete_weight_impl(db, id=None):
    if id is not None:
        db.query(Weight).filter(Weight.id == id).delete()
    else:
        db.query(Weight).delete()
    db.commit()


def target_weight_impl(db, target_date: datetime):
    """
    Get the target weight for a specific date.
    """
    # hard-code here
    start_date = "2025-04-02"
    start_weight = 115.0
    # duration = 365 # one year
    duration = 270  # 9 months
    target_dec = 30  # 30kg in one year
    decay_rate = target_dec / duration

    # Linear Approximation for target weight
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if target_date < start_date:
        return None
    days_passed = (target_date - start_date).days
    target_weight = start_weight - decay_rate * days_passed
    return WeightData(
        id=-1,  # No ID for target weight
        value=target_weight,
        htime=-1,
        tag="target",
        description="Target weight based on linear approximation",
    )
