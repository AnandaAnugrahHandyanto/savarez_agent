class MemoryManager:
    """记忆管理器 - 修复版"""
    
    def __init__(self):
        self._providers = []
        self._initialized = False

    def add_provider(self, provider):
        if len(self._providers) >= 2:
            raise RuntimeError("最多只能添加2个提供者")
        if not hasattr(provider, "initialize"):
            raise TypeError("provider must implement initialize()")
        self._providers.append(provider)

    def initialize_all(self, **kwargs):
        try:
            for provider in self._providers:
                provider.initialize(**kwargs)
            self._initialized = True
        except Exception:
            self._initialized = False
            raise

    def has_tool(self, name):
        return any(callable(getattr(p, name, None)) for p in self._providers)
