def flatten(nested):
    out = []
    for item in nested:
        if hasattr(item, "__iter__"):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out
