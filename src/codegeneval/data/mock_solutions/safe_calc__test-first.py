import re


def safe_calc(expr):
    if not re.fullmatch(r"[0-9.+\-*/() ]+", expr):
        raise ValueError("bad character in expression")
    return float(eval(expr))
