"""使用 Pydantic 定义的配置结构。"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """同时接受 camelCase 与 snake_case 键名的基础模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChannelsConfig(Base):
    """聊天通道配置。

    内置通道和插件通道的配置会作为额外字段（dict）存储。
    每个通道在自己的 ``__init__`` 中解析对应配置。
    通道级别的 ``streaming: true`` 会启用流式输出（要求实现 ``send_delta``）。
    """

    model_config = ConfigDict(extra="allow")

    send_progress: bool = True  # 将 agent 的文本进度流式发送到通道
    send_tool_hints: bool = False  # 流式发送工具调用提示（例如 read_file("…")）


class AgentDefaults(Base):
    """默认 agent 配置。"""

    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    provider: str = (
        "auto"  # provider 名称（例如 "anthropic"、"openrouter"），或使用 "auto" 自动检测
    )
    max_tokens: int = 8192
    context_window_tokens: int = 65_536
    temperature: float = 0.1
    max_tool_iterations: int = 40
    reasoning_effort: str | None = None  # low / medium / high，启用 LLM 思考模式


class AgentsConfig(Base):
    """Agent 配置。"""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider 配置。"""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # 自定义请求头（例如 AiHubMix 的 APP-Code）


class ProvidersConfig(Base):
    """LLM provider 集合配置。"""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)  # 任意兼容 OpenAI 的接口端点
    azure_openai: ProviderConfig = Field(default_factory=ProviderConfig)  # Azure OpenAI（model = deployment name）
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    ollama: ProviderConfig = Field(default_factory=ProviderConfig)  # Ollama 本地模型
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API 网关
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)  # SiliconFlow (硅基流动)
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)  # VolcEngine (火山引擎)
    volcengine_coding_plan: ProviderConfig = Field(default_factory=ProviderConfig)  # VolcEngine Coding Plan
    byteplus: ProviderConfig = Field(default_factory=ProviderConfig)  # BytePlus (VolcEngine international)
    byteplus_coding_plan: ProviderConfig = Field(default_factory=ProviderConfig)  # BytePlus Coding Plan
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig, exclude=True)  # OpenAI Codex（OAuth）
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig, exclude=True)  # Github Copilot（OAuth）


class HeartbeatConfig(Base):
    """心跳服务配置。"""

    enabled: bool = True
    interval_s: int = 30 * 60  # 30 分钟


class GatewayConfig(Base):
    """网关 / 服务端配置。"""

    host: str = "0.0.0.0"
    port: int = 18790
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)


class WebSearchConfig(Base):
    """网页搜索工具配置。"""

    provider: str = "brave"  # brave、tavily、duckduckgo、searxng、jina
    api_key: str = ""
    base_url: str = ""  # SearXNG 的基础 URL
    max_results: int = 5


class WebToolsConfig(Base):
    """网页工具配置。"""

    proxy: str | None = (
        None  # HTTP/SOCKS5 代理 URL，例如 "http://127.0.0.1:7890" 或 "socks5://127.0.0.1:1080"
    )
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell 执行工具配置。"""

    enable: bool = False
    timeout: int = 60
    path_append: str = ""


class PhoneExperienceMemoryConfig(Base):
    """PhoneAgent 结构化经验记忆配置。"""

    enable: bool = False
    embedding_model: str = "text-embedding-3-small"
    top_k: int = 3
    min_score: float = 0.55
    feedback_window_turns: int = 2
    feedback_window_minutes: int = 30
    chroma_path: str | None = None


class PhoneAgentConfig(Base):
    """
    手机能力配置。

    该配置同时服务于 Phase 1 的底层手机工具集，以及后续
    phone runner / phone subagent 的接线扩展。
    """

    enable: bool = True
    provider: str = "custom"
    base_url: str = "https://api.siliconflow.cn/v1"
    api_key: str = ""
    model: str = "Qwen/Qwen3.5-397B-A17B"
    extra_headers: dict[str, str] | None = None
    use_tool_calling: bool = True
    device_type: Literal["adb", "hdc", "ios"] = "adb"
    device_id: str | None = None
    adb_path: str | None = None
    platform_tools_dir: str | None = None
    adb_keyboard_apk_path: str | None = None
    auto_use_bundled_platform_tools: bool = True
    require_adb_keyboard: bool = False
    max_steps: int = 50
    lang: Literal["cn", "en"] = "cn"
    wda_url: str = "http://localhost:8100"
    max_tokens: int = 3000
    temperature: float = 0.0
    reasoning_effort: str | None = None
    experience_memory: PhoneExperienceMemoryConfig = Field(
        default_factory=PhoneExperienceMemoryConfig
    )


class MCPServerConfig(Base):
    """MCP 服务连接配置（stdio 或 HTTP）。"""

    type: Literal["stdio", "sse", "streamableHttp"] | None = None  # 省略时自动检测
    command: str = ""  # stdio 模式下要执行的命令（例如 "npx"）
    args: list[str] = Field(default_factory=list)  # stdio 模式下的命令参数
    env: dict[str, str] = Field(default_factory=dict)  # stdio 模式下附加的环境变量
    url: str = ""  # HTTP/SSE 模式下的端点 URL
    headers: dict[str, str] = Field(default_factory=dict)  # HTTP/SSE 模式下的自定义请求头
    tool_timeout: int = 30  # 工具调用在被取消前允许执行的秒数
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])  # 仅注册这些工具；既支持原始 MCP 名称，也支持包装后的 mcp_<server>_<tool> 名称；["*"] 表示全部工具，[] 表示不注册任何工具


class ToolsConfig(Base):
    """工具配置。"""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    phone_agent: PhoneAgentConfig = Field(default_factory=PhoneAgentConfig)
    restrict_to_workspace: bool = False  # 为 true 时，将所有工具访问限制在 workspace 目录内
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class Config(BaseSettings):
    """nanobot 的根配置。"""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    @property
    def workspace_path(self) -> Path:
        """获取展开后的 workspace 路径。"""
        return Path(self.agents.defaults.workspace).expanduser()

    def _match_provider(
        self, model: str | None = None
    ) -> tuple["ProviderConfig | None", str | None]:
        """匹配 provider 配置及其注册名，返回 ``(config, spec_name)``。"""
        from nanobot.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return (p, forced) if p else (None, None)

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        # 显式的 provider 前缀优先，避免 `github-copilot/...codex` 被错误匹配到 openai_codex。
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and model_prefix and normalized_prefix == spec.name:
                if spec.is_oauth or spec.is_local or p.api_key:
                    return p, spec.name

        # 按关键字匹配（顺序与 PROVIDERS 注册表一致）
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if spec.is_oauth or spec.is_local or p.api_key:
                    return p, spec.name

        # 回退逻辑：已配置的本地 provider 可以承接没有 provider 特征关键字的模型，
        # 例如 Ollama 上的纯 "llama3.2"。
        # 优先选择 detect_by_base_keyword 能命中已配置 api_base 的 provider，
        # 例如 Ollama 的 "11434" 命中 "http://localhost:11434"，优先于单纯按注册顺序选择。
        local_fallback: tuple[ProviderConfig, str] | None = None
        for spec in PROVIDERS:
            if not spec.is_local:
                continue
            p = getattr(self.providers, spec.name, None)
            if not (p and p.api_base):
                continue
            if spec.detect_by_base_keyword and spec.detect_by_base_keyword in p.api_base:
                return p, spec.name
            if local_fallback is None:
                local_fallback = (p, spec.name)
        if local_fallback:
            return local_fallback

        # 最终回退：优先网关类 provider，其次其他 provider（遵循注册顺序）
        # OAuth provider 不能作为回退选项，因为它们要求显式指定模型
        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """获取匹配到的 provider 配置（api_key、api_base、extra_headers），必要时回退到第一个可用 provider。"""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """获取匹配到的 provider 注册名（例如 "deepseek"、"openrouter"）。"""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """获取指定模型对应的 API key，必要时回退到第一个可用 key。"""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """获取指定模型对应的 API base URL，并为网关 / 本地 provider 应用默认地址。"""
        from nanobot.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        # 这里只为网关类 provider 提供默认 api_base。
        # 标准 provider（例如 Moonshot）会在 _setup_env 中通过环境变量设置 base URL，
        # 以避免污染全局的 litellm.api_base。
        if name:
            spec = find_by_name(name)
            if spec and (spec.is_gateway or spec.is_local) and spec.default_api_base:
                return spec.default_api_base
        return None

    model_config = ConfigDict(env_prefix="NANOBOT_", env_nested_delimiter="__")
