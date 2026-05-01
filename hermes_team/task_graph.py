from __future__ import annotations

import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .dispatcher import DispatchRequest, DispatchResult, TeamDispatcher


@dataclass
class TeamGraphNode:
    id: str
    role: str
    goal: str
    context: str = ''
    depends_on: list[str] = field(default_factory=list)
    toolsets: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamGraphResult:
    status: str
    results: list[DispatchResult]
    blocked_nodes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)
    parallel: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'results': [result.to_dict() for result in self.results],
            'blocked_nodes': self.blocked_nodes,
            'errors': self.errors,
            'execution_order': self.execution_order,
            'parallel': self.parallel,
        }


class TeamTaskGraph:
    def __init__(self, nodes: list[TeamGraphNode]) -> None:
        self.nodes = {node.id: node for node in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError('duplicate graph node id')
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        missing = []
        for node in self.nodes.values():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    missing.append(f'{node.id}->{dep}')
        if missing:
            raise ValueError('missing graph dependencies: ' + ', '.join(missing))
        self.topological_order()

    def topological_order(self) -> list[TeamGraphNode]:
        indegree = {node_id: 0 for node_id in self.nodes}
        children: dict[str, list[str]] = defaultdict(list)
        for node in self.nodes.values():
            for dep in node.depends_on:
                indegree[node.id] += 1
                children[dep].append(node.id)
        queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
        ordered: list[TeamGraphNode] = []
        while queue:
            node_id = queue.popleft()
            ordered.append(self.nodes[node_id])
            for child_id in children[node_id]:
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    queue.append(child_id)
        if len(ordered) != len(self.nodes):
            raise ValueError('graph contains a cycle')
        return ordered

    def execution_levels(self) -> list[list[TeamGraphNode]]:
        """Return dependency levels; nodes in the same level can run concurrently."""
        indegree = {node_id: 0 for node_id in self.nodes}
        children: dict[str, list[str]] = defaultdict(list)
        for node in self.nodes.values():
            for dep in node.depends_on:
                indegree[node.id] += 1
                children[dep].append(node.id)
        ready = [node_id for node_id, degree in indegree.items() if degree == 0]
        levels: list[list[TeamGraphNode]] = []
        processed = 0
        while ready:
            level_ids = list(ready)
            levels.append([self.nodes[node_id] for node_id in level_ids])
            processed += len(level_ids)
            next_ready: list[str] = []
            for node_id in level_ids:
                for child_id in children[node_id]:
                    indegree[child_id] -= 1
                    if indegree[child_id] == 0:
                        next_ready.append(child_id)
            ready = next_ready
        if processed != len(self.nodes):
            raise ValueError('graph contains a cycle')
        return levels


class TeamGraphRunner:
    def __init__(self, dispatcher: TeamDispatcher | None = None) -> None:
        self.dispatcher = dispatcher or TeamDispatcher()

    def run(
        self,
        graph: TeamTaskGraph,
        *,
        task_id: str,
        run_id: str,
        inherited_context: str = '',
        parallel: bool = False,
        max_concurrency: int | None = None,
    ) -> TeamGraphResult:
        if parallel:
            return self._run_parallel(
                graph,
                task_id=task_id,
                run_id=run_id,
                inherited_context=inherited_context,
                max_concurrency=max_concurrency,
            )
        return self._run_sequential(graph, task_id=task_id, run_id=run_id, inherited_context=inherited_context)

    def _run_sequential(self, graph: TeamTaskGraph, *, task_id: str, run_id: str, inherited_context: str = '') -> TeamGraphResult:
        completed: set[str] = set()
        failed: set[str] = set()
        results: list[DispatchResult] = []
        errors: list[str] = []
        execution_order: list[list[str]] = []
        for node in graph.topological_order():
            blocked_by = [dep for dep in node.depends_on if dep in failed]
            if blocked_by:
                failed.add(node.id)
                errors.append(f'{node.id} blocked by failed dependencies: {blocked_by}')
                continue
            execution_order.append([node.id])
            result = self.dispatcher.dispatch(self._request_for_node(node, task_id=task_id, run_id=run_id, inherited_context=inherited_context))
            results.append(result)
            if result.status == 'completed':
                completed.add(node.id)
            else:
                failed.add(node.id)
                errors.append(result.error or f'{node.id} {result.status}')
        status = 'completed' if len(completed) == len(graph.nodes) else 'failed'
        return TeamGraphResult(status=status, results=results, blocked_nodes=sorted(failed - completed), errors=errors, execution_order=execution_order)

    def _run_parallel(
        self,
        graph: TeamTaskGraph,
        *,
        task_id: str,
        run_id: str,
        inherited_context: str = '',
        max_concurrency: int | None = None,
    ) -> TeamGraphResult:
        completed: set[str] = set()
        failed: set[str] = set()
        results: list[DispatchResult] = []
        errors: list[str] = []
        execution_order: list[list[str]] = []
        max_concurrency = max(1, int(max_concurrency or 4))

        for level in graph.execution_levels():
            runnable: list[TeamGraphNode] = []
            for node in level:
                blocked_by = [dep for dep in node.depends_on if dep in failed]
                if blocked_by:
                    failed.add(node.id)
                    errors.append(f'{node.id} blocked by failed dependencies: {blocked_by}')
                else:
                    runnable.append(node)
            for chunk_start in range(0, len(runnable), max_concurrency):
                chunk = runnable[chunk_start:chunk_start + max_concurrency]
                if not chunk:
                    continue
                execution_order.append([node.id for node in chunk])
                chunk_results = self._dispatch_chunk(chunk, task_id=task_id, run_id=run_id, inherited_context=inherited_context)
                for node, result in chunk_results:
                    results.append(result)
                    if result.status == 'completed':
                        completed.add(node.id)
                    else:
                        failed.add(node.id)
                        errors.append(result.error or f'{node.id} {result.status}')
        status = 'completed' if len(completed) == len(graph.nodes) else 'failed'
        return TeamGraphResult(status=status, results=results, blocked_nodes=sorted(failed - completed), errors=errors, execution_order=execution_order, parallel=True)

    def _dispatch_chunk(
        self,
        nodes: list[TeamGraphNode],
        *,
        task_id: str,
        run_id: str,
        inherited_context: str,
    ) -> list[tuple[TeamGraphNode, DispatchResult]]:
        slots: list[tuple[TeamGraphNode, DispatchResult] | None] = [None] * len(nodes)

        def worker(index: int, node: TeamGraphNode) -> None:
            request = self._request_for_node(node, task_id=task_id, run_id=run_id, inherited_context=inherited_context)
            slots[index] = (node, self.dispatcher.dispatch(request))

        threads = [threading.Thread(target=worker, args=(index, node), daemon=True) for index, node in enumerate(nodes)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return [slot for slot in slots if slot is not None]

    @staticmethod
    def _request_for_node(node: TeamGraphNode, *, task_id: str, run_id: str, inherited_context: str) -> DispatchRequest:
        context = '\n\n'.join(part for part in [inherited_context, node.context] if part)
        return DispatchRequest(
            task_id=task_id,
            run_id=run_id,
            role=node.role,
            goal=node.goal,
            context=context,
            toolsets=node.toolsets,
            metadata=node.metadata | {'graph_node_id': node.id, 'depends_on': node.depends_on},
        )
