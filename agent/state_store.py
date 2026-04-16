"""
Agent State Store - 状态持久化存储

基于Event驱动持久化设计，支持：
1. 状态变更作为delta原子写入
2. 完整历史追踪
3. 支持回溯和审计
4. 多存储后端（JSON/SQLite）
"""

import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


@dataclass
class StateDelta:
    """状态变更记录 - Event驱动持久化的核心数据结构"""
    agent_id: str
    schema_name: str
    timestamp: str  # ISO 8601格式
    from_state: Optional[str]
    to_state: str
    context: Dict[str, Any]  # 转移时的上下文数据
    metadata: Dict[str, Any]  # 附加元数据
    delta_id: str  # 唯一标识符


class StateStoreBackend(ABC):
    """状态存储后端抽象类"""

    @abstractmethod
    def save_state(self, agent_id: str, schema_name: str, state: str, context: Dict[str, Any] = None) -> bool:
        """保存当前状态"""
        pass

    @abstractmethod
    def get_state(self, agent_id: str, schema_name: str) -> Optional[str]:
        """获取当前状态"""
        pass

    @abstractmethod
    def get_context(self, agent_id: str, schema_name: str) -> Dict[str, Any]:
        """获取状态上下文"""
        pass

    @abstractmethod
    def save_delta(self, delta: StateDelta) -> bool:
        """保存状态变更记录"""
        pass

    @abstractmethod
    def get_history(self, agent_id: str, schema_name: str, limit: int = 100) -> List[StateDelta]:
        """获取状态变更历史"""
        pass

    @abstractmethod
    def delete_agent(self, agent_id: str) -> bool:
        """删除agent的所有状态数据"""
        pass

    @abstractmethod
    def cleanup_stale(self, timeout_seconds: int) -> int:
        """清理过期数据，返回清理数量"""
        pass


class JSONStateStore(StateStoreBackend):
    """JSON文件存储后端 - 简单可靠，适合小型部署"""

    def __init__(self, store_dir: Path = None):
        self.store_dir = store_dir or get_hermes_home() / "state_store"
        self.store_dir.mkdir(parents=True, exist_ok=True)

        # 状态文件路径
        self.states_file = self.store_dir / "states.json"
        self.history_dir = self.store_dir / "history"
        self.history_dir.mkdir(exist_ok=True)

        # 线程锁
        self._lock = threading.Lock()

        # 加载现有状态
        self._states: Dict[str, Dict[str, Any]] = {}
        self._load_states()

    def _load_states(self):
        """从文件加载现有状态"""
        if self.states_file.exists():
            try:
                with open(self.states_file, 'r', encoding='utf-8') as f:
                    self._states = json.load(f)
                logger.debug(f"从 {self.states_file} 加载了 {len(self._states)} 个状态")
            except Exception as e:
                logger.error(f"加载状态文件失败: {e}")
                self._states = {}

    def _save_states(self):
        """保存状态到文件"""
        try:
            with open(self.states_file, 'w', encoding='utf-8') as f:
                json.dump(self._states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")

    def _get_agent_key(self, agent_id: str, schema_name: str) -> str:
        """生成agent的唯一key"""
        return f"{agent_id}:{schema_name}"

    def save_state(self, agent_id: str, schema_name: str, state: str, context: Dict[str, Any] = None) -> bool:
        """保存当前状态"""
        with self._lock:
            key = self._get_agent_key(agent_id, schema_name)

            # 获取旧状态用于记录delta
            old_state = self._states.get(key, {}).get('state')

            # 更新状态
            self._states[key] = {
                'state': state,
                'context': context or {},
                'updated_at': datetime.utcnow().isoformat()
            }
            self._save_states()

            # 记录delta（如果状态有变化）
            if old_state != state:
                delta = StateDelta(
                    agent_id=agent_id,
                    schema_name=schema_name,
                    timestamp=datetime.utcnow().isoformat(),
                    from_state=old_state,
                    to_state=state,
                    context=context or {},
                    metadata={'source': 'save_state'},
                    delta_id=f"{agent_id}:{schema_name}:{datetime.utcnow().timestamp()}"
                )
                self.save_delta(delta)

            logger.debug(f"状态已保存: {key} -> {state}")
            return True

    def get_state(self, agent_id: str, schema_name: str) -> Optional[str]:
        """获取当前状态"""
        with self._lock:
            key = self._get_agent_key(agent_id, schema_name)
            data = self._states.get(key)
            return data['state'] if data else None

    def get_context(self, agent_id: str, schema_name: str) -> Dict[str, Any]:
        """获取状态上下文"""
        with self._lock:
            key = self._get_agent_key(agent_id, schema_name)
            data = self._states.get(key)
            return data.get('context', {}) if data else {}

    def save_delta(self, delta: StateDelta) -> bool:
        """保存状态变更记录"""
        try:
            # 使用agent_id作为子目录组织历史
            agent_dir = self.history_dir / delta.agent_id
            agent_dir.mkdir(exist_ok=True)

            # 保存delta到JSONL文件（增量追加）
            delta_file = agent_dir / f"{delta.schema_name}.jsonl"
            with open(delta_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(delta), ensure_ascii=False) + '\n')

            logger.debug(f"Delta已保存: {delta.agent_id} {delta.from_state} -> {delta.to_state}")
            return True
        except Exception as e:
            logger.error(f"保存delta失败: {e}")
            return False

    def get_history(self, agent_id: str, schema_name: str, limit: int = 100) -> List[StateDelta]:
        """获取状态变更历史"""
        delta_file = self.history_dir / agent_id / f"{schema_name}.jsonl"
        if not delta_file.exists():
            return []

        deltas = []
        try:
            with open(delta_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        deltas.append(StateDelta(**data))
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"读取历史记录失败: {e}")

        # 返回最近的N条记录
        return deltas[-limit:] if len(deltas) > limit else deltas

    def delete_agent(self, agent_id: str) -> bool:
        """删除agent的所有状态数据"""
        with self._lock:
            # 删除状态
            keys_to_delete = [k for k in self._states.keys() if k.startswith(f"{agent_id}:")]
            for key in keys_to_delete:
                del self._states[key]

            self._save_states()

            # 删除历史记录
            agent_dir = self.history_dir / agent_id
            if agent_dir.exists():
                import shutil
                shutil.rmtree(agent_dir)

            logger.info(f"Agent数据已删除: {agent_id}")
            return True

    def cleanup_stale(self, timeout_seconds: int) -> int:
        """清理过期数据，返回清理数量"""
        import time
        cutoff_time = datetime.utcnow().timestamp() - timeout_seconds

        cleaned = 0

        with self._lock:
            # 清理过期状态
            keys_to_delete = []
            for key, data in self._states.items():
                try:
                    updated_at = datetime.fromisoformat(data.get('updated_at', ''))
                    if updated_at.timestamp() < cutoff_time:
                        keys_to_delete.append(key)
                except Exception:
                    continue

            for key in keys_to_delete:
                del self._states[key]
                cleaned += 1

            if keys_to_delete:
                self._save_states()

            # 清理过期历史目录
            for agent_dir in self.history_dir.iterdir():
                if not agent_dir.is_dir():
                    continue
                try:
                    # 检查目录最后修改时间
                    if agent_dir.stat().st_mtime < cutoff_time:
                        import shutil
                        shutil.rmtree(agent_dir)
                        cleaned += 1
                except Exception as e:
                    logger.warning(f"清理历史目录失败 {agent_dir}: {e}")

        if cleaned > 0:
            logger.info(f"清理了 {cleaned} 个过期状态")
        return cleaned


class SQLiteStateStore(StateStoreBackend):
    """SQLite存储后端 - 更适合高并发和大量数据"""

    def __init__(self, db_path: Path = None):
        import sqlite3

        self.db_path = db_path or get_hermes_home() / "state_store.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        import sqlite3

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        cursor = self._conn.cursor()

        # 状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS states (
                agent_id TEXT NOT NULL,
                schema_name TEXT NOT NULL,
                state TEXT NOT NULL,
                context_json TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (agent_id, schema_name)
            )
        ''')

        # 历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                schema_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                context_json TEXT,
                metadata_json TEXT,
                delta_id TEXT NOT NULL
            )
        ''')

        # 索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_agent ON state_history(agent_id, schema_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_time ON state_history(timestamp)')

        self._conn.commit()
        logger.info(f"SQLite状态存储已初始化: {self.db_path}")

    def save_state(self, agent_id: str, schema_name: str, state: str, context: Dict[str, Any] = None) -> bool:
        """保存当前状态"""
        import sqlite3

        with self._lock:
            cursor = self._conn.cursor()

            # 获取旧状态
            cursor.execute(
                'SELECT state FROM states WHERE agent_id=? AND schema_name=?',
                (agent_id, schema_name)
            )
            row = cursor.fetchone()
            old_state = row[0] if row else None

            # 更新状态
            cursor.execute('''
                INSERT OR REPLACE INTO states (agent_id, schema_name, state, context_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                agent_id,
                schema_name,
                state,
                json.dumps(context or {}, ensure_ascii=False),
                datetime.utcnow().isoformat()
            ))

            self._conn.commit()

            # 记录delta
            if old_state != state:
                delta = StateDelta(
                    agent_id=agent_id,
                    schema_name=schema_name,
                    timestamp=datetime.utcnow().isoformat(),
                    from_state=old_state,
                    to_state=state,
                    context=context or {},
                    metadata={'source': 'save_state'},
                    delta_id=f"{agent_id}:{schema_name}:{datetime.utcnow().timestamp()}"
                )
                self.save_delta(delta)

            return True

    def get_state(self, agent_id: str, schema_name: str) -> Optional[str]:
        """获取当前状态"""
        import sqlite3

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                'SELECT state FROM states WHERE agent_id=? AND schema_name=?',
                (agent_id, schema_name)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_context(self, agent_id: str, schema_name: str) -> Dict[str, Any]:
        """获取状态上下文"""
        import sqlite3

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                'SELECT context_json FROM states WHERE agent_id=? AND schema_name=?',
                (agent_id, schema_name)
            )
            row = cursor.fetchone()
            return json.loads(row[0]) if row else {}

    def save_delta(self, delta: StateDelta) -> bool:
        """保存状态变更记录"""
        import sqlite3

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute('''
                INSERT INTO state_history
                (agent_id, schema_name, timestamp, from_state, to_state, context_json, metadata_json, delta_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                delta.agent_id,
                delta.schema_name,
                delta.timestamp,
                delta.from_state,
                delta.to_state,
                json.dumps(delta.context, ensure_ascii=False),
                json.dumps(delta.metadata, ensure_ascii=False),
                delta.delta_id
            ))
            self._conn.commit()
            return True

    def get_history(self, agent_id: str, schema_name: str, limit: int = 100) -> List[StateDelta]:
        """获取状态变更历史"""
        import sqlite3

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute('''
                SELECT agent_id, schema_name, timestamp, from_state, to_state,
                       context_json, metadata_json, delta_id
                FROM state_history
                WHERE agent_id=? AND schema_name=?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (agent_id, schema_name, limit))

            deltas = []
            for row in cursor.fetchall():
                deltas.append(StateDelta(
                    agent_id=row[0],
                    schema_name=row[1],
                    timestamp=row[2],
                    from_state=row[3],
                    to_state=row[4],
                    context=json.loads(row[5]),
                    metadata=json.loads(row[6]),
                    delta_id=row[7]
                ))
            return deltas

    def delete_agent(self, agent_id: str) -> bool:
        """删除agent的所有状态数据"""
        import sqlite3

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute('DELETE FROM states WHERE agent_id=?', (agent_id,))
            cursor.execute('DELETE FROM state_history WHERE agent_id=?', (agent_id,))
            self._conn.commit()
            logger.info(f"Agent数据已删除: {agent_id}")
            return True

    def cleanup_stale(self, timeout_seconds: int) -> int:
        """清理过期数据，返回清理数量"""
        import time
        import sqlite3

        cutoff_time = datetime.utcnow().isoformat()

        with self._lock:
            cursor = self._conn.cursor()

            # 删除过期状态
            cursor.execute('''
                DELETE FROM states
                WHERE datetime(updated_at) < datetime(?, '-{} seconds')
            ''', (cutoff_time, timeout_seconds))
            cleaned = cursor.rowcount

            # 删除过期历史
            cursor.execute('''
                DELETE FROM state_history
                WHERE datetime(timestamp) < datetime(?, '-{} seconds')
            ''', (cutoff_time, timeout_seconds))
            cleaned += cursor.rowcount

            self._conn.commit()

        if cleaned > 0:
            logger.info(f"清理了 {cleaned} 条过期记录")
        return cleaned


# =============================================================================
# 全局状态存储实例
# =============================================================================

# 默认使用JSON存储，可通过配置切换到SQLite
_default_store: Optional[StateStoreBackend] = None


def get_state_store(backend: str = "json") -> StateStoreBackend:
    """获取状态存储实例（单例）"""
    global _default_store

    if _default_store is None:
        if backend == "sqlite":
            _default_store = SQLiteStateStore()
        else:
            _default_store = JSONStateStore()

    return _default_store


def reset_state_store():
    """重置状态存储（主要用于测试）"""
    global _default_store
    _default_store = None
