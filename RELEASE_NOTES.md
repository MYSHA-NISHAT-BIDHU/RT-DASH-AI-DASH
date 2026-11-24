# Prepublication audit, 24 November 2026

Audited source inputs:
- `RT_DASH_Supplementary_Materials_REVISION (1).zip`: 278 entries; clean ZIP CRC; 231/231 archive SHA-256 checksums verified.
- `AI_DASH_Project.zip`: 453 entries; clean ZIP CRC. Its current package claims finalized November 6, 2026; this curated release retains only the source-related material listed in the README.

Execution checks performed before staging:
- RT-DASH: 25 Python unit tests passed; C++ Release build succeeded; CTest 1/1.
- AI-DASH: 48 Python unit tests passed; C++ Release build succeeded; CTest 1/1.

Static review: no obvious tokens, private key blocks or embedded passwords matched the scanned text-file patterns. This does not certify an exhaustive security review.

Excluded: third-party raw dataset snapshots, synthetic processed dataset, large and generated result CSVs, compiled software/firmware, PNG figures, PDFs, PPTX, obsolete legacy top-level implementation and manuscript drafts. The original S1 package remains the authoritative complete RT-DASH supplementary archive; source-only distribution is intentionally not a byte-for-byte S1 mirror.

The project was **not** independently tested for complete numerical reproduction from this curated source-only distribution.
