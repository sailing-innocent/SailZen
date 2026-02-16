from sail_server.utils.env import read_env

read_env("dev")
from sail_server.db import Database

db = Database.get_instance().get_db_session()
from sail_server.data.text import Work

work = db.query(Work).filter(Work.id == 8).first()
print(f"作品: {work.title}")
print(f"作者: {work.author}")
print(f"版本数: {len(work.editions)}")
for e in work.editions:
    print(f"  版本 {e.id}: {e.edition_name}, {e.char_count:,} 字")
db.close()
