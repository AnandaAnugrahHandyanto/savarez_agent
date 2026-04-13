import warnings
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class BaseConfigModel(BaseModel):
    """
    Shim to provide dict-like access for backward compatibility.
    Allows config["key"] and config.get("key") during refactoring.
    """
    model_config = {
        "extra": "ignore"  # Ignore stale config entries from user config.yaml without throwing
    }
    
    def _resolve_aliases(self, key: str) -> str:
        for field_name, field in self.__class__.model_fields.items():
            if field.alias == key:
                return field_name
        return key

    def get(self, key: str, default: Any = None) -> Any:
        key = self._resolve_aliases(key)
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def __getitem__(self, key: str) -> Any:
        key = self._resolve_aliases(key)
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def keys(self) -> Any:
        return self.model_dump().keys()

    def values(self) -> Any:
        return self.model_dump().values()

    def items(self) -> Any:
        return self.model_dump().items()

    def pop(self, key: str, default: Any = None) -> Any:
        key = self._resolve_aliases(key)
        if hasattr(self, key):
            val = getattr(self, key)
            setattr(self, key, default)
            return val
        return default

    def update(self, other: Dict[str, Any]) -> None:
        for k, v in other.items():
            self.__setitem__(k, v)

class AgentConfig(BaseConfigModel):
    max_turns: int = Field(default=90)
    gateway_timeout: int = Field(default=1800)
    tool_use_enforcement: Union[str, bool, List[str]] = Field(default="auto")
    gateway_timeout_warning: int = Field(default=900)

class KnowledgeConfig(BaseConfigModel):
    vault_path: str = Field(default="")
    wiki_path: str = Field(default="")
    agent_prefix: str = Field(default="Hermes")
    sync_episodes: bool = Field(default=False)
    sync_interval: int = Field(default=3600)

class TerminalConfig(BaseConfigModel):
    backend: str = Field(default="local")
    modal_mode: str = Field(default="auto")
    cwd: str = Field(default=".")
    timeout: int = Field(default=180)
    env_passthrough: List[str] = Field(default_factory=list)
    docker_image: str = Field(default="nikolaik/python-nodejs:python3.11-nodejs20")
    docker_forward_env: List[str] = Field(default_factory=list)
    singularity_image: str = Field(default="docker://nikolaik/python-nodejs:python3.11-nodejs20")
    modal_image: str = Field(default="nikolaik/python-nodejs:python3.11-nodejs20")
    daytona_image: str = Field(default="nikolaik/python-nodejs:python3.11-nodejs20")
    container_cpu: int = Field(default=1)
    container_memory: int = Field(default=5120)
    container_disk: int = Field(default=51200)
    container_persistent: bool = Field(default=True)
    docker_volumes: List[str] = Field(default_factory=list)
    docker_mount_cwd_to_workspace: bool = Field(default=False)
    persistent_shell: bool = Field(default=True)

class CamofoxConfig(BaseConfigModel):
    managed_persistence: bool = Field(default=False)

class BrowserConfig(BaseConfigModel):
    inactivity_timeout: int = Field(default=120)
    command_timeout: int = Field(default=30)
    record_sessions: bool = Field(default=False)
    allow_private_urls: bool = Field(default=False)
    camofox: CamofoxConfig = Field(default_factory=CamofoxConfig)

class CheckpointsConfig(BaseConfigModel):
    enabled: bool = Field(default=True)
    max_snapshots: int = Field(default=50)

class CouncilConfig(BaseConfigModel):
    enabled: bool = Field(default=True)
    default_depth: str = Field(default="quick")
    reviewer_model: Optional[str] = Field(default=None)
    chairman_model: Optional[str] = Field(default=None)
    skip_for_trivial: bool = Field(default=True)
    trivial_keywords: List[str] = Field(default_factory=lambda: [
        "weather", "time", "calculator", "hello", "thanks",
    ])

class CompressionConfig(BaseConfigModel):
    enabled: bool = Field(default=True)
    threshold: float = Field(default=0.50)
    target_ratio: float = Field(default=0.20)
    protect_last_n: int = Field(default=20)
    summary_model: str = Field(default="")
    summary_provider: str = Field(default="auto")
    summary_base_url: Optional[str] = Field(default=None)

class SmartModelRoutingCheapModelConfig(BaseConfigModel):
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)

class SmartModelRoutingConfig(BaseConfigModel):
    enabled: bool = Field(default=False)
    max_simple_chars: int = Field(default=160)
    max_simple_words: int = Field(default=28)
    cheap_model: Union[Dict[str, Any], SmartModelRoutingCheapModelConfig] = Field(default_factory=dict)

class ProviderModelConfig(BaseConfigModel):
    provider: str = Field(default="auto")
    model: str = Field(default="")
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    timeout: int = Field(default=30)
    download_timeout: Optional[int] = Field(default=None)

class AuxiliaryConfig(BaseConfigModel):
    vision: ProviderModelConfig = Field(
        default_factory=lambda: ProviderModelConfig(timeout=30, download_timeout=30)
    )
    web_extract: ProviderModelConfig = Field(
        default_factory=lambda: ProviderModelConfig(timeout=360)
    )
    compression: ProviderModelConfig = Field(
        default_factory=lambda: ProviderModelConfig(timeout=120)
    )
    session_search: ProviderModelConfig = Field(default_factory=ProviderModelConfig)
    skills_hub: ProviderModelConfig = Field(default_factory=ProviderModelConfig)
    approval: ProviderModelConfig = Field(default_factory=ProviderModelConfig)
    mcp: ProviderModelConfig = Field(default_factory=ProviderModelConfig)
    flush_memories: ProviderModelConfig = Field(default_factory=ProviderModelConfig)

class DisplayConfig(BaseConfigModel):
    compact: bool = Field(default=False)
    personality: str = Field(default="kawaii")
    resume_display: str = Field(default="full")
    busy_input_mode: str = Field(default="interrupt")
    bell_on_complete: bool = Field(default=False)
    show_reasoning: bool = Field(default=False)
    streaming: bool = Field(default=False)
    inline_diffs: bool = Field(default=True)
    show_cost: bool = Field(default=False)
    skin: str = Field(default="default")
    tool_progress_command: bool = Field(default=False)
    tool_preview_length: int = Field(default=0)

class PrivacyConfig(BaseConfigModel):
    redact_pii: bool = Field(default=False)

class VoiceEdgeConfig(BaseConfigModel):
    voice: str = Field(default="en-US-AriaNeural")

class VoiceElevenLabsConfig(BaseConfigModel):
    voice_id: str = Field(default="pNInz6obpgDQGcFmaJgB")
    model_id: str = Field(default="eleven_multilingual_v2")

class VoiceOpenAIConfig(BaseConfigModel):
    model: str = Field(default="gpt-4o-mini-tts")
    voice: str = Field(default="alloy")

class VoiceNeuttsConfig(BaseConfigModel):
    ref_audio: str = Field(default="")
    ref_text: str = Field(default="")
    model: str = Field(default="neuphonic/neutts-air-q4-gguf")
    device: str = Field(default="cpu")

class TTSConfig(BaseConfigModel):
    provider: str = Field(default="edge")
    edge: VoiceEdgeConfig = Field(default_factory=VoiceEdgeConfig)
    elevenlabs: VoiceElevenLabsConfig = Field(default_factory=VoiceElevenLabsConfig)
    openai: VoiceOpenAIConfig = Field(default_factory=VoiceOpenAIConfig)
    neutts: VoiceNeuttsConfig = Field(default_factory=VoiceNeuttsConfig)

class STTLocalConfig(BaseConfigModel):
    model: str = Field(default="base")

class STTOpenAIConfig(BaseConfigModel):
    model: str = Field(default="whisper-1")

class STTConfig(BaseConfigModel):
    enabled: bool = Field(default=True)
    provider: str = Field(default="local")
    local: STTLocalConfig = Field(default_factory=STTLocalConfig)
    openai: STTOpenAIConfig = Field(default_factory=STTOpenAIConfig)

class VoiceInputConfig(BaseConfigModel):
    record_key: str = Field(default="ctrl+b")
    max_recording_seconds: int = Field(default=120)
    auto_tts: bool = Field(default=False)
    silence_threshold: int = Field(default=200)
    silence_duration: float = Field(default=3.0)

class HumanDelayConfig(BaseConfigModel):
    mode: str = Field(default="off")
    min_ms: int = Field(default=800)
    max_ms: int = Field(default=2500)

class MemoryConfig(BaseConfigModel):
    memory_enabled: bool = Field(default=True)
    user_profile_enabled: bool = Field(default=True)
    memory_char_limit: int = Field(default=2200)
    user_char_limit: int = Field(default=1375)

class DelegationConfig(BaseConfigModel):
    model: str = Field(default="")
    provider: str = Field(default="")
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    max_iterations: int = Field(default=50)

class SkillsConfig(BaseConfigModel):
    external_dirs: List[str] = Field(default_factory=list)

class DiscordConfig(BaseConfigModel):
    require_mention: bool = Field(default=True)
    free_response_channels: str = Field(default="")
    auto_thread: bool = Field(default=True)
    reactions: bool = Field(default=True)

class ApprovalsConfig(BaseConfigModel):
    mode: str = Field(default="manual")
    timeout: int = Field(default=60)
    scope: str = Field(default="dangerous_only")
    companion_gate: bool = Field(default=True)

class WebsiteBlocklistConfig(BaseConfigModel):
    enabled: bool = Field(default=False)
    domains: List[str] = Field(default_factory=list)
    shared_files: List[str] = Field(default_factory=list)

class SecurityConfig(BaseConfigModel):
    redact_secrets: bool = Field(default=True)
    tirith_enabled: bool = Field(default=True)
    tirith_path: str = Field(default="tirith")
    tirith_timeout: int = Field(default=5)
    tirith_fail_open: bool = Field(default=True)
    website_blocklist: WebsiteBlocklistConfig = Field(default_factory=WebsiteBlocklistConfig)

class CronConfig(BaseConfigModel):
    wrap_response: bool = Field(default=True)

class LoggingConfig(BaseConfigModel):
    level: str = Field(default="INFO")
    max_size_mb: int = Field(default=5)
    backup_count: int = Field(default=3)

class HermesConfig(BaseConfigModel):
    model: Union[str, Dict[str, Any]] = Field(default="")
    fallback_providers: List[str] = Field(default_factory=list)
    credential_pool_strategies: Dict[str, Any] = Field(default_factory=dict)
    toolsets: List[str] = Field(default_factory=lambda: ["hermes-cli"])
    
    agent: AgentConfig = Field(default_factory=AgentConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    checkpoints: CheckpointsConfig = Field(default_factory=CheckpointsConfig)
    council: CouncilConfig = Field(default_factory=CouncilConfig)
    
    file_read_max_chars: int = Field(default=100_000)
    custom_providers: list = Field(default_factory=list)
    
    compression: CompressionConfig = Field(default_factory=CompressionConfig)
    provider_routing: Dict[str, Any] = Field(default_factory=dict)
    smart_model_routing: SmartModelRoutingConfig = Field(default_factory=SmartModelRoutingConfig)
    auxiliary: AuxiliaryConfig = Field(default_factory=AuxiliaryConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    voice: VoiceInputConfig = Field(default_factory=VoiceInputConfig)
    human_delay: HumanDelayConfig = Field(default_factory=HumanDelayConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    delegation: DelegationConfig = Field(default_factory=DelegationConfig)
    
    prefill_messages_file: str = Field(default="")
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    honcho: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = Field(default="")
    
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    whatsapp: Dict[str, Any] = Field(default_factory=dict)
    approvals: ApprovalsConfig = Field(default_factory=ApprovalsConfig)
    
    command_allowlist: List[str] = Field(default_factory=list)
    quick_commands: Dict[str, Any] = Field(default_factory=dict)
    personalities: Dict[str, Any] = Field(default_factory=dict)
    
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    cron: CronConfig = Field(default_factory=CronConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    config_version: int = Field(default=12, alias="_config_version")
