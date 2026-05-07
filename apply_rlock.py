#!/usr/bin/env python3
"""Apply RLock thread safety to memory_manager.py + add concurrency tests.
Runs on a clean upstream/main checkout for fix/memory-manager-thread-safety branch.
"""
import sys

# --- 1. Patch memory_manager.py ---
filepath = 'agent/memory_manager.py'
with open(filepath) as f:
    content = f.read()

# Add threading import
content = content.replace(
    'import inspect\nfrom typing import Any, Dict, List, Optional',
    'import inspect\nimport threading\nfrom typing import Any, Dict, List, Optional',
    1
)

# Add self._lock to __init__
content = content.replace(
    '        self._has_external: bool = False  # True once a non-builtin provider is added\n\n    # -- Registration',
    '        self._has_external: bool = False  # True once a non-builtin provider is added\n        self._lock = threading.RLock()\n\n    # -- Registration',
    1
)

# Wrap add_provider body in with self._lock:
old = '''        is_builtin = provider.name == "builtin"

        if not is_builtin:
            if self._has_external:
                existing = next(
                    (p.name for p in self._providers if p.name != "builtin"), "unknown"
                )
                logger.warning(
                    "Rejected memory provider '%s' — external provider '%s' is "
                    "already registered. Only one external memory provider is "
                    "allowed at a time. Configure which one via memory.provider "
                    "in config.yaml.",
                    provider.name, existing,
                )
                return
            self._has_external = True

        self._providers.append(provider)

        # Index tool names → provider for routing
        for schema in provider.get_tool_schemas():
            tool_name = schema.get("name", "")
            if tool_name and tool_name not in self._tool_to_provider:
                self._tool_to_provider[tool_name] = provider
            elif tool_name in self._tool_to_provider:
                logger.warning(
                    "Memory tool name conflict: '%s' already registered by %s, "
                    "ignoring from %s",
                    tool_name,
                    self._tool_to_provider[tool_name].name,
                    provider.name,
                )

        logger.info(
            "Memory provider '%s' registered (%d tools)",
            provider.name,
            len(provider.get_tool_schemas()),
        )'''

new = '''        with self._lock:
            is_builtin = provider.name == "builtin"

            if not is_builtin:
                if self._has_external:
                    existing = next(
                        (p.name for p in self._providers if p.name != "builtin"), "unknown"
                    )
                    logger.warning(
                        "Rejected memory provider '%s' — external provider '%s' is "
                        "already registered. Only one external memory provider is "
                        "allowed at a time. Configure which one via memory.provider "
                        "in config.yaml.",
                        provider.name, existing,
                    )
                    return
                self._has_external = True

            self._providers.append(provider)

            # Index tool names → provider for routing
            for schema in provider.get_tool_schemas():
                tool_name = schema.get("name", "")
                if tool_name and tool_name not in self._tool_to_provider:
                    self._tool_to_provider[tool_name] = provider
                elif tool_name in self._tool_to_provider:
                    logger.warning(
                        "Memory tool name conflict: '%s' already registered by %s, "
                        "ignoring from %s",
                        tool_name,
                        self._tool_to_provider[tool_name].name,
                        provider.name,
                    )

            logger.info(
                "Memory provider '%s' registered (%d tools)",
                provider.name,
                len(provider.get_tool_schemas()),
            )'''

if old not in content:
    print("ERROR: add_provider body not found")
    sys.exit(1)
content = content.replace(old, new, 1)

with open(filepath, 'w') as f:
    f.write(content)

# Verify syntax
import py_compile
py_compile.compile(filepath, doraise=True)
print("memory_manager.py: OK")

# --- 2. Add concurrency tests to test file ---
testfile = 'tests/agent/test_memory_provider.py'
with open(testfile) as f:
    tcontent = f.read()

test_block = '''


class TestMemoryManagerConcurrency:
    """Thread-safety tests for MemoryManager."""

    def test_concurrent_add_same_provider(self):
        """Multiple threads adding the same builtin provider should not corrupt state."""
        import threading
        mgr = MemoryManager()
        builtin = FakeMemoryProvider("builtin", tools=[
            {"name": "builtin_tool", "description": "Tool", "parameters": {}},
        ])

        def adder():
            mgr.add_provider(builtin)

        threads = [threading.Thread(target=adder) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(mgr.providers) >= 1
        assert mgr.providers[0].name == "builtin"
        assert mgr.has_tool("builtin_tool")

    def test_concurrent_add_builtin_and_external(self):
        """Concurrent builtin + external registration should both succeed."""
        import threading
        mgr = MemoryManager()
        builtin = FakeMemoryProvider("builtin", tools=[
            {"name": "builtin_tool", "description": "Builtin", "parameters": {}},
        ])
        ext = FakeMemoryProvider("ext", tools=[
            {"name": "ext_tool", "description": "External", "parameters": {}},
        ])

        results = []
        def add_builtin():
            try:
                mgr.add_provider(builtin)
                results.append("builtin_ok")
            except Exception as e:
                results.append(("builtin_err", str(e)))

        def add_ext():
            try:
                mgr.add_provider(ext)
                results.append("ext_ok")
            except Exception as e:
                results.append(("ext_err", str(e)))

        threads = [threading.Thread(target=add_builtin),
                   threading.Thread(target=add_ext)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert "builtin_ok" in results
        assert "ext_ok" in results
        assert len(mgr.providers) >= 2
        assert mgr.has_tool("builtin_tool")
        assert mgr.has_tool("ext_tool")

    def test_concurrent_tool_routing_while_adding(self):
        """Tool calls during provider addition should not crash."""
        import threading
        mgr = MemoryManager()
        builtin = FakeMemoryProvider("builtin", tools=[
            {"name": "builtin_tool", "description": "Builtin", "parameters": {}},
        ])
        mgr.add_provider(builtin)

        ext = FakeMemoryProvider("ext", tools=[
            {"name": "ext_tool", "description": "External", "parameters": {}},
        ])

        results = []
        def router():
            try:
                result = mgr.handle_tool_call("builtin_tool", {})
                results.append(("ok", result))
            except Exception as e:
                results.append(("err", str(e)))

        threads = [threading.Thread(target=router) for _ in range(20)]
        threads.append(threading.Thread(target=mgr.add_provider, args=(ext,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        errors = [r for r in results if r[0] == "err"]
        assert len(errors) == 0, f"Concurrent routing errors: {errors}"
        assert mgr.has_tool("ext_tool")

    def test_concurrent_handle_tool_call(self):
        """Multiple threads routing tool calls concurrently should not crash."""
        import threading
        mgr = MemoryManager()
        builtin = FakeMemoryProvider("builtin", tools=[
            {"name": "builtin_tool", "description": "Builtin", "parameters": {}},
        ])
        ext = FakeMemoryProvider("ext", tools=[
            {"name": "ext_tool", "description": "External", "parameters": {}},
        ])
        mgr.add_provider(builtin)
        mgr.add_provider(ext)

        results = []
        def route_builtin():
            try:
                r = mgr.handle_tool_call("builtin_tool", {"key": "val"})
                results.append("ok")
            except Exception as e:
                results.append(("err", str(e)))

        def route_ext():
            try:
                r = mgr.handle_tool_call("ext_tool", {"key": "val"})
                results.append("ok")
            except Exception as e:
                results.append(("err", str(e)))

        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=route_builtin))
            threads.append(threading.Thread(target=route_ext))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        errors = [r for r in results if isinstance(r, tuple) and r[0] == "err"]
        assert len(errors) == 0, f"Concurrent routing errors: {errors}"
        assert len(results) == 20


'''

marker = '\n\nclass TestPluginMemoryDiscovery:'
if marker not in tcontent:
    print("ERROR: insertion marker not found in test file")
    sys.exit(1)

tcontent = tcontent.replace(marker, test_block + marker, 1)
with open(testfile, 'w') as f:
    f.write(tcontent)

print("test_memory_provider.py: OK — concurrency tests added")
