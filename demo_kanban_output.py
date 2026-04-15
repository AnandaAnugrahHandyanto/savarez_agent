import json
from tools.epic_manager_tool import EpicManager
manager = EpicManager(verbose=False)
tasks = [
  {"id": "t1", "title": "DB Init", "description": "SQLite DB 생성", "depends_on": []},
  {"id": "t2", "title": "Add Func", "description": "할일 추가 기능", "depends_on": ["t1"]},
  {"id": "t3", "title": "CLI UI", "description": "터미널 인풋", "depends_on": ["t2"]}
]
print(manager._generate_kanban_text(tasks))
