"""Verify the public selector against an existing private benchmark manifest."""
import argparse
import json
import time
from pathlib import Path
from ocrllm import RetainedVideoFrame, select_extracted_frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--expected', required=True, type=Path)
    args = parser.parse_args()
    row = json.loads(args.manifest.read_text())['lectures'][0]
    frames = tuple(RetainedVideoFrame(frame_index=x['frame_index'], timestamp_seconds=x['timestamp_seconds'], path=Path(x['path'])) for x in row['frames'])
    started = time.monotonic()
    selected = select_extracted_frames(frames, duration_seconds=row['duration_seconds'])
    expected = json.loads(args.expected.read_text())['courses'][0]['selected_images']
    passed = [int(Path(p).stem.rsplit('-', 1)[1]) for p in expected] == [x.frame_index for x in selected]
    print(json.dumps(dict(source_frames=len(frames), selected_frames=len(selected), seconds=time.monotonic()-started, exact_baseline_indices_match=passed)))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
