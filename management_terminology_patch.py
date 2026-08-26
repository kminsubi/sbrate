import io
import zipfile


_REPLACEMENTS = (
    ("종합현황", "경영지표"),
)


def _rewrite_xlsx(stream):
    if stream is None:
        return stream
    try:
        if hasattr(stream, "seek"):
            stream.seek(0)
        raw = stream.read() if hasattr(stream, "read") else bytes(stream)
        source = io.BytesIO(raw)
        output = io.BytesIO()
        with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith((".xml", ".rels")):
                    text = data.decode("utf-8", errors="ignore")
                    for old, new in _REPLACEMENTS:
                        text = text.replace(old, new)
                    data = text.encode("utf-8")
                zout.writestr(info, data)
        output.seek(0)
        return output
    except Exception:
        try:
            if hasattr(stream, "seek"):
                stream.seek(0)
        except Exception:
            pass
        return stream


def install_management_terminology_patch():
    try:
        import management_export_v2 as mev2
    except Exception:
        return False

    if getattr(mev2, "_management_terminology_patch_installed", False):
        return True

    mev2.SECTION_LABELS["general"] = "경영지표"

    for name in ("_general_single", "_general_compare"):
        original = getattr(mev2, name, None)
        if not callable(original) or getattr(original, "__sbrate_terminology_wrapped__", False):
            continue

        def wrapped(*args, __original=original, **kwargs):
            return _rewrite_xlsx(__original(*args, **kwargs))

        wrapped.__sbrate_terminology_wrapped__ = True
        setattr(mev2, name, wrapped)

    mev2._management_terminology_patch_installed = True
    print("Management terminology patch installed: 업권현황 / 경영지표")
    return True
