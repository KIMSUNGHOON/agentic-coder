# Agent Tools - Online/Offline Mode Design

**Date**: 2026-01-08
**Purpose**: Network security interface design for online/offline mode
**Status**: ✅ Design Complete - Ready for Phase 2 Implementation

---

## Executive Summary

**보안 요구사항**: 외부 네트워크 요청이 제한된 보안망 환경을 지원하기 위해 online/offline mode 인터페이스 설계

**핵심 목표**:
1. 네트워크 모드를 명시적으로 설정 가능
2. 외부 네트워크 필요 도구 자동 비활성화
3. Runtime에 모드 확인 및 graceful fallback
4. Phase 2부터 순차적 적용

---

## 1. Architecture Design

### 1.1 Tool Network Requirements

각 도구는 네트워크 요구사항을 명시적으로 선언:

| Tool | Network Type | Offline Usable | Reason |
|------|--------------|----------------|--------|
| WebSearchTool | EXTERNAL_API | ❌ No | Tavily API (interactive) |
| HttpRequestTool (Phase 2) | EXTERNAL_API | ❌ No | REST API calls (interactive) |
| DownloadFileTool (Phase 2) | EXTERNAL_DOWNLOAD | ✅ Yes | wget/curl (one-way) |
| CodeSearchTool | LOCAL | ✅ Yes | Local ChromaDB |
| GitCommitTool | LOCAL | ✅ Yes | Local git commands |
| FileTools (4) | LOCAL | ✅ Yes | Local file system |
| CodeTools (3) | LOCAL | ✅ Yes | Local execution |
| GitTools (4) | LOCAL | ✅ Yes | Local git |

**Summary**:
- **Online-only tools**: 2 (WebSearchTool, HttpRequestTool) - blocked in offline mode
- **Download tools**: 1 (DownloadFileTool) - allowed in offline mode (wget/curl)
- **Offline-capable tools**: 12 (모든 로컬 도구)

**Note**: 보안망에서 wget/curl 같은 파일 다운로드는 허용되지만, 양방향 API 통신(Tavily, REST APIs)은 차단됨

### 1.2 Network Mode Configuration

**Environment Variable**:
```bash
# .env
NETWORK_MODE=online  # or 'offline'
```

**Supported Modes**:
- `online` (default) - 모든 도구 사용 가능
- `offline` - 외부 네트워크 필요 도구 비활성화

---

## 2. Interface Design

### 2.1 BaseTool Extension (Phase 2)

**File**: `backend/app/tools/base.py`

```python
class BaseTool(ABC):
    """Base class for all tools"""

    def __init__(self, name: str, category: ToolCategory):
        self.name = name
        self.category = category
        self.description = ""
        self.parameters = {}

        # NEW: Network requirement declaration
        self.requires_network = False  # Default: offline-capable
        self.network_type = NetworkType.LOCAL  # Default: local only

    # NEW: Network availability check
    def is_available_in_mode(self, network_mode: str) -> bool:
        """Check if tool is available in current network mode

        Args:
            network_mode: 'online' or 'offline'

        Returns:
            True if tool can be used in this mode
        """
        if network_mode == "offline":
            # Block interactive external APIs in offline mode
            if self.network_type == NetworkType.EXTERNAL_API:
                return False
            # Allow downloads (wget/curl) even in offline mode
            if self.network_type == NetworkType.EXTERNAL_DOWNLOAD:
                return True
        return True

    # NEW: Graceful degradation message
    def get_unavailable_message(self) -> str:
        """Get message when tool is unavailable due to network mode"""
        if self.requires_network:
            return (
                f"Tool '{self.name}' requires network access and is disabled in offline mode. "
                f"Set NETWORK_MODE=online to enable."
            )
        return ""
```

**NetworkType Enum**:
```python
class NetworkType(Enum):
    """Network requirement types"""
    LOCAL = "local"              # No network needed (local file system, git, etc.)
    INTERNAL = "internal"        # Internal network only (company intranet)
    EXTERNAL_API = "external_api"    # External API calls (Tavily, REST APIs) - BLOCKED in offline
    EXTERNAL_DOWNLOAD = "external_download"  # File downloads (wget, curl) - ALLOWED in offline
```

**Important Note**:
- `EXTERNAL_API`: Interactive API calls (Tavily search, REST APIs) - **blocked in offline mode**
- `EXTERNAL_DOWNLOAD`: One-way file downloads (wget, curl) - **allowed in offline mode**
- This distinction allows secure networks to download packages/files while blocking interactive external APIs

### 2.2 Tool Implementation Pattern

**Online-only Tool Example** (WebSearchTool - Interactive API):
```python
class WebSearchTool(BaseTool):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("web_search", ToolCategory.WEB)

        # NEW: Declare network requirement (interactive API - blocked in offline)
        self.requires_network = True
        self.network_type = NetworkType.EXTERNAL_API

        self.description = "Search the web (requires online mode - interactive API)"
        # ... rest of implementation
```

**Download Tool Example** (DownloadFileTool - One-way download):
```python
class DownloadFileTool(BaseTool):
    def __init__(self):
        super().__init__("download_file", ToolCategory.FILE)

        # NEW: Declare as download (allowed in offline mode)
        self.requires_network = True  # Still needs network
        self.network_type = NetworkType.EXTERNAL_DOWNLOAD  # But allowed in offline

        self.description = "Download files using wget/curl (works in offline mode)"
        # ... rest of implementation
```

**Offline-capable Tool Example** (CodeSearchTool):
```python
class CodeSearchTool(BaseTool):
    def __init__(self, chroma_path: Optional[str] = None):
        super().__init__("code_search", ToolCategory.SEARCH)

        # NEW: Declare as offline-capable
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Search code semantically (works offline)"
        # ... rest of implementation
```

### 2.3 ToolRegistry Enhancement (Phase 2)

**File**: `backend/app/tools/registry.py`

```python
class ToolRegistry:
    """Singleton registry with network mode support"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._network_mode = self._get_network_mode()
        self._register_default_tools()

        logger.info(f"Tool Registry initialized: mode={self._network_mode}, tools={len(self._tools)}")

        # Log disabled tools in offline mode
        if self._network_mode == "offline":
            disabled = [t.name for t in self._tools.values() if t.requires_network]
            if disabled:
                logger.warning(f"Offline mode: {len(disabled)} tools disabled: {disabled}")

    def _get_network_mode(self) -> str:
        """Get network mode from environment"""
        import os
        mode = os.getenv("NETWORK_MODE", "online").lower()

        if mode not in ["online", "offline"]:
            logger.warning(f"Invalid NETWORK_MODE '{mode}', defaulting to 'online'")
            mode = "online"

        return mode

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[BaseTool]:
        """List tools, filtered by network mode and category"""
        tools = list(self._tools.values())

        # Filter by category
        if category:
            tools = [t for t in tools if t.category == category]

        # Filter by network mode
        tools = [t for t in tools if t.is_available_in_mode(self._network_mode)]

        return tools

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name, checking network availability"""
        tool = self._tools.get(name)

        if tool and not tool.is_available_in_mode(self._network_mode):
            logger.warning(
                f"Tool '{name}' requested but unavailable in {self._network_mode} mode"
            )
            return None

        return tool

    def get_network_mode(self) -> str:
        """Get current network mode"""
        return self._network_mode

    def get_statistics(self) -> Dict:
        """Get registry statistics including network mode info"""
        stats = {
            "total_tools": len(self._tools),
            "network_mode": self._network_mode,
            "by_category": {},
            "by_network": {
                "local": 0,
                "internal": 0,
                "external": 0
            },
            "available_tools": 0,
            "disabled_tools": 0
        }

        for tool in self._tools.values():
            # Category stats
            cat = tool.category.value
            if cat not in stats["by_category"]:
                stats["by_category"][cat] = 0
            stats["by_category"][cat] += 1

            # Network stats
            stats["by_network"][tool.network_type.value] += 1

            # Availability stats
            if tool.is_available_in_mode(self._network_mode):
                stats["available_tools"] += 1
            else:
                stats["disabled_tools"] += 1

        return stats
```

### 2.4 Configuration File (.env)

**File**: `.env.example`

```bash
# =========================
# Network Mode Configuration
# =========================
# Controls which tools are available based on network access
# Options:
#   - online  : All tools available (requires internet access)
#   - offline : Only local tools (no external network requests)
#
# Use 'offline' in secure/air-gapped networks
NETWORK_MODE=online

# =========================
# Agent Tools Configuration
# =========================
# Tavily API Key for Web Search Tool (ONLINE MODE ONLY)
# Get your API key at: https://tavily.com
# Leave empty to disable web search functionality
# Note: Ignored in offline mode
TAVILY_API_KEY=

# ChromaDB Path for Code Search Tool (WORKS OFFLINE)
# Default: ./chroma_db (relative to project root)
CHROMA_DB_PATH=./chroma_db
```

---

## 3. User Experience

### 3.1 Online Mode (Default)

**Configuration**:
```bash
NETWORK_MODE=online
TAVILY_API_KEY=your_key
```

**Behavior**:
- ✅ All 15 tools available (when Phase 2 complete)
- ✅ WebSearchTool works (external API)
- ✅ HttpRequestTool works (REST APIs)
- ✅ DownloadFileTool works (wget/curl)
- ✅ CodeSearchTool works (local)
- ✅ GitCommitTool works (local)

**Registry Stats**:
```json
{
  "total_tools": 15,
  "network_mode": "online",
  "available_tools": 15,
  "disabled_tools": 0,
  "by_network": {
    "local": 12,
    "external_api": 2,
    "external_download": 1
  }
}
```

### 3.2 Offline Mode (Secure Network)

**Configuration**:
```bash
NETWORK_MODE=offline
# TAVILY_API_KEY ignored
```

**Behavior**:
- ✅ 13 tools available (12 local + 1 download)
- ❌ WebSearchTool disabled (interactive API)
- ❌ HttpRequestTool disabled (interactive API)
- ✅ DownloadFileTool works (wget/curl allowed in offline mode)
- ✅ CodeSearchTool works (local ChromaDB)
- ✅ GitCommitTool works (local git)

**Registry Stats**:
```json
{
  "total_tools": 15,
  "network_mode": "offline",
  "available_tools": 13,
  "disabled_tools": 2,
  "by_network": {
    "local": 12,
    "external_api": 0,
    "external_download": 1
  }
}
```

**User Feedback**:
```
[INFO] Offline mode: 13/15 tools available
[WARNING] 2 tools disabled (interactive APIs): ['web_search', 'http_request']
[INFO] Download tool available: wget/curl allowed in offline mode
```

### 3.3 Tool Request in Wrong Mode

**Scenario**: Agent requests `web_search` in offline mode

```python
tool = registry.get_tool("web_search")
# Returns: None

# Log output:
# [WARNING] Tool 'web_search' requested but unavailable in offline mode
```

**Agent Behavior**:
- Agent receives `None` instead of tool
- Agent should gracefully handle missing tool
- Agent can use alternative tools (e.g., CodeSearchTool for docs)

---

## 4. Migration Plan

### Phase 2 Implementation (12 hours)

**Step 1: BaseTool Extension (2h)**
```python
# backend/app/tools/base.py
- Add requires_network attribute
- Add network_type attribute
- Add is_available_in_mode() method (with download support)
- Add NetworkType enum (LOCAL, INTERNAL, EXTERNAL_API, EXTERNAL_DOWNLOAD)
```

**Step 2: Update Existing Tools (2h)**
```python
# Phase 1 tools
WebSearchTool:       requires_network = True,  network_type = EXTERNAL_API
CodeSearchTool:      requires_network = False, network_type = LOCAL
GitCommitTool:       requires_network = False, network_type = LOCAL

# Original tools (11)
All file/code/git:   requires_network = False, network_type = LOCAL

# Phase 2 new tools
HttpRequestTool:     requires_network = True,  network_type = EXTERNAL_API
DownloadFileTool:    requires_network = True,  network_type = EXTERNAL_DOWNLOAD
```

**Step 3: ToolRegistry Enhancement (3h)**
```python
# backend/app/tools/registry.py
- Add _get_network_mode()
- Filter tools in list_tools()
- Check availability in get_tool()
- Enhanced statistics
```

**Step 4: Configuration (1h)**
```python
# .env.example, .env
- Add NETWORK_MODE variable
- Update documentation
```

**Step 5: Testing (3h)**
```python
# backend/app/tools/tests/test_network_mode.py (NEW)
- Test online mode (all tools)
- Test offline mode (local only)
- Test tool filtering
- Test graceful degradation
```

**Step 6: Documentation (1h)**
```python
# Update docs
- AGENT_TOOLS_PHASE1_README.md
- Add network mode section
- Usage examples for both modes
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

**File**: `backend/app/tools/tests/test_network_mode.py` (NEW in Phase 2)

```python
import pytest
import os
from unittest.mock import patch
from app.tools.registry import ToolRegistry, get_registry
from app.tools.base import NetworkType

class TestNetworkMode:
    """Test network mode functionality"""

    def test_online_mode_all_tools_available(self):
        """Test that all tools are available in online mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()
            stats = registry.get_statistics()

            assert stats["network_mode"] == "online"
            assert stats["available_tools"] == 14
            assert stats["disabled_tools"] == 0

    def test_offline_mode_filters_network_tools(self):
        """Test that network tools are filtered in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            registry = ToolRegistry()
            stats = registry.get_statistics()

            assert stats["network_mode"] == "offline"
            assert stats["available_tools"] == 12
            assert stats["disabled_tools"] == 2

    def test_offline_mode_web_search_unavailable(self):
        """Test WebSearchTool is unavailable in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            registry = ToolRegistry()
            tool = registry.get_tool("web_search")

            assert tool is None

    def test_offline_mode_code_search_available(self):
        """Test CodeSearchTool is available in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            registry = ToolRegistry()
            tool = registry.get_tool("code_search")

            assert tool is not None
            assert tool.name == "code_search"

    def test_tool_network_type_declaration(self):
        """Test tools declare correct network types"""
        registry = ToolRegistry()

        web_search = registry._tools["web_search"]
        assert web_search.requires_network is True
        assert web_search.network_type == NetworkType.EXTERNAL

        code_search = registry._tools["code_search"]
        assert code_search.requires_network is False
        assert code_search.network_type == NetworkType.LOCAL

    def test_invalid_mode_defaults_to_online(self):
        """Test invalid mode defaults to online"""
        with patch.dict(os.environ, {"NETWORK_MODE": "invalid"}):
            registry = ToolRegistry()
            assert registry.get_network_mode() == "online"
```

### 5.2 Integration Tests

```python
class TestNetworkModeIntegration:
    """Test network mode integration with agents"""

    @pytest.mark.asyncio
    async def test_agent_graceful_degradation_offline(self):
        """Test agent handles unavailable tools gracefully"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            from app.agent.langchain.tool_adapter import get_langchain_tools

            tools = get_langchain_tools(session_id="test")
            tool_names = [t.name for t in tools]

            # Should have 12 tools, not 14
            assert len(tools) == 12
            assert "web_search" not in tool_names
            assert "code_search" in tool_names
```

---

## 6. Documentation Updates

### 6.1 README Section

**Add to**: `docs/AGENT_TOOLS_PHASE1_README.md`

```markdown
## Network Mode

TestCodeAgent supports two network modes for different deployment environments:

### Online Mode (Default)

**Use Case**: Development, cloud deployments, networks with internet access

**Configuration**:
```bash
NETWORK_MODE=online
TAVILY_API_KEY=your_key
```

**Available Tools**: All 14 tools
- ✅ WebSearchTool (external API)
- ✅ CodeSearchTool (local)
- ✅ All other tools

### Offline Mode (Secure Networks)

**Use Case**: Air-gapped networks, secure corporate environments, restricted internet

**Configuration**:
```bash
NETWORK_MODE=offline
```

**Available Tools**: 12 local tools
- ❌ WebSearchTool (disabled - requires external API)
- ✅ CodeSearchTool (works - local database)
- ✅ GitCommitTool (works - local git)
- ✅ All file/code/git tools

**Behavior**:
- External network tools automatically disabled
- Agents gracefully handle unavailable tools
- No external requests made
- Suitable for secure/restricted networks

### Tool Network Requirements

| Tool | Network | Offline Usable |
|------|---------|----------------|
| WebSearchTool | External | ❌ No |
| CodeSearchTool | Local | ✅ Yes |
| GitCommitTool | Local | ✅ Yes |
| File Tools (4) | Local | ✅ Yes |
| Code Tools (3) | Local | ✅ Yes |
| Git Tools (4) | Local | ✅ Yes |
```

### 6.2 Security Considerations

**Add to documentation**:

```markdown
## Security Considerations

### Network Isolation

**Offline Mode Benefits**:
- ✅ No external API calls (zero external attack surface)
- ✅ No API keys required
- ✅ Suitable for air-gapped networks
- ✅ Compliance with strict security policies
- ✅ Data never leaves local network

**Online Mode Risks**:
- ⚠️ External API calls to Tavily
- ⚠️ API keys in environment variables
- ⚠️ Network egress required
- ⚠️ Third-party service dependency

**Recommendation**:
- Use **offline mode** in production secure environments
- Use **online mode** only in development or trusted networks
- Never expose API keys in version control
- Rotate API keys regularly
```

---

## 7. Future Enhancements

### Phase 3: Internal Network Mode

**New Mode**: `internal`
```bash
NETWORK_MODE=internal  # Allow intranet, block internet
```

**Use Case**: Corporate networks with internal APIs but no internet

**Tool Behavior**:
- ✅ Allow internal HTTP requests (company APIs)
- ✅ Allow downloads (wget/curl)
- ❌ Block external internet (Tavily)
- ✅ All local tools

### Phase 3: Per-Tool Override

**Configuration**:
```bash
NETWORK_MODE=offline
ALLOW_TOOLS=code_search,git_commit  # Whitelist specific tools
BLOCK_TOOLS=execute_python         # Blacklist specific tools
```

### Secure Network Download Policy

**Important Clarification**:
- **wget/curl downloads**: ✅ Allowed in offline mode (one-way, file download only)
- **Interactive APIs**: ❌ Blocked in offline mode (Tavily, REST APIs with responses)
- **Rationale**: Downloads don't send sensitive data out; APIs may leak information

**Example Use Cases in Offline Mode**:
```python
# ✅ ALLOWED: Download public packages
download_tool = registry.get_tool("download_file")
result = await download_tool.execute(
    url="https://pypi.org/packages/...",
    destination="/tmp/package.tar.gz"
)

# ❌ BLOCKED: Search external API
web_search = registry.get_tool("web_search")  # Returns None in offline mode

# ❌ BLOCKED: Call external REST API
http_tool = registry.get_tool("http_request")  # Returns None in offline mode
```

---

## 8. Migration Checklist

### Phase 2 Implementation Tasks

- [ ] **BaseTool Extension** (2h)
  - [ ] Add `requires_network` attribute
  - [ ] Add `network_type` attribute
  - [ ] Add `NetworkType` enum
  - [ ] Add `is_available_in_mode()` method
  - [ ] Add `get_unavailable_message()` method

- [ ] **Update Phase 1 Tools** (2h)
  - [ ] WebSearchTool: `requires_network=True, network_type=EXTERNAL`
  - [ ] CodeSearchTool: `requires_network=False, network_type=LOCAL`
  - [ ] GitCommitTool: `requires_network=False, network_type=LOCAL`

- [ ] **Update Original Tools** (30min)
  - [ ] All 11 original tools: `requires_network=False, network_type=LOCAL`

- [ ] **ToolRegistry Enhancement** (3h)
  - [ ] Add `_get_network_mode()` method
  - [ ] Filter in `list_tools()`
  - [ ] Check in `get_tool()`
  - [ ] Add `get_network_mode()` method
  - [ ] Enhanced `get_statistics()`

- [ ] **Configuration** (1h)
  - [ ] Add `NETWORK_MODE` to `.env.example`
  - [ ] Add documentation comments
  - [ ] Update config validation

- [ ] **Testing** (3h)
  - [ ] Create `test_network_mode.py`
  - [ ] Online mode tests
  - [ ] Offline mode tests
  - [ ] Tool filtering tests
  - [ ] Integration tests

- [ ] **Documentation** (1h)
  - [ ] Update `AGENT_TOOLS_PHASE1_README.md`
  - [ ] Add network mode section
  - [ ] Security considerations
  - [ ] Usage examples

- [ ] **Git Commit & Push**
  - [ ] Commit with descriptive message
  - [ ] Update `Requirement.md`
  - [ ] Push to remote

**Total**: 12 hours (Phase 2 task)

---

## 9. Example Usage Scenarios

### Scenario 1: Development (Online)

```bash
# .env
NETWORK_MODE=online
TAVILY_API_KEY=dev_key_12345
```

```python
# All tools work
registry = get_registry()

# Web search works
web = registry.get_tool("web_search")
result = await web.execute(query="Python 2025")  # ✅ Works

# Local search works
code = registry.get_tool("code_search")
result = await code.execute(query="auth")  # ✅ Works
```

### Scenario 2: Production Secure Network (Offline)

```bash
# .env
NETWORK_MODE=offline
# No TAVILY_API_KEY needed
```

```python
# Only local tools work
registry = get_registry()

# Web search disabled
web = registry.get_tool("web_search")  # Returns None
# Agent handles gracefully

# Local search works
code = registry.get_tool("code_search")
result = await code.execute(query="auth")  # ✅ Works

# Git commits work
git = registry.get_tool("git_commit")
result = await git.execute(message="Update")  # ✅ Works
```

### Scenario 3: Agent Adaptation

```python
# Agent checks tool availability
tools = registry.list_tools()

if "web_search" in [t.name for t in tools]:
    # Use web search
    result = await web_search.execute(query="...")
else:
    # Fallback to local docs search
    result = await code_search.execute(
        query="...",
        file_type_filter="markdown"
    )
```

---

## 10. Conclusion

**Design Complete**: ✅ Ready for Phase 2 implementation

**Key Benefits**:
1. ✅ **Security**: Offline mode for air-gapped networks
2. ✅ **Flexibility**: Easy mode switching via environment
3. ✅ **Graceful**: Tools automatically filtered by mode
4. ✅ **Clear**: Explicit network requirement declaration
5. ✅ **Tested**: Comprehensive test strategy

**Implementation Timeline**:
- Phase 2: 12 hours (network mode infrastructure)
- All tools updated with network declarations
- Full test coverage
- Documentation complete

**Next Steps**:
1. Phase 2 시작 시 이 설계 문서 참고
2. BaseTool 확장부터 순차적 구현
3. 테스트 작성 및 검증
4. 문서 업데이트

---

**Approved for Phase 2 Implementation** ✅
