"""Check the final publication receipt of a retained audio checkpoint."""
import hashlib


def is_audio_markdown_published(state, path):
    if state.audio_output_limit_policy is None:
        return path.is_file()
    if state.published_markdown_sha256 is None:
        return False
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == state.published_markdown_sha256
    except OSError:
        return False
