"""Explicit offline commands. Never evaluate Python or execute shell commands."""
import ast
import math
import operator
from datetime import datetime

HELP = '''Offline commands (no API key needed):
/help — show commands
/time — current local date and time
/calc (12 + 8) * 3 — arithmetic (+ - * / // % **)
/task add Finish ICT homework — save a task
/tasks — list unfinished tasks
/task done 1 — complete a task by ID
/status — provider and memory information
/clear — clear saved conversation (tasks are kept)'''


def calculate(expression):
    if len(expression) > 200:
        raise ValueError('Expression is too long.')
    tree = ast.parse(expression, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError('Expression is too complex.')
    binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
              ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
              ast.Mod: operator.mod, ast.Pow: operator.pow}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in binary:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError('Exponent must be between -100 and 100.')
            value = binary[type(node.op)](left, right)
        else:
            raise ValueError('Only numbers and arithmetic operators are allowed.')
        if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError('Result is outside the supported range.')
        return value

    return visit(tree.body)


def run_command(message, store):
    command, _, argument = message.partition(' ')
    command, argument = command.lower(), argument.strip()
    if command == '/help':
        return HELP
    if command == '/time':
        return datetime.now().astimezone().strftime('%A, %d %B %Y, %H:%M:%S %Z')
    if command == '/calc':
        try:
            return str(calculate(argument))
        except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, RecursionError):
            return 'Invalid calculation. Use numbers and + - * / // % ** with parentheses; keep values below 1e100 and exponents within ±100.'
    if command == '/tasks':
        return '\n'.join(f'{key}. {text}' for key, text in store.tasks()) or 'No unfinished tasks.'
    if command == '/task':
        action, _, value = argument.partition(' ')
        value = value.strip()
        if action.lower() == 'add' and value:
            return f'Task #{store.add_task(value)} saved: {value}'
        if action.lower() == 'done' and value.isascii() and value.isdigit() and len(value) < 19:
            return 'Task completed.' if store.complete_task(int(value)) else 'No unfinished task with that ID.'
        return 'Use /task add <description> or /task done <ID>.'
    if message.startswith('/'):
        return 'Unknown command. Type /help for available commands.'
    return None
