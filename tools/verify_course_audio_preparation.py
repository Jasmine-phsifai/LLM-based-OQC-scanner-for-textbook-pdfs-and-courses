"""Exercise real AAC/M4A archive planning and local clip preparation, without a provider."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from ocrllm import split_audio
from ocrllm.audio.snapshot_product_mp3 import snapshot_product_mp3
from ocrllm.audio.materialize_long_audio_interval import materialize_long_audio_interval
from ocrllm.audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from ocrllm.audio.probe_product_mp3 import probe_product_mp3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--temp-dir', required=True, type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    started = time.monotonic()
    plan = split_audio(args.source, interval_minutes=10, include_boundary_context=False)
    planned = time.monotonic()
    with snapshot_product_mp3(args.source, temp_dir=args.temp_dir) as snapshot:
        assert snapshot.path.suffix == '.m4a'
        window = LongAudioIntervalWindow(index=0, logical_start_seconds=0.0, logical_end_seconds=10.0, actual_start_seconds=0.0, actual_end_seconds=10.0)
        with materialize_long_audio_interval(snapshot.path, window=window) as clip:
            duration = probe_product_mp3(clip)
            assert 9.9 < duration < 10.2
    passed = digest == hashlib.sha256(args.source.read_bytes()).hexdigest()
    print(json.dumps(dict(passed=passed, planned_slices=len(plan), source_seconds=plan[-1].logical_end_seconds, clip_seconds=duration, planning_seconds=planned-started, wall_seconds=time.monotonic()-started, provider_calls=0)))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
