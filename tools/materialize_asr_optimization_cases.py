"""Prepare fixed ASR experiments with the owner's interval materializer; no inference."""
import argparse, hashlib, json, shutil, tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from ocrllm.audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from ocrllm.audio.materialize_long_audio_interval import materialize_long_audio_interval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in json.loads(args.cases.read_text()):
        checkpoint = json.loads(Path(case['checkpoint']).read_text())
        source = Path(unquote(urlsplit(checkpoint['source']['uri']).path))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != checkpoint['source']['sha256']:
            raise ValueError('Source differs from recognition checkpoint')
        with tempfile.TemporaryDirectory(dir=args.output) as tmp:
            owned = Path(tmp) / source.name
            shutil.copyfile(source, owned)
            window = LongAudioIntervalWindow(0, case['start'], case['end'], case['start'], case['end'])
            with materialize_long_audio_interval(owned, window=window) as clip:
                target = args.output / (case['id'] + '.mp3')
                if target.exists():
                    raise FileExistsError(target)
                shutil.copyfile(clip, target)
        rows.append({**case, 'path': str(target), 'source_sha256': digest,
                     'input_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    (args.output / 'manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(json.dumps({'cases': len(rows), 'manifest': str(args.output / 'manifest.json')}))


if __name__ == '__main__':
    main()
