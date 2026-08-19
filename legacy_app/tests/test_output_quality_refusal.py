from OCRLLM.core.output_quality import looks_like_refusal


def test_short_apology_refusals_are_detected():
    assert looks_like_refusal("抱歉，我帮不了你识别这张图。")
    assert looks_like_refusal("Sorry, this request cannot be completed.")


def test_long_transcription_containing_apology_is_not_a_refusal():
    transcription = "这是正常识别正文。" * 30 + "原文中写道：抱歉。"

    assert not looks_like_refusal(transcription)
