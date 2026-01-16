"""Prompt Engineering for GPT-OSS-120B

Optimized prompts for GPT-OSS-120B model with:
- Few-shot examples (OpenAI Cookbook best practices)
- Chain-of-Thought reasoning with <think> tags
- Structured outputs (JSON Schema with strict=true)
- Clear constraints and guidelines

Key Features:
- GPT-OSS-120B supports CoT with <think> tags
- Adjustable reasoning effort (low/medium/high)
- Structured outputs guarantee valid JSON
- Tool integration for enhanced capabilities

References:
- OpenAI Cookbook: https://cookbook.openai.com/
- GPT-OSS: https://github.com/openai/gpt-oss
- Structured Outputs: https://cookbook.openai.com/examples/structured_outputs_intro

Security: All prompts and responses are stored locally only.
"""

from typing import List, Dict, Any


class PromptTemplate:
    """Base class for prompt templates"""

    @staticmethod
    def format_system_message(role: str, constraints: List[str] = None) -> str:
        """Create structured system message

        Args:
            role: Role description (e.g., "senior software engineer")
            constraints: List of constraints/rules to follow

        Returns:
            Formatted system message
        """
        base = f"You are a {role}.\n\n"

        if constraints:
            base += "Follow these rules:\n"
            for i, constraint in enumerate(constraints, 1):
                base += f"{i}. {constraint}\n"

        return base.strip()

    @staticmethod
    def format_few_shot_examples(examples: List[Dict[str, str]]) -> str:
        """Format few-shot examples

        Args:
            examples: List of {"input": ..., "output": ...} dicts

        Returns:
            Formatted examples string
        """
        formatted = "Here are examples:\n\n"

        for i, ex in enumerate(examples, 1):
            formatted += f"Example {i}:\n"
            formatted += f"Input: {ex['input']}\n"
            formatted += f"Output: {ex['output']}\n\n"

        return formatted

    @staticmethod
    def format_json_schema(schema: Dict[str, Any]) -> str:
        """Format JSON schema description

        Args:
            schema: Dictionary describing expected JSON structure

        Returns:
            Formatted schema string
        """
        import json
        return f"Respond with JSON matching this structure:\n```json\n{json.dumps(schema, indent=2)}\n```"


class CodingPrompts:
    """Prompts for coding workflow"""

    @staticmethod
    def planning_prompt(task: str, workspace: str, context: Dict = None) -> List[Dict[str, str]]:
        """Generate planning prompt for coding task

        Args:
            task: Task description
            workspace: Workspace path
            context: Additional context

        Returns:
            Messages list with system and user messages
        """
        system_message = PromptTemplate.format_system_message(
            role="expert software engineer specializing in code architecture and planning",
            constraints=[
                "Think step-by-step before providing your analysis",
                "Be specific about file names and approaches",
                "Consider edge cases and potential issues",
                "Respond ONLY with valid JSON - no additional text",
            ]
        )

        # Few-shot examples
        examples = [
            {
                "input": "Create a REST API endpoint for user authentication",
                "output": """{
  "reasoning": "Need user model, authentication endpoint, JWT tokens, and password hashing",
  "approach": "FastAPI with SQLAlchemy ORM and JWT authentication",
  "steps": [
    "Create database models for User",
    "Implement password hashing with bcrypt",
    "Create authentication endpoints (login, register)",
    "Add JWT token generation and validation",
    "Write unit tests for auth flow"
  ],
  "files_to_modify": ["models/user.py", "routes/auth.py", "utils/security.py", "tests/test_auth.py"],
  "dependencies": ["fastapi", "sqlalchemy", "python-jose", "passlib"],
  "risks": ["Password storage security", "Token expiration handling"]
}"""
            }
        ]

        json_schema = {
            "reasoning": "string - Your step-by-step analysis",
            "approach": "string - High-level approach",
            "steps": ["string - Specific step 1", "string - Specific step 2", "..."],
            "files_to_modify": ["string - file path"],
            "dependencies": ["string - package name"],
            "risks": ["string - potential issue"]
        }

        user_prompt = f"""Task: {task}
Workspace: {workspace}

{PromptTemplate.format_few_shot_examples(examples)}

{PromptTemplate.format_json_schema(json_schema)}

Now analyze this task and provide your plan:"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ]

    @staticmethod
    def execution_prompt(
        task: str,
        plan: Dict,
        current_step: int,
        previous_actions: List[Dict] = None
    ) -> List[Dict[str, str]]:
        """Generate execution prompt

        Args:
            task: Task description
            plan: Execution plan
            current_step: Current step number
            previous_actions: List of previous actions taken

        Returns:
            Messages list
        """
        import json

        system_message = PromptTemplate.format_system_message(
            role="expert software engineer executing code changes",
            constraints=[
                "Execute ONE action at a time",
                "Think about the current step before acting",
                "Verify your action is correct for the current goal",
                "Respond ONLY with valid JSON - no additional text",
            ]
        )

        examples = [
            {
                "input": "Step 1: Create a simple calculator file",
                "output": """{
  "reasoning": "Need to create calculator.py with basic arithmetic functions - this completes the task",
  "action": "WRITE_FILE",
  "parameters": {
    "file_path": "calculator.py",
    "content": "def add(a, b):\\n    return a + b\\n\\ndef subtract(a, b):\\n    return a - b\\n\\ndef multiply(a, b):\\n    return a * b\\n\\ndef divide(a, b):\\n    if b == 0:\\n        raise ValueError('Cannot divide by zero')\\n    return a / b"
  },
  "next_step": "Use COMPLETE action"
}"""
            },
            {
                "input": "Step 2: File created, task is done",
                "output": """{
  "reasoning": "Calculator file created successfully with all required functions, task is finished",
  "action": "COMPLETE",
  "parameters": {
    "summary": "Created calculator.py with add, subtract, multiply, and divide functions"
  },
  "next_step": "Task complete"
}"""
            }
        ]

        # Available actions (UPPERCASE - CRITICAL!)
        available_actions = """
        Available actions (use UPPERCASE):
        - READ_FILE: Read file contents
          Parameters: {"file_path": "path/to/file.py"}

        - WRITE_FILE: Write or create file
          Parameters: {"file_path": "path/to/file.py", "content": "file contents"}

        - LIST_DIRECTORY: List directory contents
          Parameters: {"path": ".", "recursive": false}

        - SEARCH_CODE: Search for pattern in code
          Parameters: {"pattern": "search term", "file_pattern": "*.py"}

        - RUN_TESTS: Run tests
          Parameters: {"test_path": "tests/"}

        - GIT_STATUS: Check git status
          Parameters: {}

        - COMPLETE: Task is finished ⚠️ USE THIS WHEN DONE!
          Parameters: {"summary": "What was accomplished"}

        🚨 CRITICAL: Use COMPLETE as soon as task is done!
        - After creating a file → COMPLETE
        - After making changes → COMPLETE
        - Don't keep working unnecessarily → COMPLETE
        """

        json_schema = {
            "reasoning": "string - Why you chose this action",
            "action": "string - UPPERCASE action name (READ_FILE, WRITE_FILE, LIST_DIRECTORY, SEARCH_CODE, RUN_TESTS, GIT_STATUS, or COMPLETE)",
            "parameters": {
                "param_name": "param_value - Specific to the action"
            },
            "next_step": "string - What to do after (or 'Task complete' if using COMPLETE)"
        }

        previous_actions_str = (
            f"\n\nPrevious actions:\n{json.dumps(previous_actions[-5:], indent=2)}"
            if previous_actions
            else ""
        )

        user_prompt = f"""Task: {task}

Plan: {json.dumps(plan, indent=2)}

Current Step: {current_step + 1}/{len(plan.get('steps', []))}
Step Description: {plan.get('steps', [])[current_step] if current_step < len(plan.get('steps', [])) else 'Final step'}
{previous_actions_str}

{available_actions}

{PromptTemplate.format_few_shot_examples(examples)}

{PromptTemplate.format_json_schema(json_schema)}

Think step-by-step:
1. What is the current goal?
2. What action will accomplish this goal?
3. Are you DONE? Then use COMPLETE action!
4. What are the exact parameters?

Now provide your next action:"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ]


class ResearchPrompts:
    """Prompts for research workflow"""

    @staticmethod
    def query_formulation_prompt(task: str) -> List[Dict[str, str]]:
        """Generate query formulation prompt"""
        system_message = PromptTemplate.format_system_message(
            role="expert research analyst",
            constraints=[
                "Break down complex topics into searchable queries",
                "Consider multiple perspectives",
                "Prioritize reliable sources",
                "Respond ONLY with valid JSON",
            ]
        )

        examples = [
            {
                "input": "Research best practices for microservices architecture",
                "output": """{
  "reasoning": "Microservices is broad - need queries for patterns, communication, deployment, testing",
  "queries": [
    "microservices architecture patterns 2026",
    "microservices communication best practices REST vs gRPC",
    "microservices deployment strategies kubernetes docker",
    "microservices testing patterns integration tests"
  ],
  "focus_areas": ["Architecture patterns", "Inter-service communication", "Deployment", "Testing strategies"],
  "expected_sources": ["technical blogs", "documentation", "case studies"]
}"""
            }
        ]

        json_schema = {
            "reasoning": "string - Your analysis of what to research",
            "queries": ["string - Specific search query"],
            "focus_areas": ["string - Topic area"],
            "expected_sources": ["string - Source type"]
        }

        user_prompt = f"""Research Task: {task}

{PromptTemplate.format_few_shot_examples(examples)}

{PromptTemplate.format_json_schema(json_schema)}

Formulate research queries:"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ]


class DataPrompts:
    """Prompts for data analysis workflow"""

    @staticmethod
    def analysis_prompt(task: str, data_summary: Dict) -> List[Dict[str, str]]:
        """Generate data analysis prompt"""
        import json

        system_message = PromptTemplate.format_system_message(
            role="expert data analyst with strong statistical knowledge",
            constraints=[
                "Focus on meaningful insights, not just descriptions",
                "Suggest appropriate visualizations",
                "Consider data quality and limitations",
                "Respond ONLY with valid JSON",
            ]
        )

        examples = [
            {
                "input": "Analyze sales data: 10000 rows, columns: date, product, revenue, quantity",
                "output": """{
  "reasoning": "Sales data over time - look for trends, seasonality, top products",
  "analysis_steps": [
    "Calculate revenue trends over time",
    "Identify top-selling products",
    "Analyze seasonality patterns",
    "Compute average order value",
    "Find correlations between product categories"
  ],
  "visualizations": [
    {"type": "line_chart", "data": "revenue_over_time", "title": "Revenue Trend"},
    {"type": "bar_chart", "data": "top_products", "title": "Top 10 Products"},
    {"type": "heatmap", "data": "monthly_seasonality", "title": "Seasonal Patterns"}
  ],
  "insights_to_find": [
    "Growth rate",
    "Peak sales periods",
    "Product performance",
    "Revenue distribution"
  ]
}"""
            }
        ]

        json_schema = {
            "reasoning": "string - Your analytical approach",
            "analysis_steps": ["string - Specific analysis to perform"],
            "visualizations": [
                {
                    "type": "string - chart type",
                    "data": "string - data to visualize",
                    "title": "string - chart title"
                }
            ],
            "insights_to_find": ["string - Key insight to look for"]
        }

        user_prompt = f"""Task: {task}

Data Summary: {json.dumps(data_summary, indent=2)}

{PromptTemplate.format_few_shot_examples(examples)}

{PromptTemplate.format_json_schema(json_schema)}

Plan your analysis:"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ]


class AgentPrompts:
    """Prompts for sub-agent operations"""

    @staticmethod
    def task_decomposition_prompt(task: str, context: Dict = None) -> List[Dict[str, str]]:
        """Generate task decomposition prompt"""
        import json

        system_message = PromptTemplate.format_system_message(
            role="expert project manager skilled at breaking down complex tasks",
            constraints=[
                "Analyze task complexity carefully",
                "Break into independent subtasks when possible",
                "Assign appropriate agent types",
                "Consider dependencies between subtasks",
                "Respond ONLY with valid JSON",
            ]
        )

        examples = [
            {
                "input": "Build a complete web application with user authentication",
                "output": """{
  "reasoning": "Large task requiring frontend, backend, database, and testing - can parallelize frontend and backend",
  "complexity": "COMPLEX",
  "requires_decomposition": true,
  "subtasks": [
    {
      "description": "Design and implement database schema for users",
      "agent_type": "code_writer",
      "estimated_complexity": "MODERATE",
      "dependencies": []
    },
    {
      "description": "Create backend REST API with authentication endpoints",
      "agent_type": "code_writer",
      "estimated_complexity": "COMPLEX",
      "dependencies": ["subtask_0"]
    },
    {
      "description": "Build frontend login and registration UI",
      "agent_type": "code_writer",
      "estimated_complexity": "MODERATE",
      "dependencies": []
    },
    {
      "description": "Write integration tests for auth flow",
      "agent_type": "code_tester",
      "estimated_complexity": "MODERATE",
      "dependencies": ["subtask_1", "subtask_2"]
    }
  ],
  "execution_strategy": "MIXED",
  "reasoning_for_strategy": "Subtasks 0,2 can run in parallel, then 1, then 3 depends on 1 and 2"
}"""
            }
        ]

        json_schema = {
            "reasoning": "string - Your analysis of the task",
            "complexity": "string - SIMPLE, MODERATE, or COMPLEX",
            "requires_decomposition": "boolean",
            "subtasks": [
                {
                    "description": "string - Clear subtask description",
                    "agent_type": "string - code_reader/writer/tester, data_loader/analyzer/visualizer, etc",
                    "estimated_complexity": "string - SIMPLE, MODERATE, or COMPLEX",
                    "dependencies": ["string - subtask indices this depends on"]
                }
            ],
            "execution_strategy": "string - PARALLEL, SEQUENTIAL, or MIXED",
            "reasoning_for_strategy": "string - Why this strategy"
        }

        context_str = f"\n\nContext: {json.dumps(context, indent=2)}" if context else ""

        user_prompt = f"""Task: {task}{context_str}

{PromptTemplate.format_few_shot_examples(examples)}

{PromptTemplate.format_json_schema(json_schema)}

Analyze and decompose this task:"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ]
