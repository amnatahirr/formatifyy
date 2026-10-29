import json, os, tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

router = APIRouter(prefix="/api")


def _get_groq_client():
    """Lazy-load Groq client so a missing key only errors at call time."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured on the server. "
                   "Please add it to backend/.env and restart the server.",
        )
    try:
        from groq import Groq  # noqa: PLC0415
        return Groq(api_key=api_key)
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="groq package is not installed. Run: pip install groq",
        )


FONTS = {"Times New Roman", "Arial", "Calibri", "Georgia",
         "Courier New", "Garamond", "Verdana"}
PAGE_SIZES = {"A4", "Letter", "Legal", "A3", "Tabloid"}
TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72}

# key -> ("num", min, max) | ("bool",) | ("enum", set) | ("margin",)
SCHEMA = {
    "body_size": ("num", 6, 48),
    "body_line_spacing": ("num", 0.8, 4),
    "body_justified": ("bool",),
    "body_space_before": ("num", 0, 100),
    "body_space_after": ("num", 0, 100),
    "first_line_indent": ("num", 0, 3),
    "bullet_indent": ("num", 0, 3),
    "page_size": ("enum", PAGE_SIZES),
    "font_family": ("enum", FONTS),
    "margin_top": ("margin",), "margin_bottom": ("margin",),
    "margin_left": ("margin",), "margin_right": ("margin",),
}
for _n in range(1, 5):
    SCHEMA[f"heading{_n}_size"] = ("num", 6, 72)
    SCHEMA[f"heading{_n}_bold"] = ("bool",)
    SCHEMA[f"heading{_n}_italic"] = ("bool",)
    SCHEMA[f"heading{_n}_space_before"] = ("num", 0, 100)
    SCHEMA[f"heading{_n}_space_after"] = ("num", 0, 100)

SYSTEM = f"""You convert spoken document-formatting commands (English, Urdu or
Roman Urdu) into a JSON patch for a template form.
Return ONLY: {{"changes": {{...}}, "unclear": "<what you could not understand or ''"}}
Allowed keys: {sorted(SCHEMA)}.
Rules:
- Include ONLY keys the speaker mentioned. Never guess.
- margin_* values must be {{"value": number, "unit": "mm|cm|in|pt"}}.
- font_family must be one of {sorted(FONTS)}.
- 'heading' without a number means heading1..heading4 all.
- Relative commands ('thora barha do') -> compute from the CURRENT values given.
- body_line_spacing is a multiplier (1.5, 2.0); sizes are in pt."""


def sanitize(changes: dict, spacing_unit: str):
    out, rejected = {}, []
    for k, v in (changes or {}).items():
        spec = SCHEMA.get(k)
        try:
            if spec is None:
                raise ValueError
            kind = spec[0]
            if kind == "num":
                x = float(v)
                if not spec[1] <= x <= spec[2]:
                    raise ValueError
                out[k] = x
            elif kind == "bool":
                if not isinstance(v, bool):
                    raise ValueError
                out[k] = v
            elif kind == "enum":
                if v not in spec[1]:
                    raise ValueError
                if k == "font_family":
                    for f in ["body_font", "bullet_font", "numbered_font"] + \
                             [f"heading{n}_font" for n in range(1, 5)]:
                        out[f] = v
                else:
                    out[k] = v
            elif kind == "margin":
                mm = float(v["value"]) * TO_MM[v["unit"]]
                if not 0 <= mm <= 100:
                    raise ValueError
                out[k] = round(mm / TO_MM[spacing_unit], 2)
        except Exception:
            rejected.append(k)
    return out, rejected


@router.post("/admin/templates/voice-patch")
async def voice_patch(
    audio: UploadFile = File(...),
    current: str = Form("{}"),
    spacing_unit: str = Form("mm"),
    user_id: int = 0,
):
    client = _get_groq_client()  # raises 503 if key missing or groq not installed

    data = await audio.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Audio empty or too large")
    if spacing_unit not in TO_MM:
        spacing_unit = "mm"

    # Determine file extension from upload content_type for Groq compatibility
    content_type = (audio.content_type or "audio/wav").lower()
    ext = ".webm" if "webm" in content_type else \
          ".mp4"  if "mp4"  in content_type else \
          ".m4a"  if "m4a"  in content_type else \
          ".ogg"  if "ogg"  in content_type else ".wav"

    # Save to temp file (Groq needs a real file path, not bytes)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with open(path, "rb") as fh:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",   # Groq's fastest Whisper model
                file=fh,
                response_format="text",
            )
        # Groq returns a plain string when response_format="text"
        transcript = transcription if isinstance(transcription, str) else transcription.text
    finally:
        os.remove(path)

    if not transcript.strip():
        return {"transcript": "", "patch": {}, "rejected": [], "unclear": "Nothing was heard"}

    # Use Groq LLM to convert transcript → JSON patch
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",          # Fast + accurate Groq LLM
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"Spacing unit of the form: {spacing_unit}\n"
                f"CURRENT values: {current}\nCOMMAND: {transcript}"},
        ],
        temperature=0.1,   # Low temp for deterministic JSON output
    )
    raw = json.loads(resp.choices[0].message.content)
    patch, rejected = sanitize(raw.get("changes"), spacing_unit)
    print('[VOICE] POST $url');
    return {"transcript": transcript, "patch": patch,
            "rejected": rejected, "unclear": raw.get("unclear", "")}