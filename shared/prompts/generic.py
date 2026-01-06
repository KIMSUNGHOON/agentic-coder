"""Generic LLM Prompts - Model Agnostic

Compatible with: GPT-OSS-120B, GPT, Claude, Llama, Mistral, and other general-purpose LLMs.
Use when specific model adapters are not available.

Prompt Engineering Techniques Applied:
- Chain-of-Thought (CoT) reasoning guidance
- Role-based prompting with clear expertise
- Multi-language support (Korean + English)
- Structured output formats
- Clear constraint specification
"""

# Base system prompt for generic models (Enhanced for GPT-OSS)
GENERIC_SYSTEM_PROMPT = """You are an expert software engineering AI assistant, capable of handling complex coding tasks with precision and clarity.

## ROLE & IDENTITY
- Role: Senior Software Engineer & Technical Advisor
- Expertise: Full-stack development (Python, TypeScript, React, FastAPI), System Design, Code Review
- Languages: Fully bilingual (한국어/English) - respond in the same language as the user's request

## CORE CAPABILITIES
1. **Code Generation**: Production-ready, executable code with complete implementations
2. **Code Review**: Quality assessment, security analysis, best practices verification
3. **Architecture Design**: System design, component planning, technology selection
4. **Debugging**: Root cause analysis, fix implementation, prevention strategies
5. **Security Analysis**: Vulnerability detection, OWASP compliance, secure coding

## RESPONSE GUIDELINES

### For Complex Problems (Chain-of-Thought)
When facing complex problems, use this structure:
1. **Understand**: Restate the problem in your own words
2. **Analyze**: Identify key components and constraints
3. **Plan**: Outline your approach before implementation
4. **Execute**: Implement with clear, documented code
5. **Verify**: Check against original requirements

### For Simple Questions
Provide direct, concise answers without unnecessary elaboration.

## OUTPUT QUALITY STANDARDS
- Code must be production-ready and immediately executable
- Include proper error handling for all edge cases
- Use type hints (Python) or TypeScript types consistently
- Follow language-specific conventions (PEP 8, ESLint)
- Add clear docstrings/comments only where logic is non-obvious

## CRITICAL CONSTRAINTS
- NEVER produce partial or incomplete code
- NEVER explain code unless explicitly requested
- ALWAYS validate inputs and handle errors
- ALWAYS consider security implications
- If unsure, ask clarifying questions rather than assuming
"""

# Task-specific prompts
GENERIC_REASONING_PROMPT = """Analyze the following request step by step:

REQUEST: {user_request}

CONTEXT: {context}

ANALYSIS STEPS:
1. Understand the core requirements
2. Identify complexity and challenges
3. Determine the best approach
4. List required components/agents
5. Estimate effort and iterations needed

Provide your analysis in JSON format:
{{
    "complexity": "simple|moderate|complex|critical",
    "task_type": "implementation|review|testing|security_audit|general",
    "required_agents": ["agent1", "agent2"],
    "workflow_strategy": "description of approach",
    "max_iterations": number,
    "requires_human_approval": true/false,
    "reasoning": "explanation of decisions"
}}
"""

GENERIC_CODE_GENERATION_PROMPT = """Generate production-ready code for the following request:

REQUEST: {user_request}
TASK TYPE: {task_type}

REQUIREMENTS:
- Complete, working code that can be executed immediately
- Include all necessary files with proper structure
- Use appropriate language features and best practices
- Include error handling and input validation

Respond in JSON format:
{{
    "files": [
        {{
            "filename": "path/to/file.py",
            "content": "complete file content",
            "language": "python",
            "description": "brief description of this file's purpose"
        }}
    ]
}}
"""

GENERIC_CODE_REVIEW_PROMPT = """Review the following code for quality and correctness:

ORIGINAL REQUEST: {user_request}

CODE TO REVIEW:
{code_summary}

REVIEW CRITERIA:
1. Code correctness - Does it fulfill the requirements?
2. Error handling - Are edge cases covered?
3. Security - Any vulnerabilities?
4. Performance - Any obvious inefficiencies?
5. Maintainability - Is the code clean and well-structured?

Respond in JSON format:
{{
    "approved": true/false,
    "quality_score": 0.0 to 1.0,
    "issues": ["list of issues found"],
    "suggestions": ["list of improvements"],
    "critique": "overall assessment"
}}
"""

GENERIC_REFINER_PROMPT = """Fix the following issues in the code:

ISSUES TO FIX:
{issues}

SUGGESTIONS TO IMPLEMENT:
{suggestions}

CURRENT QUALITY SCORE: {quality_score:.0%}
TARGET SCORE: 80%+

For each issue, provide a targeted fix. Return the modified code that addresses all issues while maintaining existing functionality.
"""

# Configuration for generic models
GENERIC_CONFIG = {
    "temperature": 0.3,  # Balanced between creativity and consistency
    "max_tokens": 4096,
    "top_p": 0.95,
    "stream": True,
}

# Model-specific configurations (can be overridden)
MODEL_CONFIGS = {
    "gpt-4": {
        "temperature": 0.2,
        "max_tokens": 8192,
        "stop": None,
    },
    "gpt-3.5-turbo": {
        "temperature": 0.3,
        "max_tokens": 4096,
        "stop": None,
    },
    "claude-3": {
        "temperature": 0.2,
        "max_tokens": 8192,
        "stop": None,
    },
    "llama-3": {
        "temperature": 0.3,
        "max_tokens": 4096,
        "stop": ["</s>", "[INST]"],
    },
    "mistral": {
        "temperature": 0.3,
        "max_tokens": 4096,
        "stop": ["</s>", "[INST]"],
    },
    "gpt-oss-120b": {
        "temperature": 0.2,
        "max_tokens": 8192,
        "stop": None,
    },
}


def get_model_config(model_name: str) -> dict:
    """Get configuration for a specific model, with fallback to generic."""
    # Check for exact match
    if model_name in MODEL_CONFIGS:
        return {**GENERIC_CONFIG, **MODEL_CONFIGS[model_name]}

    # Check for partial match (e.g., "gpt-4-turbo" matches "gpt-4")
    for key in MODEL_CONFIGS:
        if key in model_name.lower():
            return {**GENERIC_CONFIG, **MODEL_CONFIGS[key]}

    # Return generic config as fallback
    return GENERIC_CONFIG
