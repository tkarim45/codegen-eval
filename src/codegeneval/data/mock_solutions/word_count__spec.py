def word_count(text):
    counts = {}
    for raw in text.lower().split():
        word = raw.strip(".,!?;:'\"()[]")
        if word:
            counts[word] = counts.get(word, 0) + 1
    return counts
