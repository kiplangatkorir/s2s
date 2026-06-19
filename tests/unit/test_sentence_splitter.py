from pipeline.sentence_splitter import SentenceSplitter


def test_sentence_splitter_flushes_short_phrase_without_punctuation():
    splitter = SentenceSplitter(flush_chars=12)

    phrases = splitter.feed("hello there how are you")

    assert phrases == ["hello there how are"]


def test_sentence_splitter_flushes_hard_cap_when_buffer_grows_large():
    splitter = SentenceSplitter(flush_chars=12)

    long_text = "word " * 130
    phrases = splitter.feed(long_text)

    # First phrase should be cut at the last word boundary before MAX_CHARS (120).
    # "word " * 23 + "word" = 115 chars (23 words + space + 24th word, stripped).
    # Verify the phrase is under the hard cap and the full text is preserved.
    from pipeline.sentence_splitter import MAX_CHARS
    assert len(phrases[0]) <= MAX_CHARS
    assert " ".join(phrases) == long_text.strip()
