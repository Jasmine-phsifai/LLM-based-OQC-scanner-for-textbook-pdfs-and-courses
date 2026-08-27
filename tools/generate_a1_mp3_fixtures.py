"""Regenerate the synthetic Stage A1 MP3 validation corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


_SYNTHETIC_INPUT = "sine=frequency=997:sample_rate=44100:duration=0.500"
_FIXTURE_FILENAMES = (
    "valid_cbr.mp3",
    "valid_vbr.mp3",
    "valid_id3.mp3",
    "one_frame.mp3",
    "incomplete_tail.mp3",
    "corrupted_middle.mp3",
)
_ACCEPTED_FILENAMES = frozenset(
    {
        "valid_cbr.mp3",
        "valid_vbr.mp3",
        "valid_id3.mp3",
        "incomplete_tail.mp3",
    }
)


def generate_a1_mp3_fixtures(*, ffmpeg: Path, output_directory: Path) -> None:
    """Write deterministic MP3 fixtures and their provenance manifest."""

    ffmpeg = ffmpeg.resolve(strict=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    mp3_directory = output_directory / "mp3"
    mp3_directory.mkdir(parents=True, exist_ok=True)

    cbr_arguments = _encoder_arguments(
        bitrate_arguments=("-b:a", "32k"),
        output_path=mp3_directory / "valid_cbr.mp3",
    )
    vbr_arguments = _encoder_arguments(
        bitrate_arguments=("-q:a", "8"),
        output_path=mp3_directory / "valid_vbr.mp3",
    )
    id3_arguments = (
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(mp3_directory / "valid_cbr.mp3"),
        "-map_metadata",
        "-1",
        "-c:a",
        "copy",
        "-metadata",
        "title=OCRLLM synthetic 997 Hz",
        "-metadata",
        "artist=OCRLLM tests",
        "-write_id3v1",
        "0",
        "-id3v2_version",
        "3",
        str(mp3_directory / "valid_id3.mp3"),
    )
    for arguments in (cbr_arguments, vbr_arguments, id3_arguments):
        _run_ffmpeg(ffmpeg, arguments)

    cbr_bytes = (mp3_directory / "valid_cbr.mp3").read_bytes()
    frame_offsets = _mpeg_layer3_frame_offsets(cbr_bytes)
    if len(frame_offsets) < 4:
        raise RuntimeError("generated CBR MP3 has too few frames")
    (mp3_directory / "one_frame.mp3").write_bytes(
        cbr_bytes[: frame_offsets[1]]
    )
    (mp3_directory / "incomplete_tail.mp3").write_bytes(
        cbr_bytes[: frame_offsets[-1] + 1]
    )
    corrupted = bytearray(cbr_bytes)
    corrupt_offset = frame_offsets[len(frame_offsets) // 2 + 1]
    corrupted[corrupt_offset : corrupt_offset + 4] = b"\x00" * 4
    (mp3_directory / "corrupted_middle.mp3").write_bytes(corrupted)

    import miniaudio

    fixtures = []
    for filename in _FIXTURE_FILENAMES:
        path = mp3_directory / filename
        info = miniaudio.mp3_get_file_info(str(path))
        stream = miniaudio.mp3_stream_file(str(path), frames_to_read=4096)
        decoded_sample_count = 0
        try:
            for chunk in stream:
                decoded_sample_count += len(chunk)
        finally:
            stream.close()
        data = path.read_bytes()
        fixtures.append(
            {
                "filename": filename,
                "validation": (
                    "accept" if filename in _ACCEPTED_FILENAMES else "reject"
                ),
                "byte_size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "channel_count": info.nchannels,
                "sample_rate_hz": info.sample_rate,
                "reported_frame_count": info.num_frames,
                "decoded_frame_count": decoded_sample_count // info.nchannels,
            }
        )

    version_output = subprocess.run(
        [str(ffmpeg), "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    manifest: dict[str, Any] = {
        "schema": "ocrllm.a1-mp3-fixtures.v1",
        "validation_contract": (
            "accept means accepted by the decoder contract, not a claim of "
            "pristine MPEG bitstream provenance"
        ),
        "synthetic_input": _SYNTHETIC_INPUT,
        "generator": {
            "ffmpeg_version": version_output,
            "ffmpeg_sha256": hashlib.sha256(ffmpeg.read_bytes()).hexdigest(),
            "encoder": "libmp3lame",
            "decoder": f"miniaudio {miniaudio.__version__}",
            "commands": [
                _portable_arguments(cbr_arguments, output_directory),
                _portable_arguments(vbr_arguments, output_directory),
                _portable_arguments(id3_arguments, output_directory),
            ],
            "derivations": {
                "one_frame.mp3": "valid_cbr bytes before the second MPEG frame",
                "incomplete_tail.mp3": "valid_cbr through one byte of its final MPEG frame",
                "corrupted_middle.mp3": "zero the four-byte header of middle MPEG frame 12",
            },
        },
        "fixtures": fixtures,
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _encoder_arguments(
    *,
    bitrate_arguments: tuple[str, str],
    output_path: Path,
) -> tuple[str, ...]:
    return (
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        _SYNTHETIC_INPUT,
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:a",
        "+bitexact",
        "-threads",
        "1",
        "-c:a",
        "libmp3lame",
        *bitrate_arguments,
        "-write_xing",
        "1",
        "-id3v2_version",
        "0",
        str(output_path),
    )


def _run_ffmpeg(ffmpeg: Path, arguments: tuple[str, ...]) -> None:
    subprocess.run([str(ffmpeg), *arguments], check=True)


def _portable_arguments(
    arguments: tuple[str, ...],
    output_directory: Path,
) -> list[str]:
    root = str(output_directory)
    return [
        argument.replace(root, "{output}").replace("\\", "/")
        for argument in arguments
    ]


def _mpeg_layer3_frame_offsets(data: bytes) -> tuple[int, ...]:
    offsets: list[int] = []
    offset = 0
    while offset + 4 <= len(data):
        header = int.from_bytes(data[offset : offset + 4], "big")
        if header >> 21 != 0x7FF:
            raise RuntimeError(f"invalid MPEG sync at byte {offset}")
        version_bits = (header >> 19) & 0b11
        layer_bits = (header >> 17) & 0b11
        bitrate_index = (header >> 12) & 0b1111
        sample_rate_index = (header >> 10) & 0b11
        padding = (header >> 9) & 1
        if version_bits == 0b01 or layer_bits != 0b01:
            raise RuntimeError("generated file is not MPEG Layer III")
        if bitrate_index in {0, 15} or sample_rate_index == 3:
            raise RuntimeError("generated file has unsupported free/invalid frame metadata")

        mpeg1 = version_bits == 0b11
        bitrates = (
            (32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
            if mpeg1
            else (8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
        )
        sample_rates = (44100, 48000, 32000)
        sample_rate = sample_rates[sample_rate_index]
        if version_bits == 0b10:
            sample_rate //= 2
        elif version_bits == 0b00:
            sample_rate //= 4
        coefficient = 144000 if mpeg1 else 72000
        frame_length = (
            coefficient * bitrates[bitrate_index - 1] // sample_rate + padding
        )
        offsets.append(offset)
        offset += frame_length
    if offset != len(data):
        raise RuntimeError("generated file ends inside an MPEG frame")
    return tuple(offsets)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_arguments()
    generate_a1_mp3_fixtures(
        ffmpeg=arguments.ffmpeg,
        output_directory=arguments.output_directory,
    )
