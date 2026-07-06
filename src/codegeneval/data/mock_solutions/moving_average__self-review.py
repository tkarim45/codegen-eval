def moving_average(values, window):
    if window <= 0:
        raise ValueError("window must be positive")
    if window > len(values):
        return []
    out = []
    s = sum(values[:window])
    out.append(s / window)
    for i in range(window, len(values)):
        s += values[i] - values[i - window]
        out.append(s / window)
    return out
