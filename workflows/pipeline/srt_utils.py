import json


def fmt_srt_time(sec):
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


def extract_words_from_segments(segments):
    words = []
    for seg in segments:
        for word in (seg.words or []):
            w = word.word.strip() if hasattr(word, 'word') else ''
            if w:
                words.append({"word": w, "start": word.start, "end": word.end})
    return words


def words_to_srt(words, max_words=10, max_chars_per_line=42):
    if not words:
        return ""
    lines = []
    idx = 1
    for group_start in range(0, len(words), max_words):
        group = words[group_start:group_start + max_words]
        phrase_start = group[0]['start']
        phrase_end = group[-1]['end']
        phrase_text = ' '.join(w['word'] for w in group)
        
        if len(phrase_text) > max_chars_per_line:
            mid = len(group) // 2
            line1 = ' '.join(w['word'] for w in group[:mid])
            line2 = ' '.join(w['word'] for w in group[mid:])
            phrase_text = f"{line1}\n{line2}"
        
        lines.append(f"{idx}\n{fmt_srt_time(phrase_start)} --> {fmt_srt_time(phrase_end)}\n{phrase_text}\n")
        idx += 1
    return '\n'.join(lines)


def validate_srt_readability(srt_content, max_chars_per_line=42):
    issues = []
    blocks = srt_content.strip().split('\n\n')
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        text_lines = lines[2:]
        for line in text_lines:
            if len(line) > max_chars_per_line:
                issues.append(f"Line too long ({len(line)} chars): '{line[:50]}...'")
    return {
        "valid": len(issues) == 0,
        "issues": issues[:10],
        "total_blocks": len(blocks),
    }


def save_words_json(words, path, transcription_text=""):
    data = {"words": words}
    if transcription_text:
        data["text"] = transcription_text.strip()
    with open(path, "w") as f:
        json.dump(data, f)


def load_words_json(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "words" in data:
        return data["words"]
    return []
