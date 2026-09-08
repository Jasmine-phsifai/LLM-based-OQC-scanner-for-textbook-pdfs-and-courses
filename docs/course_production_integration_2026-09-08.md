# Course production integration evidence — 2026-09-08

The maintainer explicitly requested production composition, AAC/M4A archive
consumption, failed-range recovery and persistent incremental progress. Crawler
calls the public frame selector and owns publishing. OCRLLM owns frame selection,
request clips, recognition, bounded recovery and Markdown; Model Lab owns model
behavior and service lifecycle. No combined video lifecycle was added.

- Frame selection: actual 1,225-frame fourth-course package selected the same
  97 indices as the existing baseline, 14.455 seconds. The public function does
  not copy, rewrite or delete images.
- AAC/M4A: the real 24 kHz course archive planned 17 ten-minute slots without
  whole-course transcoding. An actual ten-second request clip decoded as
  10.0001875 seconds. Source hash unchanged; real temporary parent path exceeded
  260 characters. Planning 0.03594 seconds, scenario wall 0.80058 seconds.
- Current Model Lab efd21fc classified all three original failed ten-minute ASR
  slots 5/15/16 as 422/output_token_limit: input tokens 7815/7815/2547, output
  tokens 8192 each, EOS false, inference 166.590/171.003/164.682 seconds. This
  establishes ASR generation-cap failures, not OCR context overflow. The one
  deliberate ordinary resume reused all 14 settled slots and made three calls.
- With Model Lab 78ddd4b, explicit two-minute recovery created 12 child ranges
  inside the same checkpoint. Two real calls completed before an injected
  KeyboardInterrupt at the HTTP boundary. The same original plan then resumed
  the remaining ten calls, preserving the first two and all original 14 parents.
  Interrupted stage 24.51772 seconds; resume 203.17661 seconds. Eleven children
  settled, recovering parents 5 and 16; parent 15 child 1 (9120–9240 seconds)
  still hit the generation cap. Result honestly remained 16/17 partial.
- A final explicit one-minute refinement of that sole failed 120-second range
  is separately recorded below when finished. No VAD, silence deletion, prompt
  change, quality relaxation or model-marker fabrication was introduced.
- The fresh-call automatic subdivision path is opt-in and restricted to the
  observed output_token_limit machine code. A real-media/synthetic-HTTP scenario
  verified one failed original plus two successful children (three accounted
  calls); a non-budget 422 stopped after one call. These responses are synthetic
  and do not count as model inference or transcription-quality evidence. The
  initial synthetic fixture omitted required response fields and was rejected;
  fixing the fixture proved the parser remained strict.

Runnable scenarios: `tools/verify_extracted_frame_selection.py`,
`tools/verify_course_audio_preparation.py`,
`tools/run_failed_audio_resplit_scenario.py`, and
`tools/verify_audio_output_limit_recovery.py`. Private run evidence stays under
`/mnt/r/course-pipeline-state/validation`; original recognition state/Markdown
remain under the existing fourth-course directory. Production callers use
`inspect_markdown_job` and public resume, never the internal checkpoint schema.

Relevant checks: selection 23 passed/3 skipped; AAC preparation and audio 41
passed/1 skipped; recovery changes existing merged-audio/light-import 27 passed.
These overlap; counts are not summed as independent coverage.
