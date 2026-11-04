import io
import os
import pathlib
import struct
import zlib
from typing import Dict, Tuple

import numpy as np
from PIL import Image
import pytest

TESTBENCH_DIR = pathlib.Path(__file__).resolve().parent.parent
DSP_ASSETS_DIR = TESTBENCH_DIR / "output" / "dsp_assets"
DSP_COURSEWORK_DIR = pathlib.Path(
    os.environ.get("DSP_COURSEWORK_DIR", "E:\\STUDY_NEW_GEN\\\u0426\u041e\u0421")
)


def test_empirical_all_43_pz_pages_integrity() -> None:
    """Verify all 43 PZ pages exist, have valid PNG magic bytes, IEND chunks, and dimensions."""
    assert DSP_ASSETS_DIR.is_dir(), f"Assets dir does not exist: {DSP_ASSETS_DIR}"

    for page_idx in range(1, 44):
        file_path = DSP_ASSETS_DIR / f"pz_page_{page_idx:02d}.png"
        assert file_path.is_file(), f"Missing coursework page: {file_path.name}"
        assert file_path.stat().st_size >= 50_000, f"Page {file_path.name} file size too small: {file_path.stat().st_size} bytes"

        data = file_path.read_bytes()
        # Verify PNG magic bytes
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG magic in {file_path.name}"

        # Verify IEND chunk structure: [4 bytes len=0][4 bytes 'IEND'][4 bytes CRC]
        chunk_len = struct.unpack(">I", data[-12:-8])[0]
        chunk_type = data[-8:-4]
        chunk_crc = struct.unpack(">I", data[-4:])[0]
        assert chunk_len == 0, f"{file_path.name}: IEND length != 0"
        assert chunk_type == b"IEND", f"{file_path.name}: chunk type != IEND"
        assert chunk_crc == zlib.crc32(b"IEND"), f"{file_path.name}: invalid IEND CRC"

        # Verify image dimensions
        with Image.open(io.BytesIO(data)) as img:
            assert img.format == "PNG", f"{file_path.name}: format is {img.format}"
            w, h = img.size
            assert max(w, h) >= 2400, f"{file_path.name}: long edge {max(w, h)} < 2400 px"

            if page_idx == 42:
                # Page 42 must be A3 landscape
                assert w >= 4900 and h >= 3500, f"Page 42 not A3 landscape: {w}x{h}"
                assert (w, h) == (4973, 3521), f"Page 42 unexpected dimensions: {w}x{h}"
            elif page_idx == 43:
                # Page 43 is Appendix C A4 portrait
                assert (w, h) == (2493, 3521), f"Page 43 unexpected dimensions: {w}x{h}"
            else:
                # Pages 1..41 are GOST A4 portrait
                assert (w, h) == (2481, 3509), f"Page {page_idx} unexpected dimensions: {w}x{h}"


def test_empirical_drawings_e2_pe2_integrity() -> None:
    """Verify drawing_e2.png and drawing_pe2.png exist, have correct dimensions, and match pages 42/43."""
    e2_path = DSP_ASSETS_DIR / "drawing_e2.png"
    pe2_path = DSP_ASSETS_DIR / "drawing_pe2.png"

    for path, expected_dim in [
        (e2_path, (4973, 3521)),
        (pe2_path, (2493, 3521)),
    ]:
        assert path.is_file(), f"Missing drawing: {path.name}"
        assert path.stat().st_size >= 50_000, f"Drawing {path.name} too small: {path.stat().st_size} bytes"

        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG magic in {path.name}"
        chunk_type = data[-8:-4]
        chunk_crc = struct.unpack(">I", data[-4:])[0]
        assert chunk_type == b"IEND"
        assert chunk_crc == zlib.crc32(b"IEND")

        with Image.open(io.BytesIO(data)) as img:
            assert img.size == expected_dim, f"{path.name} dimensions {img.size} != {expected_dim}"
            assert max(img.size) >= 2400

    # Cross-verify page 42 with drawing_e2
    pz42_data = (DSP_ASSETS_DIR / "pz_page_42.png").read_bytes()
    e2_data = e2_path.read_bytes()
    assert pz42_data == e2_data, "pz_page_42.png bytes do not match drawing_e2.png!"

    # Cross-verify page 43 with drawing_pe2
    pz43_data = (DSP_ASSETS_DIR / "pz_page_43.png").read_bytes()
    pe2_data = pe2_path.read_bytes()
    assert pz43_data == pe2_data, "pz_page_43.png bytes do not match drawing_pe2.png!"


def test_empirical_drawings_match_source_pdfs() -> None:
    """Verify pixel-by-pixel fidelity against fresh PyMuPDF renders of 22.10.2026 source PDFs."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF (fitz) not available")

    e2_pdf = (
        DSP_COURSEWORK_DIR
        / "coursework"
        / "drawings"
        / "\u041f\u0413\u0422\u0423.466225.001_\u042d2.pdf"
    )
    pe2_pdf = (
        DSP_COURSEWORK_DIR
        / "coursework"
        / "drawings"
        / "\u041f\u0413\u0422\u0423.466225.001_\u041f\u042d2.pdf"
    )

    if not (e2_pdf.is_file() and pe2_pdf.is_file()):
        pytest.skip("Source PDFs not present on filesystem")

    mat = fitz.Matrix(300.0 / 72.0, 300.0 / 72.0)

    # 1. E2 schematic
    doc_e2 = fitz.open(str(e2_pdf))
    pix_e2 = doc_e2[0].get_pixmap(matrix=mat, alpha=False)
    arr_e2_fresh = np.frombuffer(pix_e2.samples, dtype=np.uint8).reshape(
        (pix_e2.height, pix_e2.width, 3)
    )
    doc_e2.close()

    arr_e2_disk = np.array(Image.open(DSP_ASSETS_DIR / "drawing_e2.png"))
    assert arr_e2_fresh.shape == arr_e2_disk.shape
    diff_e2 = np.abs(arr_e2_fresh.astype(float) - arr_e2_disk.astype(float))
    assert np.max(diff_e2) == 0.0, f"drawing_e2 has pixel differences: max diff={np.max(diff_e2)}"

    # 2. PE2 parts list
    doc_pe2 = fitz.open(str(pe2_pdf))
    pix_pe2 = doc_pe2[0].get_pixmap(matrix=mat, alpha=False)
    arr_pe2_fresh = np.frombuffer(pix_pe2.samples, dtype=np.uint8).reshape(
        (pix_pe2.height, pix_pe2.width, 3)
    )
    doc_pe2.close()

    arr_pe2_disk = np.array(Image.open(DSP_ASSETS_DIR / "drawing_pe2.png"))
    assert arr_pe2_fresh.shape == arr_pe2_disk.shape
    diff_pe2 = np.abs(arr_pe2_fresh.astype(float) - arr_pe2_disk.astype(float))
    assert np.max(diff_pe2) == 0.0, f"drawing_pe2 has pixel differences: max diff={np.max(diff_pe2)}"


def test_empirical_non_blank_and_color_variance() -> None:
    """Verify none of the staged images are blank, flat solid color, or placeholder rectangles."""
    all_pngs = sorted(DSP_ASSETS_DIR.glob("*.png"))
    assert len(all_pngs) == 51, f"Expected exactly 51 staged PNGs, found {len(all_pngs)}"

    for path in all_pngs:
        with Image.open(path) as img:
            arr = np.array(img.convert("RGB"))
            mean_val = float(np.mean(arr))
            std_val = float(np.std(arr))
            min_val = int(np.min(arr))
            max_val = int(np.max(arr))

            # Non-blank / non-solid checks
            assert std_val >= 15.0, f"{path.name} has low standard deviation {std_val} (likely solid/blank)"
            assert min_val <= 40, f"{path.name} min pixel value too high {min_val} (missing dark text/lines)"
            assert max_val >= 220, f"{path.name} max pixel value too low {max_val} (missing white background)"

            # Ensure NOT fallback placeholder background (16, 24, 42)
            corner_sample = arr[:50, :50, :]
            corner_mean = np.mean(corner_sample, axis=(0, 1))
            is_placeholder_bg = (
                abs(corner_mean[0] - 16) < 3
                and abs(corner_mean[1] - 24) < 3
                and abs(corner_mean[2] - 42) < 3
            )
            assert not is_placeholder_bg, f"{path.name} matches placeholder background (16, 24, 42)"


def test_empirical_figures_integrity() -> None:
    """Verify canonical MATLAB & architecture figures exist and meet dimensions."""
    expected_figures: Dict[str, Tuple[int, int]] = {
        "fig_3_1.png": (3826, 2370),
        "fig_4_1.png": (3408, 4908),
        "fig_5_1.png": (3163, 2472),
        "fig_5_2.png": (2135, 2097),
        "fig_5_3.png": (2486, 1829),
        "fig_5_5.png": (2496, 1829),
    }

    for filename, (exp_w, exp_h) in expected_figures.items():
        fig_path = DSP_ASSETS_DIR / filename
        assert fig_path.is_file(), f"Missing figure: {filename}"
        assert fig_path.stat().st_size >= 50_000, f"Figure {filename} size too small"

        with Image.open(fig_path) as img:
            assert img.size == (exp_w, exp_h), f"{filename} dimensions {img.size} != ({exp_w}, {exp_h})"


def test_cleanliness_no_literal_cyrillic() -> None:
    """Verify this challenge test file contains 0 literal Cyrillic characters."""
    raw = pathlib.Path(__file__).read_bytes()
    cyrillic_chars = [b for b in raw if 0xD0 <= b <= 0xD3]
    # Check via decoded string
    text = raw.decode("utf-8")
    import re
    cyr = re.findall(r"[\u0400-\u04FF]", text)
    assert len(cyr) == 0, f"Found {len(cyr)} literal Cyrillic characters in test file"
