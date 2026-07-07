# Phase 3A Backend Test Fix Report

## 1. Root Cause of Each Failure
- **Failure 1: 422 error during upload test (`test_landed_cost_integration_and_review`)**
  - The test file size is 28.24 MB (located at `c:\Users\itisa\Desktop\UP_CODSP_backend\backend\test_data\AnparaTPS-LandedCost-(16-31)March26 (1).pdf`).
  - The backend hardcoded upload limit was 25 MB (`_MAX_UPLOAD_BYTES = 25 * 1024 * 1024`), causing the endpoint to correctly reject the file with a 422 Validation Error.
- **Failure 2: Parser Note mismatch (`test_landed_cost_parser_extraction`)**
  - The test was hardcoded to read the PDF from a directory outside the workspace (`c:\Users\itisa\Desktop\UP_CODSP_backend\...`).
  - This external PDF was scanned (image-only) on Page 2, causing the parser to output the warning: `Page 2 does not contain selectable text (may be scanned).`
  - The test asserted that `len(notes) == 0`, which failed because of this scanning warning.

## 2. Decision Made for Upload Size and Why
- **Decision:** Implemented **Option B**.
- **Reasoning:** Large PDF document uploads (such as the 28.24 MB calibration PDF containing multi-page scanned/selectable text) are realistic operational files for UPRVUNL. Rather than completely disabling the limit, we increased the threshold to a bounded value of **35 MB** and made it configurable via environment variables (`DOCUMENT_MAX_UPLOAD_SIZE_BYTES`).

## 3. Exact Files Changed
- [`backend/app/core/config.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/core/config.py) — Added `document_max_upload_size_bytes` settings.
- [`backend/app/modules/documents/router.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/documents/router.py) — Replaced hardcoded `25 MB` limit with the configurable `settings.document_max_upload_size_bytes` value and formatted the E501 line length correctly.
- [`backend/.env.example`](file:///c:/Users/itisa/Desktop/mdsir/backend/.env.example) — Documented `DOCUMENT_MAX_UPLOAD_SIZE_BYTES=36700160` (35 MB).
- [`backend/.env`](file:///c:/Users/itisa/Desktop/mdsir/backend/.env) — Added `DOCUMENT_MAX_UPLOAD_SIZE_BYTES=36700160` to local settings.
- [`backend/tests/test_landed_costs_extraction.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_landed_costs_extraction.py) — Changed `REAL_PDF_PATH` to resolve dynamically to the workspace `test_data` path, and added a test case `test_oversized_file_rejected` to verify rejection of mock files > 35 MB.

## 4. Whether Production Upload Limit Changed
- **Yes**, the maximum document upload size limit has been raised to **35 MB** (configurable via environment variables) to accommodate valid UPRVUNL operational documents.

## 5. How Parser-Note Tests Were Made Robust
- Fixed `REAL_PDF_PATH` to resolve dynamically to the clean workspace file (`mdsir/backend/test_data/...` which is 15.66 MB and contains full selectable text on Page 2).
- The parser note check correctly asserts that there are 0 warnings/notes for this clean, compliant layout.

## 6. Final Pytest, Ruff, and Frontend Build Results
- **pytest:** **PASSED** (all 46 tests executed and passed successfully in 4.55s).
- **ruff check:** **PASSED** (all lint checks passed).
- **npm run build:** **PASSED** (successfully compiled production bundle in 3.85s).

## 7. Git Safety Confirmation
- The `.venv/` and `.env` files are ignored by the root and backend `.gitignore` configuration.
- The `storage/documents/*` and `backend/test_data/` paths are ignored, preventing large PDFs from being tracked by Git.

---
