# Agentic 2.0 Architecture - LLM-First Design

## Core Philosophy

**Agentic 2.0 is a pure LLM-based system.** Every decision is made by the language model, not by keyword matching or rule-based logic (except as ultimate fallback when LLM is unavailable).

## Key Principle: Trust the LLM

```
User Input → LLM classifies → LLM plans → LLM decides → LLM acts → LLM responds
```

**NO keyword matching at workflow level!**

---

## System Architecture

### High-Level Flow

```
┌─────────────┐
│ User Input  │ Example: "Hello"
└──────┬──────┘
       │
       ↓
┌─────────────────────┐
│   IntentRouter      │ LLM-based classification
│                     │
│ [vLLM Running?]     │
│  ├─ YES → LLM      │ → Classifies as GENERAL (0.95 conf)
│  └─ NO → Fallback  │ → Emergency keyword matching
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Workflow Selection  │
│  ├─ CODING          │ → CodingWorkflow
│  ├─ RESEARCH        │ → ResearchWorkflow
│  ├─ DATA            │ → DataWorkflow
│  └─ GENERAL         │ → GeneralWorkflow ← "Hello" goes here
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ GeneralWorkflow     │
│                     │
│ 1. plan_node()      │ → LLM creates plan
│    ├─ LLM returns:  │    task_type="conversational"
│    └─ Detected!     │
│                     │
│ 2. [Conversational?]│ YES!
│    └─ Generate      │ → LLM generates response
│       response      │    "Hello! I'm Agentic 2.0..."
│                     │
│ 3. Complete ✅      │ → NO tools executed!
└─────────────────────┘
       │
       ↓
┌─────────────────────┐
│ User sees response  │ Natural, contextual greeting
└─────────────────────┘
```

---

## Component Details

### 1. IntentRouter (core/router.py)

**Purpose**: Classify user intent into one of 4 domains

**Primary Method**: LLM-based classification
```python
async def _llm_classify(user_prompt: str) -> IntentClassification:
    # LLM analyzes prompt and returns:
    # - domain: "coding" | "research" | "data" | "general"
    # - confidence: 0.0 - 1.0
    # - reasoning: "Why this domain was chosen"
```

**Fallback Method**: Keyword-based (only if LLM unavailable)
```python
def _fallback_classify(user_prompt: str) -> IntentClassification:
    # Used ONLY when vLLM servers are down
    # Checks greeting keywords, then coding/research/data keywords
    # Returns GENERAL if no match (safe default)
```

**Classification Prompt** (lines 95-102):
```
4. GENERAL: Task management, greetings, and mixed workflows
   - Simple greetings and conversational responses
     (ALWAYS use GENERAL for greetings!)

   Examples: "Hello", "Hi", "Hey", "How are you?"

IMPORTANT: If the input is a simple greeting,
ALWAYS classify as GENERAL with high confidence!
```

### 2. GeneralWorkflow (workflows/general_workflow.py)

**Purpose**: Handle general tasks, greetings, and multi-domain operations

**Plan Node** (plan_node):
```python
async def plan_node(state: AgenticState):
    # 1. Ask LLM to create a plan
    planning_prompt = """
    Task: {user_input}

    Respond in JSON:
    {
      "task_type": "file_organization|system_admin|conversational|...",
      "steps": [...],
      "tools_needed": [...]
    }
    """

    response = await self.call_llm(messages)
    plan = json.loads(response)

    # 2. Check if conversational
    if plan.get('task_type') == 'conversational':
        # Generate natural response with LLM!
        conversation_prompt = f"""
        The user said: "{user_input}"
        Generate a friendly, helpful response.
        """

        response = await self.call_llm(conv_messages, temperature=0.7)
        state["task_result"] = response  # Natural, contextual!
        state["task_status"] = COMPLETED
        state["should_continue"] = False
        return state  # Done! No execute_node!
```

**Key Point**: NO keyword matching! LLM decides if it's conversational.

**Execute Node** (execute_node):
Only runs if task is NOT conversational. For greetings, this never executes.

### 3. CodingWorkflow (workflows/coding_workflow.py)

**Purpose**: Handle code-related tasks

**Previous Approach** (REMOVED ❌):
```python
# DEFENSIVE: Handle simple greetings
if any(keyword in task_lower for keyword in greeting_keywords):
    return "Hello! I'm Agentic 2.0..."  # Hardcoded!
```

**Current Approach** (✅):
```python
# NO defensive checks!
# Trust that IntentRouter classified correctly
# If greeting reaches here, it's a misclassification
# → LLM will still handle it appropriately
```

---

## Decision Flow Examples

### Example 1: Simple Greeting - "Hello"

```
User: "Hello"
  ↓
IntentRouter:
  - LLM prompt includes: "ALWAYS use GENERAL for greetings!"
  - LLM returns: {domain: "general", confidence: 0.95}
  - Log: "✅ Classification: general (confidence: 0.95)"
  ↓
GeneralWorkflow.plan_node():
  - LLM creates plan: {task_type: "conversational", ...}
  - Detects conversational → Generate response
  - LLM prompt: "User said 'Hello', generate friendly response"
  - LLM returns: "Hello! I'm Agentic 2.0, your AI assistant..."
  - state["task_status"] = COMPLETED
  - state["should_continue"] = False
  ↓
Result:
  - NO execute_node called (no tools!)
  - User sees: "Hello! I'm Agentic 2.0, your AI assistant..."
  - Log: "💬 Conversational task detected, generating LLM response"
        "✅ Generated conversational response: Hello! I'm..."
```

### Example 2: Coding Task - "Create calculator.py"

```
User: "Create calculator.py with add, subtract functions"
  ↓
IntentRouter:
  - LLM analyzes: "Create" + "calculator.py" + "functions"
  - LLM returns: {domain: "coding", confidence: 0.92}
  - Log: "✅ Classification: coding (confidence: 0.92)"
  ↓
CodingWorkflow.plan_node():
  - LLM creates detailed plan:
    {steps: ["Write calculator.py", "Add add function", ...]}
  - state["task_status"] = IN_PROGRESS
  ↓
CodingWorkflow.execute_node():
  - Iteration 1: LLM decides action → WRITE_FILE
    - Creates calculator.py with functions
  - Iteration 2: LLM decides action → COMPLETE
    - Task done!
  ↓
Result:
  - Tools executed: WRITE_FILE
  - User sees: File created with code displayed
```

### Example 3: Complex Question - "How do I optimize React performance?"

```
User: "How do I optimize React performance?"
  ↓
IntentRouter:
  - LLM analyzes: Question about technical topic
  - LLM returns: {domain: "research", confidence: 0.88}
  - Log: "✅ Classification: research (confidence: 0.88)"
  ↓
ResearchWorkflow (NOT conversational!):
  - This requires research and analysis
  - Tools may be used: web search, documentation lookup
  ↓
Result:
  - Tools executed: WEB_SEARCH, READ_FILE (docs)
  - User sees: Comprehensive answer with sources
```

---

## Why LLM-First?

### ❌ Keyword-Based Approach (OLD)

**Problems**:
1. **Limited**: Only handles known keywords
2. **Brittle**: "Hello" works, but "Greetings" might not
3. **Hardcoded**: Same response every time
4. **No context**: Can't understand nuance
5. **High maintenance**: Adding new greetings requires code changes

**Example**:
```python
# Hardcoded keyword list
greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이']

if any(keyword in user_input for keyword in greeting_keywords):
    return "Hello! I'm Agentic 2.0..."  # Same response always!
```

What if user says:
- "Good morning!" → Not in list, might fail!
- "Hey there!" → "hey" matches, but response ignores "there"
- "Howdy" → Not in list, misclassified!

### ✅ LLM-Based Approach (NEW)

**Benefits**:
1. **Unlimited**: Handles ANY conversational input
2. **Flexible**: Understands variations and context
3. **Dynamic**: Different response based on input
4. **Intelligent**: Understands nuance and intent
5. **Zero maintenance**: No keyword lists to update

**Example**:
```python
# LLM analyzes ANY input
conversation_prompt = f"""
The user said: "{user_input}"
Generate a friendly, helpful response.
"""

response = await self.call_llm(conv_messages, temperature=0.7)
return response  # Contextual, natural response!
```

Handles:
- "Hello" → "Hello! I'm Agentic 2.0..."
- "Good morning!" → "Good morning! How can I help you today?"
- "Hey there!" → "Hey! I'm ready to assist you..."
- "Howdy" → "Howdy! What can I do for you?"
- "How are you?" → "I'm functioning well, thank you for asking! ..."

---

## Fallback Strategy

### When LLM is Available (Normal Operation)

```
Every decision → LLM
```

- IntentRouter: LLM classification
- Workflow planning: LLM creates plan
- Conversational response: LLM generates response
- Tool decisions: LLM chooses tools
- Completion detection: LLM decides when done

### When LLM is Unavailable (vLLM Servers Down)

```
IntentRouter → Keyword fallback
Workflow → Error message to user
```

**IntentRouter Fallback** (router.py lines 261-273):
```python
def _fallback_classify(user_prompt: str):
    # Check greeting keywords
    greeting_keywords = ['hello', 'hi', 'hey', ...]
    if any(kw in prompt_lower for kw in greeting_keywords):
        return IntentClassification(
            domain=GENERAL,
            confidence=0.95,
            reasoning="Simple greeting detected (rule-based)"
        )

    # Check domain keywords
    # coding_keywords, research_keywords, data_keywords...

    # Default to GENERAL if no match
    return IntentClassification(domain=GENERAL, confidence=0.5)
```

**Workflow Error Handling** (general_workflow.py lines 115-148):
```python
except Exception as e:
    error_msg = str(e)
    if "Connection" in error_msg or "refused" in error_msg:
        user_msg = (
            "🚨 LLM 서버에 연결할 수 없습니다!\n\n"
            "해결 방법:\n"
            "1. vLLM 서버가 실행 중인지 확인하세요\n"
            "2. ./start_vllm.sh 실행\n"
            "3. 30초 대기 후 재시도\n"
        )
    state["task_status"] = FAILED
    state["task_result"] = user_msg
```

**Key Point**: Keyword fallback is ONLY in IntentRouter for emergency classification. Workflows themselves rely purely on LLM.

---

## Testing LLM-First Behavior

### Test 1: Simple Greeting

```bash
# Start system
./start_vllm.sh && sleep 30
python -m cli.app

# Input
> Hello

# Expected logs
✅ Classification: general (confidence: 0.95)
📋 Planning general task: Hello
💬 Conversational task detected, generating LLM response
✅ Generated conversational response: Hello! I'm Agentic 2.0...

# Expected output (natural, may vary)
Hello! I'm Agentic 2.0, your AI assistant specialized in
software development. How can I help you today?

# Should NOT see
❌ "Executing Tools and operations"
❌ "🔧 Executing action: READ_FILE"
❌ Multiple iterations
```

### Test 2: Variation Greetings

```bash
# Test various greetings - all should work!
> Good morning!
> Hey there!
> Howdy!
> What's up?
> How are you?

# All should:
✅ Classify as GENERAL
✅ Detect as conversational
✅ Generate appropriate LLM response
✅ NO tool execution
```

### Test 3: LLM Unavailable (Fallback Test)

```bash
# Stop vLLM servers
./stop_vllm.sh

# Run CLI
python -m cli.app

# Input
> Hello

# Expected logs
❌ LLM classification failed: Connection refused
🔄 Falling back to rule-based classification
👋 Detected greeting in fallback: 'Hello'
🔧 Fallback classification: general (confidence: 0.95)
❌ Planning error: Connection refused

# Expected output
🚨 LLM 서버에 연결할 수 없습니다!

해결 방법:
1. vLLM 서버가 실행 중인지 확인하세요
2. ./start_vllm.sh 실행
3. 30초 대기 후 재시도
```

---

## Architecture Benefits

### 1. Intelligence
- LLM understands context, nuance, variations
- Handles inputs you never anticipated
- Natural, human-like responses

### 2. Maintainability
- No keyword lists to update
- No hardcoded responses
- Changes to behavior = changes to prompts only

### 3. Scalability
- Adding new languages: Just update prompts
- New conversational patterns: LLM handles automatically
- New domains: Add to classification prompt

### 4. Consistency
- All decisions follow same pattern: "Ask LLM"
- Single source of truth: LLM
- Predictable behavior: Trust the model

### 5. Testability
- Test prompts, not keywords
- Test LLM responses, not hardcoded strings
- Test fallback behavior separately

---

## Summary

**Core Principle**:
```
LLM makes ALL decisions. Keyword matching is ONLY for emergency fallback.
```

**"Hello" Flow**:
```
Input → LLM classifies as GENERAL → LLM plans as conversational
→ LLM generates response → User sees natural greeting → Done!
(No tools executed!)
```

**Why This Matters**:
- Follows system design philosophy (LLM-first)
- More intelligent and flexible
- Easier to maintain and extend
- Better user experience

**When Keyword Matching is OK**:
- IntentRouter fallback (vLLM down)
- Ultimate fallback responses (LLM fails)

**When Keyword Matching is WRONG**:
- Workflow decision logic
- Hardcoded responses at workflow level
- Replacing LLM judgment

---

**Last Updated**: 2026-01-16
**Branch**: claude/fix-hardcoded-config-QyiND
**Philosophy**: LLM-First, Trust the Model
