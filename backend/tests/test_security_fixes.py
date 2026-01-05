"""Test Security Auto-Fix Logic

This module tests the OWASP Top 10 security fixes implemented in refiner.py.
Run with: pytest backend/tests/test_security_fixes.py -v
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.agent.langgraph.nodes.refiner import (
    _apply_fix_heuristic,
    _fix_sql_injection,
    _fix_command_injection,
    _fix_xss,
    _fix_path_traversal,
    _fix_hardcoded_credentials,
    _fix_insecure_deserialization,
    _fix_input_validation,
    _fix_eval_exec,
)


class TestSQLInjectionFix:
    """Test SQL injection vulnerability fixes"""

    def test_fstring_sql_detected(self):
        """F-string SQL should be flagged"""
        code = '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
'''
        fixed = _fix_sql_injection(code)
        assert "SECURITY WARNING" in fixed
        assert "SQL injection" in fixed

    def test_format_sql_detected(self):
        """String.format() SQL should be flagged"""
        code = '''
query = "SELECT * FROM users WHERE name = '{}'".format(name)
'''
        fixed = _fix_sql_injection(code)
        assert "TODO: Fix SQL injection" in fixed

    def test_concat_sql_detected(self):
        """String concatenation SQL should be flagged"""
        code = '''
query = "SELECT * FROM users WHERE id = " + user_id
'''
        fixed = _fix_sql_injection(code)
        assert "string concatenation" in fixed

    def test_parameterized_query_unchanged(self):
        """Parameterized queries should not be flagged"""
        code = '''
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
'''
        fixed = _fix_sql_injection(code)
        assert "SECURITY WARNING" not in fixed


class TestCommandInjectionFix:
    """Test command injection vulnerability fixes"""

    def test_os_system_fixed(self):
        """os.system() should be converted to subprocess"""
        code = '''
import os
os.system("ls -la")
'''
        fixed = _fix_command_injection(code)
        assert "subprocess.run" in fixed or "DISABLED" in fixed

    def test_shell_true_fixed(self):
        """shell=True should be changed to shell=False"""
        code = '''
subprocess.run(cmd, shell=True)
'''
        fixed = _fix_command_injection(code)
        assert "shell=False" in fixed

    def test_eval_fixed(self):
        """eval() should be changed to ast.literal_eval()"""
        code = '''
result = eval(user_input)
'''
        fixed = _fix_command_injection(code)
        assert "ast.literal_eval" in fixed
        assert "import ast" in fixed


class TestXSSFix:
    """Test Cross-Site Scripting vulnerability fixes"""

    def test_innerhtml_flagged(self):
        """innerHTML usage should be flagged"""
        code = '''
element.innerHTML = user_input
'''
        fixed = _fix_xss(code)
        assert "XSS" in fixed or "escape" in fixed

    def test_safe_filter_flagged(self):
        """Jinja2 |safe filter should be flagged"""
        code = '''
{{ user_input|safe }}
'''
        fixed = _fix_xss(code)
        assert "sanitized" in fixed or "XSS" in fixed


class TestPathTraversalFix:
    """Test path traversal vulnerability fixes"""

    def test_open_with_variable_flagged(self):
        """open() with variable path should be flagged"""
        code = '''
with open(user_path + "/file.txt") as f:
    data = f.read()
'''
        fixed = _fix_path_traversal(code)
        assert "directory traversal" in fixed or "Validate path" in fixed


class TestHardcodedCredentialsFix:
    """Test hardcoded credentials vulnerability fixes"""

    def test_password_fixed(self):
        """Hardcoded password should use environment variable"""
        code = '''
password = "secret123"
'''
        fixed = _fix_hardcoded_credentials(code)
        assert "os.environ.get" in fixed
        assert "import os" in fixed

    def test_api_key_fixed(self):
        """Hardcoded API key should use environment variable"""
        code = '''
api_key = "sk-1234567890"
'''
        fixed = _fix_hardcoded_credentials(code)
        assert "os.environ.get" in fixed


class TestInsecureDeserializationFix:
    """Test insecure deserialization vulnerability fixes"""

    def test_pickle_flagged(self):
        """pickle.load() should be flagged"""
        code = '''
import pickle
data = pickle.load(file)
'''
        fixed = _fix_insecure_deserialization(code)
        assert "arbitrary code" in fixed or "TODO" in fixed

    def test_yaml_load_fixed(self):
        """yaml.load() should be changed to yaml.safe_load()"""
        code = '''
import yaml
data = yaml.load(file)
'''
        fixed = _fix_insecure_deserialization(code)
        assert "safe_load" in fixed


class TestInputValidationFix:
    """Test input validation fixes"""

    def test_function_gets_validation(self):
        """Function parameters should get validation"""
        code = '''
def process_data(user_input, count):
    return user_input * count
'''
        fixed = _fix_input_validation(code)
        assert "Input validation" in fixed
        assert "is None" in fixed


class TestEvalExecFix:
    """Test eval/exec vulnerability fixes"""

    def test_eval_fixed(self):
        """eval() should be changed to ast.literal_eval()"""
        code = '''
result = eval(expression)
'''
        fixed = _fix_eval_exec(code)
        assert "ast.literal_eval" in fixed

    def test_exec_flagged(self):
        """exec() should be flagged for review"""
        code = '''
exec(code_string)
'''
        fixed = _fix_eval_exec(code)
        assert "TODO" in fixed or "WARNING" in fixed


class TestHeuristicDispatch:
    """Test the main heuristic dispatch function"""

    def test_sql_injection_issue(self):
        """SQL injection issue should trigger SQL fix"""
        code = '''query = f"SELECT * FROM users WHERE id = {id}"'''
        fixed = _apply_fix_heuristic(code, "SQL injection vulnerability found")
        assert "SECURITY WARNING" in fixed

    def test_command_injection_issue(self):
        """Command injection issue should trigger command fix"""
        code = '''os.system(cmd)'''
        fixed = _apply_fix_heuristic(code, "Command injection risk with os.system")
        assert "subprocess" in fixed or "DISABLED" in fixed

    def test_hardcoded_password_issue(self):
        """Hardcoded password issue should trigger credential fix"""
        code = '''password = "admin123"'''
        fixed = _apply_fix_heuristic(code, "Hardcoded password detected")
        assert "os.environ" in fixed

    def test_generic_security_issue(self):
        """Generic security issue should apply multiple fixes"""
        code = '''
os.system(cmd)
query = f"SELECT * FROM users"
'''
        fixed = _apply_fix_heuristic(code, "Security vulnerability")
        # Should apply multiple fixes
        assert fixed != code


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
