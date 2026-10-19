"""Convert a formatted DOCX into a downloadable LaTeX zip (report.tex + media/)."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

from fastapi import HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask


def _cleanup_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def convert_docx_to_latex_zip(docx_path: str) -> tuple[str, str]:
    """
    Run pandoc on ``docx_path`` and zip ``report.tex`` plus extracted media.

    Returns ``(zip_path, temp_dir)``. Caller must delete ``temp_dir`` after
    the response is sent. Raises ``HTTPException(500)`` on conversion failure.
    """
    if not docx_path or not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="No formatted file")

    tmp = tempfile.mkdtemp(prefix="fmt_latex_")
    try:
        import pypandoc

        tex_path = os.path.join(tmp, "report.tex")
        media_dir = os.path.join(tmp, "media")
        pypandoc.convert_file(
            docx_path,
            "latex",
            format="docx",
            outputfile=tex_path,
            extra_args=["--standalone", f"--extract-media={media_dir}"],
        )
        if not os.path.exists(tex_path):
            raise RuntimeError("Pandoc did not produce report.tex")

        zip_path = os.path.join(tmp, "report_latex.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tex_path, "report.tex")
            if os.path.isdir(media_dir):
                for root, _, files in os.walk(media_dir):
                    for name in files:
                        full = os.path.join(root, name)
                        zf.write(full, os.path.relpath(full, tmp).replace("\\", "/"))
        return zip_path, tmp
    except HTTPException:
        _cleanup_dir(tmp)
        raise
    except Exception as exc:
        _cleanup_dir(tmp)
        raise HTTPException(
            status_code=500,
            detail=f"Could not convert document to LaTeX. {exc}",
        ) from exc


def latex_zip_response(docx_path: str) -> FileResponse:
    zip_path, tmp = convert_docx_to_latex_zip(docx_path)
    return FileResponse(
        path=zip_path,
        filename="report_latex.zip",
        media_type="application/zip",
        background=BackgroundTask(_cleanup_dir, tmp),
    )
