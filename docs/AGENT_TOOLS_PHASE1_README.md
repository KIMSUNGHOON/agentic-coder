# Agent Tools Phase 1 - User Guide

**Version**: 1.0.0
**Date**: 2026-01-08
**Status**: ✅ Production Ready

---

## Overview

Agent Tools Phase 1 adds **3 powerful new tools** to the TestCodeAgent system, enabling agents to search the web, discover code semantically, and create git commits programmatically.

### New Tools

1. **WebSearchTool** - Search the internet using Tavily API
2. **CodeSearchTool** - Semantic code search using ChromaDB RAG
3. **GitCommitTool** - Create git commits with validation

**Total Tools**: 14 (11 original + 3 new)

---

## Features

### 1. WebSearchTool 🌐

Search the web for up-to-date information using the Tavily search API.

**Capabilities**:
- Natural language search queries
- Configurable result count (1-20)
- Search depth options (basic/advanced)
- High-quality, AI-optimized results

**Use Cases**:
- "What are the latest Python best practices in 2025?"
- "Find documentation for FastAPI streaming responses"
- "Search for solutions to ChromaDB connection errors"

**Example Usage**:
```python
from app.tools.registry import get_registry

registry = get_registry()
web_search = registry.get_tool("web_search")

result = await web_search.execute(
    query="Python asyncio best practices 2025",
    max_results=5,
    search_depth="basic"
)

# Result contains:
# - result_count: Number of results found
# - results: List of {title, url, content, score}
```

**Configuration**:
```bash
# .env
TAVILY_API_KEY=your_api_key_here  # Get from https://tavily.com
```

---

### 2. CodeSearchTool 🔍

Semantic search across your codebase using natural language queries.

**Capabilities**:
- Natural language code queries
- Semantic similarity matching (not just keyword search)
- Filter by repository and file type
- Fast retrieval using ChromaDB vector database

**Use Cases**:
- "Find authentication logic"
- "Where is file upload handling implemented?"
- "Show me error handling code"
- "Find API endpoint definitions"

**Example Usage**:
```python
from app.tools.registry import get_registry

registry = get_registry()
code_search = registry.get_tool("code_search")

result = await code_search.execute(
    query="authentication middleware",
    n_results=5,
    repo_filter="TestCodeAgent",
    file_type_filter="python"
)

# Result contains:
# - result_count: Number of code snippets found
# - results: List of {file_path, file_type, content, score, repo}
```

**Configuration**:
```bash
# .env
CHROMA_DB_PATH=./chroma_db  # Path to vector database
```

**Prerequisites**:
- ChromaDB must be initialized with embedded code
- Use `RepositoryEmbedder` to embed repositories first

---

### 3. GitCommitTool 🔨

Create git commits programmatically with validation.

**Capabilities**:
- Create commits with custom messages
- Stage specific files or all changes
- Validate commit message length
- Parse commit hash from output
- Comprehensive error handling

**Use Cases**:
- Automated commit creation in workflows
- Batch file commits
- Workflow integration with git

**Example Usage**:
```python
from app.tools.registry import get_registry

registry = get_registry()
git_commit = registry.get_tool("git_commit")

# Option 1: Commit specific files
result = await git_commit.execute(
    message="feat: Add web search functionality",
    files=["backend/app/tools/web_tools.py", "requirements.txt"]
)

# Option 2: Commit all changes
result = await git_commit.execute(
    message="refactor: Update tool system",
    add_all=True
)

# Result contains:
# - commit_hash: SHA of created commit
# - message: Commit message
# - staged_files: List of files committed
```

**Validation Rules**:
- Message: 5-500 characters
- Must have staged changes
- Git must be installed and configured

---

## Installation

### 1. Install Dependencies

```bash
# Install tavily-python for WebSearchTool
pip install tavily-python>=0.3.0

# ChromaDB and other dependencies already installed
```

### 2. Configure API Keys

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Tavily API key
nano .env
```

```bash
# .env
TAVILY_API_KEY=your_api_key_here
CHROMA_DB_PATH=./chroma_db
```

### 3. Get Tavily API Key

1. Visit https://tavily.com
2. Sign up for free account
3. Copy your API key from dashboard
4. Add to `.env` file

**Free Tier**: 1,000 searches/month

---

## Usage

### For LangChain Agents

All new tools are automatically available through the LangChain adapter:

```python
from app.agent.langchain.tool_adapter import get_langchain_tools

# Get all tools (includes Phase 1 tools)
tools = get_langchain_tools(session_id="my-session")

# Get specific tools
web_search_tool = next(t for t in tools if t.name == "web_search")
code_search_tool = next(t for t in tools if t.name == "code_search")
git_commit_tool = next(t for t in tools if t.name == "git_commit")

# Use in LangChain agent
from langchain.agents import initialize_agent

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description"
)
```

### For Direct Use

```python
from app.tools.registry import get_registry

# Get registry (singleton)
registry = get_registry()

# WebSearchTool
web_search = registry.get_tool("web_search")
result = await web_search.execute(query="Python FastAPI 2025")

# CodeSearchTool
code_search = registry.get_tool("code_search")
result = await code_search.execute(query="authentication logic")

# GitCommitTool
git_commit = registry.get_tool("git_commit")
result = await git_commit.execute(
    message="feat: Add new feature",
    add_all=True
)
```

---

## Tool Categories

Agent tools are organized by category:

| Category | Tools | Count |
|----------|-------|-------|
| **FILE** | ReadFile, WriteFile, SearchFiles, ListDirectory | 4 |
| **CODE** | ExecutePython, RunTests, LintCode | 3 |
| **GIT** | GitStatus, GitDiff, GitLog, GitBranch, **GitCommit** ⭐ | 5 |
| **WEB** | **WebSearch** ⭐ | 1 |
| **SEARCH** | **CodeSearch** ⭐ | 1 |
| **Total** | | **14** |

⭐ = New in Phase 1

---

## Error Handling

All tools implement robust error handling:

### WebSearchTool Errors

```python
# API key not set
{
    "success": false,
    "error": "Tavily API key not found. Set TAVILY_API_KEY environment variable"
}

# Network error
{
    "success": false,
    "error": "Web search failed: Connection timeout"
}
```

### CodeSearchTool Errors

```python
# ChromaDB not initialized
{
    "success": false,
    "error": "ChromaDB initialization failed: Collection not found"
}

# No results found (success=True, but result_count=0)
{
    "success": true,
    "output": {"result_count": 0, "results": []}
}
```

### GitCommitTool Errors

```python
# Nothing to commit
{
    "success": false,
    "error": "Nothing to commit (no staged changes). Use add_all=True or specify files."
}

# Message too short
{
    "success": false,
    "error": "Commit message too short (minimum 5 characters)"
}

# Git not installed
{
    "success": false,
    "error": "Git not found. Please install git."
}
```

---

## Testing

### Run Unit Tests

```bash
# Test individual tools
pytest backend/app/tools/tests/test_web_tools.py -v
pytest backend/app/tools/tests/test_search_tools.py -v
pytest backend/app/tools/tests/test_git_commit.py -v

# Test integration
pytest backend/app/tools/tests/test_integration.py -v
```

### Run Integration Tests

```bash
# Requires: TAVILY_API_KEY set, ChromaDB initialized
pytest backend/app/tools/tests/ -v -m integration
```

### Test with Mock Data

All unit tests use mocks by default - no API keys or external services required:

```bash
pytest backend/app/tools/tests/ -v
```

---

## Performance

### WebSearchTool

- **Latency**: 500-2000ms (network dependent)
- **Rate Limit**: 1000 searches/month (free tier)
- **Caching**: Not implemented (Phase 2)

### CodeSearchTool

- **Latency**: <500ms (local database)
- **Embedding Model**: ChromaDB default (sentence-transformers)
- **Index Size**: Depends on codebase size
- **Memory**: ~100-500MB (typical)

### GitCommitTool

- **Latency**: 100-500ms (local git commands)
- **No External Dependencies**: Pure git subprocess calls
- **Validation**: Message length, staged changes

---

## Troubleshooting

### WebSearchTool Issues

**Problem**: "Tavily API key not found"
**Solution**: Set `TAVILY_API_KEY` in `.env` file

**Problem**: "Import error: tavily-python not installed"
**Solution**: `pip install tavily-python>=0.3.0`

**Problem**: "Rate limit exceeded"
**Solution**: Upgrade Tavily plan or implement caching (Phase 2)

### CodeSearchTool Issues

**Problem**: "ChromaDB initialization failed"
**Solution**: Embed repository first using `RepositoryEmbedder`

```python
import chromadb
from app.utils.repository_embedder import RepositoryEmbedder

client = chromadb.PersistentClient(path="./chroma_db")
embedder = RepositoryEmbedder(client, "code_repositories")
embedder.embed_repository(
    repo_path="/path/to/repo",
    repo_name="my_repo"
)
```

**Problem**: "No results found"
**Solution**: Check that repository was embedded, try broader query

### GitCommitTool Issues

**Problem**: "Nothing to commit"
**Solution**: Use `add_all=True` or specify `files` parameter

**Problem**: "Git not found"
**Solution**: Install git: `apt install git` or `brew install git`

**Problem**: "Commit message too short"
**Solution**: Use at least 5 characters for commit message

---

## Backward Compatibility

✅ **100% Backward Compatible**

- All existing tools unchanged
- No breaking changes to APIs
- WebUI continues to work without Phase 1 tools
- Agents automatically discover new tools
- Optional functionality (graceful degradation)

**Existing Tool Count**:
- Before Phase 1: 11 tools
- After Phase 1: 14 tools (+3)

---

## Next Steps

### Phase 2 (Planned)

1. **LangChain Tool Adapter** - @tool decorator support
2. **OpenAI Function Calling** - GPT-4 schema support
3. **Tool Result Caching** - Cache expensive operations
4. **HttpRequestTool** - REST API calls

### Phase 3 (Planned)

1. **FormatCodeTool** - black/prettier integration
2. **ShellCommandTool** - Safe shell execution
3. **DocstringGenerator** - AI-powered docstrings
4. **Tool Observability** - Metrics and monitoring

---

## API Reference

### WebSearchTool

```python
class WebSearchTool(BaseTool):
    def __init__(self, api_key: Optional[str] = None)

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> ToolResult
```

### CodeSearchTool

```python
class CodeSearchTool(BaseTool):
    def __init__(self, chroma_path: Optional[str] = None)

    async def execute(
        self,
        query: str,
        n_results: int = 5,
        repo_filter: Optional[str] = None,
        file_type_filter: Optional[str] = None
    ) -> ToolResult
```

### GitCommitTool

```python
class GitCommitTool(BaseTool):
    def __init__(self)

    async def execute(
        self,
        message: str,
        files: Optional[List[str]] = None,
        add_all: bool = False
    ) -> ToolResult
```

---

## License

Same as TestCodeAgent project license.

---

## Support

- **Issues**: https://github.com/KIMSUNGHOON/TestCodeAgent/issues
- **Documentation**: `docs/AGENT_TOOLS_ANALYSIS_REPORT.md`
- **Analysis**: `docs/AGENT_TOOLS_PHASE1_IMPACT_ANALYSIS.md`

---

## Changelog

### v1.0.0 (2026-01-08)

- ✅ Added WebSearchTool with Tavily API integration
- ✅ Added CodeSearchTool with ChromaDB RAG integration
- ✅ Added GitCommitTool for automated commits
- ✅ Updated ToolRegistry to support WEB and SEARCH categories
- ✅ 100% backward compatible with existing tools
- ✅ Comprehensive unit and integration tests
- ✅ Documentation and configuration examples
