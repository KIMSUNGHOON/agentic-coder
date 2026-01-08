"""Calculator module for testing CLI preview

This is a simple calculator implementation to test the CLI's
syntax highlighting and preview functionality.
"""


def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a"""
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b


def divide(a: float, b: float) -> float:
    """Divide a by b"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


class Calculator:
    """Simple calculator class"""

    def __init__(self):
        self.history = []

    def calculate(self, operation: str, a: float, b: float) -> float:
        """Perform calculation and store in history"""
        operations = {
            'add': add,
            'subtract': subtract,
            'multiply': multiply,
            'divide': divide
        }

        if operation not in operations:
            raise ValueError(f"Unknown operation: {operation}")

        result = operations[operation](a, b)
        self.history.append((operation, a, b, result))
        return result

    def get_history(self) -> list:
        """Get calculation history"""
        return self.history


if __name__ == "__main__":
    calc = Calculator()
    print(f"2 + 3 = {calc.calculate('add', 2, 3)}")
    print(f"10 - 4 = {calc.calculate('subtract', 10, 4)}")
    print(f"5 * 6 = {calc.calculate('multiply', 5, 6)}")
    print(f"20 / 4 = {calc.calculate('divide', 20, 4)}")
