def slugify(text):
    result = []
    for ch in text.strip().lower():
        if ch.isalnum():
            result.append(ch)
        elif ch in " -_" and result and result[-1] != "-":
            result.append("-")
    while result and result[-1] == "-":
        result.pop()
    return "".join(result)
