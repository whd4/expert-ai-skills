"""Safe expression evaluator for Monte Carlo outcome formulas.

Specs can contain expressions like "revenue - cost" or "hours * rate".
We parse them as Python AST but only allow a whitelist of node types,
so untrusted specs cannot execute arbitrary code.

Supported:
  - Arithmetic: + - * / // % ** (unary +/-)
  - Comparison: == != < <= > >= (returns 1.0 for True, 0.0 for False)
  - Boolean: and, or, not (short-circuit on truthiness)
  - Function calls from whitelist: min, max, abs, round, sqrt, log, exp, floor, ceil
  - If-expressions: `a if cond else b`
  - Names resolving to variables provided by the caller
"""
from __future__ import annotations

import ast
import math
from typing import Any

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


_ALLOWED_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Constant, ast.Name, ast.Load, ast.Call, ast.IfExp,
    # Operators
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
}


def _fn_sqrt(x):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.sqrt(np.abs(x))
    return math.sqrt(abs(x))


def _fn_log(x):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.log(np.maximum(x, 1e-300))
    return math.log(max(x, 1e-300))


def _fn_exp(x):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.exp(np.minimum(x, 700.0))
    return math.exp(min(x, 700.0))


def _fn_min(*args):
    if HAS_NUMPY and any(isinstance(a, np.ndarray) for a in args):
        return np.minimum.reduce([np.asarray(a) for a in args])
    if any(isinstance(a, list) for a in args):
        n = max(len(a) for a in args if isinstance(a, list))
        arrs = [a if isinstance(a, list) else [a] * n for a in args]
        return [min(vals) for vals in zip(*arrs)]
    return min(args)


def _fn_max(*args):
    if HAS_NUMPY and any(isinstance(a, np.ndarray) for a in args):
        return np.maximum.reduce([np.asarray(a) for a in args])
    if any(isinstance(a, list) for a in args):
        n = max(len(a) for a in args if isinstance(a, list))
        arrs = [a if isinstance(a, list) else [a] * n for a in args]
        return [max(vals) for vals in zip(*arrs)]
    return max(args)


def _fn_abs(x):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.abs(x)
    return abs(x)


def _fn_round(x, ndigits=0):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.round(x, int(ndigits))
    return round(x, int(ndigits))


def _fn_floor(x):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.floor(x)
    return math.floor(x)


def _fn_ceil(x):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.ceil(x)
    return math.ceil(x)


def _fn_clip(x, lo, hi):
    if HAS_NUMPY and isinstance(x, np.ndarray):
        return np.clip(x, lo, hi)
    return max(lo, min(hi, x))


_FUNCTIONS = {
    "min": _fn_min, "max": _fn_max, "abs": _fn_abs, "round": _fn_round,
    "sqrt": _fn_sqrt, "log": _fn_log, "exp": _fn_exp,
    "floor": _fn_floor, "ceil": _fn_ceil, "clip": _fn_clip,
}


def _validate(node):
    for child in ast.walk(node):
        if type(child) not in _ALLOWED_NODES:
            raise ValueError(f"disallowed expression node: {type(child).__name__}")
        if isinstance(child, ast.Call):
            if not isinstance(child.func, ast.Name) or child.func.id not in _FUNCTIONS:
                name = getattr(child.func, 'id', type(child.func).__name__)
                raise ValueError(f"disallowed function call: {name!r}")
        if isinstance(child, ast.Constant) and not isinstance(child.value, (int, float, bool)):
            raise ValueError(f"only numeric/bool constants allowed, got {type(child.value).__name__}")


def _eval(node, variables):
    if isinstance(node, ast.Expression):
        return _eval(node.body, variables)
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, bool):
            return 1.0 if val else 0.0
        return val
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"unknown variable: {node.id!r}")
        return variables[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, variables)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            if HAS_NUMPY and isinstance(operand, np.ndarray):
                return (operand == 0).astype(float)
            return 1.0 if not operand else 0.0
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, variables)
        right = _eval(node.right, variables)
        op = node.op
        # NumPy arrays handle element-wise ops natively
        if HAS_NUMPY and (isinstance(left, np.ndarray) or isinstance(right, np.ndarray)):
            if isinstance(op, ast.Add): return left + right
            if isinstance(op, ast.Sub): return left - right
            if isinstance(op, ast.Mult): return left * right
            if isinstance(op, ast.Div): return left / right
            if isinstance(op, ast.FloorDiv): return left // right
            if isinstance(op, ast.Mod): return left % right
            if isinstance(op, ast.Pow): return left ** right
        # Pure Python fallback: element-wise for lists
        if isinstance(left, list) or isinstance(right, list):
            left_arr = left if isinstance(left, list) else [left] * len(right)
            right_arr = right if isinstance(right, list) else [right] * len(left)
            if isinstance(op, ast.Add): return [a + b for a, b in zip(left_arr, right_arr)]
            if isinstance(op, ast.Sub): return [a - b for a, b in zip(left_arr, right_arr)]
            if isinstance(op, ast.Mult): return [a * b for a, b in zip(left_arr, right_arr)]
            if isinstance(op, ast.Div): return [a / b for a, b in zip(left_arr, right_arr)]
            if isinstance(op, ast.FloorDiv): return [a // b for a, b in zip(left_arr, right_arr)]
            if isinstance(op, ast.Mod): return [a % b for a, b in zip(left_arr, right_arr)]
            if isinstance(op, ast.Pow): return [a ** b for a, b in zip(left_arr, right_arr)]
        # Scalars: direct operation
        if isinstance(op, ast.Add): return left + right
        if isinstance(op, ast.Sub): return left - right
        if isinstance(op, ast.Mult): return left * right
        if isinstance(op, ast.Div): return left / right
        if isinstance(op, ast.FloorDiv): return left // right
        if isinstance(op, ast.Mod): return left % right
        if isinstance(op, ast.Pow): return left ** right
    if isinstance(node, ast.Compare):
        left = _eval(node.left, variables)
        result = None
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, variables)
            # NumPy arrays handle comparisons natively
            if HAS_NUMPY and (isinstance(left, np.ndarray) or isinstance(right, np.ndarray)):
                if isinstance(op, ast.Eq): cmp = left == right
                elif isinstance(op, ast.NotEq): cmp = left != right
                elif isinstance(op, ast.Lt): cmp = left < right
                elif isinstance(op, ast.LtE): cmp = left <= right
                elif isinstance(op, ast.Gt): cmp = left > right
                elif isinstance(op, ast.GtE): cmp = left >= right
                else:
                    raise ValueError(f"unsupported comparison: {type(op).__name__}")
                cmp_result = cmp.astype(float)
            # Pure Python fallback: element-wise for lists
            elif isinstance(left, list) or isinstance(right, list):
                left_arr = left if isinstance(left, list) else [left] * len(right)
                right_arr = right if isinstance(right, list) else [right] * len(left)
                if isinstance(op, ast.Eq): cmp_result = [1.0 if a == b else 0.0 for a, b in zip(left_arr, right_arr)]
                elif isinstance(op, ast.NotEq): cmp_result = [1.0 if a != b else 0.0 for a, b in zip(left_arr, right_arr)]
                elif isinstance(op, ast.Lt): cmp_result = [1.0 if a < b else 0.0 for a, b in zip(left_arr, right_arr)]
                elif isinstance(op, ast.LtE): cmp_result = [1.0 if a <= b else 0.0 for a, b in zip(left_arr, right_arr)]
                elif isinstance(op, ast.Gt): cmp_result = [1.0 if a > b else 0.0 for a, b in zip(left_arr, right_arr)]
                elif isinstance(op, ast.GtE): cmp_result = [1.0 if a >= b else 0.0 for a, b in zip(left_arr, right_arr)]
                else:
                    raise ValueError(f"unsupported comparison: {type(op).__name__}")
            else:
                # Scalars
                if isinstance(op, ast.Eq): cmp = left == right
                elif isinstance(op, ast.NotEq): cmp = left != right
                elif isinstance(op, ast.Lt): cmp = left < right
                elif isinstance(op, ast.LtE): cmp = left <= right
                elif isinstance(op, ast.Gt): cmp = left > right
                elif isinstance(op, ast.GtE): cmp = left >= right
                else:
                    raise ValueError(f"unsupported comparison: {type(op).__name__}")
                cmp_result = 1.0 if cmp else 0.0
            # Chain multiple comparisons via multiplication (AND semantics)
            if result is None:
                result = cmp_result
            elif isinstance(result, list) and isinstance(cmp_result, list):
                result = [a * b for a, b in zip(result, cmp_result)]
            else:
                result = result * cmp_result
            left = right
        return result
    if isinstance(node, ast.BoolOp):
        # Lazy evaluation with short-circuit semantics
        if isinstance(node.op, ast.And):
            out = _eval(node.values[0], variables)
            for v in node.values[1:]:
                # Short-circuit: if all zeros, skip remaining
                if HAS_NUMPY and isinstance(out, np.ndarray):
                    if not np.any(out):
                        return out
                elif isinstance(out, list):
                    if not any(out):
                        return out
                elif not out:
                    return 0.0
                next_val = _eval(v, variables)
                out = _fn_min(out, next_val)
            return out
        if isinstance(node.op, ast.Or):
            out = _eval(node.values[0], variables)
            for v in node.values[1:]:
                # Short-circuit: if all nonzero, skip remaining
                if HAS_NUMPY and isinstance(out, np.ndarray):
                    if np.all(out):
                        return out
                elif isinstance(out, list):
                    if all(out):
                        return out
                elif out:
                    return out
                next_val = _eval(v, variables)
                out = _fn_max(out, next_val)
            return out
    if isinstance(node, ast.Call):
        fn = _FUNCTIONS[node.func.id]
        args = [_eval(a, variables) for a in node.args]
        return fn(*args)
    if isinstance(node, ast.IfExp):
        cond = _eval(node.test, variables)
        body = _eval(node.body, variables)
        orelse = _eval(node.orelse, variables)
        if HAS_NUMPY and isinstance(cond, np.ndarray):
            return np.where(cond != 0, body, orelse)
        if isinstance(cond, list):
            body_arr = body if isinstance(body, list) else [body] * len(cond)
            orelse_arr = orelse if isinstance(orelse, list) else [orelse] * len(cond)
            return [b if c else o for c, b, o in zip(cond, body_arr, orelse_arr)]
        return body if cond else orelse
    raise ValueError(f"unhandled expression node: {type(node).__name__}")


def safe_eval(expression: str, variables: dict[str, Any]):
    """Evaluate an outcome expression against a variables dict.

    >>> safe_eval("x + y * 2", {"x": 1, "y": 3})
    7
    """
    tree = ast.parse(expression, mode="eval")
    _validate(tree)
    return _eval(tree, variables)
