from internal.data.life import (
    ServiceAccount,
)
from pydantic import BaseModel

# ------------------------------------------------
# Service Account
# ------------------------------------------------


class ServiceAccountCreate(BaseModel):
    name: str
    entry: str
    username: str
    password: str
    desp: str
    expire_time: int


class ServiceAccountRead(BaseModel):
    id: int
    name: str
    entry: str
    username: str
    password: str
    desp: str
    expire_time: int


def service_account_from_create(create: ServiceAccountCreate):
    return ServiceAccount(
        name=create.name,
        entry=create.entry,
        username=create.username,
        password=create.password,
        desp=create.desp,
        expire_time=create.expire_time,
    )


def read_from_service_account(service_account: ServiceAccount):
    return ServiceAccountRead(
        id=service_account.id,
        name=service_account.name,
        entry=service_account.entry,
        username=service_account.username,
        password=service_account.password,
        desp=service_account.desp,
        expire_time=service_account.expire_time,
    )


def create_service_account_impl(db, service_account_create: ServiceAccountCreate):
    service_account = service_account_from_create(service_account_create)
    db.add(service_account)
    db.commit()
    return read_from_service_account(service_account)


def get_service_account_impl(db, service_account_id: int):
    service_account = (
        db.query(ServiceAccount).filter(ServiceAccount.id == service_account_id).first()
    )
    return read_from_service_account(service_account)


def query_service_account_by_name_impl(db, name: str):
    service_account = (
        db.query(ServiceAccount).filter(ServiceAccount.name == name).first()
    )
    return read_from_service_account(service_account)


def get_service_accounts_impl(db, skip: int = 0, limit: int = -1):
    query = db.query(ServiceAccount)
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    service_accounts = query.all()
    return [
        read_from_service_account(service_account)
        for service_account in service_accounts
    ]


def update_service_account_impl(
    db, service_account_id: int, service_account_update: ServiceAccountCreate
):
    service_account = (
        db.query(ServiceAccount).filter(ServiceAccount.id == service_account_id).first()
    )
    service_account.name = service_account_update.name
    service_account.entry = service_account_update.entry
    service_account.username = service_account_update.username
    service_account.password = service_account_update.password
    service_account.desp = service_account_update.desp
    service_account.expire_time = service_account_update.expire_time
    db.commit()
    return read_from_service_account(service_account)


def delete_service_account_impl(db, service_account_id: int):
    service_account = (
        db.query(ServiceAccount).filter(ServiceAccount.id == service_account_id).first()
    )
    db.delete(service_account)
    db.commit()
    return read_from_service_account(service_account)
