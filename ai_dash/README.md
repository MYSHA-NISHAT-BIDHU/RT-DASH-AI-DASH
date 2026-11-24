# AI-DASH — Reviewed Source Release

**Source code and tests included.** This is a curated source package extracted from the research archive provided on 24 November 2026. It is **not** a full reproduction snapshot: large raw/processed data, experimental CSV outputs, generated media, compiled firmware artifacts, and the complete supplementary manifests are deliberately excluded.

- Python implementation: `research/rt_dash/`
- Scripts: `research/scripts/`
- Tests: `research/tests/`
- Configuration: `research/config/`
- Independent C++17 implementation and tests: `research_cpp/`

## Verification on 24 November 2026

- Python tests: 48 passed in an inspection environment.
- C++17 Release build: succeeded; CTest: 1/1 passed.
- Original uploaded ZIP passed integrity validation. RT-DASH supplementary ZIP had 231/231 SHA-256 entries matching.

## Running source tests

From this project's root, create a compatible Python environment using `research/requirements.txt` (RT-DASH also supplies `environment/requirements-lock.txt`) and execute:

```bash
PYTHONPATH=research python -m pytest -q research/tests
cmake -S research_cpp -B build-cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpp
ctest --test-dir build-cpp --output-on-failure
```

## Scope / caveats

- The research is **software-simulation based**; physical real-time performance and safety certification are not demonstrated.
- Scripts requiring the complete datasets or archived outputs will need the original research archive. Do not expect every experiment to regenerate from this trimmed package alone.
- RT-DASH: published in *Algorithms* (2026), DOI https://doi.org/10.3390/a19100863.
- AI-DASH: manuscript submitted for peer review in 2026; not yet published or accepted.
- Verify authorship and license terms before reusing third-party data or code. No dataset is redistributed here.
