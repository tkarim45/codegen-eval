def safe_calc(expr):
    allowed = set("0123456789.+-*/() ")
    if not set(expr) <= allowed:
        raise ValueError("bad character in expression")
    return float(eval(expr))
