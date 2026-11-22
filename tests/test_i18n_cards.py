"""Approval cards and tool status are built by the engine in Spanish; the window translates what the engine marks with
msg() (elissa/tools/__init__.py) through the English dictionary in elissa/static/i18n.js. Every such text needs an
entry there, or an English interface shows it in Spanish."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "elissa" / "static" / "i18n.js"


def english_keys() -> list[str]:
    text = I18N.read_text("utf-8")
    body = text[text.index("const EN = {"):text.index("\n};\n")]
    keys = []
    for m in re.finditer(r"^\s*(['\"])((?:\\.|(?!\1).)*)\1\s*:", body, re.M):
        keys.append(m.group(2).replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\"))
    return keys


def card_texts() -> set[str]:
    """msg() texts, tool labels, element kinds and warnings: everything the window translates for the engine."""
    out = {"Para", "CC", "Asunto", "Adjuntos", "elemento"}  # email labels in app.js; the default element kind
    for f in sorted((ROOT / "elissa").rglob("*.py")):
        tree = ast.parse(f.read_text("utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                name, value = n.targets[0].id, n.value
                if name in ("INTERACTIVE", "RISKY_KEYS") and isinstance(value, ast.Dict):
                    out.update(v.value for v in value.values)
                elif name == "RISKY" and isinstance(value, ast.List):
                    out.update(t.elts[1].value for t in value.elts)
            elif isinstance(n, ast.Call) and getattr(n.func, "id", None) == "msg" and n.args:
                arg = n.args[0]
                if isinstance(arg, ast.Constant):
                    out.add(arg.value)
                elif isinstance(arg, ast.JoinedStr):  # file_edit.move_preview: "{Mover|Renombrar} {carpeta|archivo}"
                    out.update(f"{a} {b}" for a in ("Mover", "Renombrar") for b in ("carpeta", "archivo"))
            elif (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add" and len(n.args) >= 3
                  and isinstance(n.args[2], ast.Constant) and isinstance(n.args[2].value, str)):
                out.add(n.args[2].value)  # ToolRegistry.add(name, description, label, …)
    return out


def test_every_card_text_has_an_english_translation():
    missing = sorted(card_texts() - set(english_keys()))
    assert not missing, f"add these to EN in elissa/static/i18n.js: {missing}"


def test_english_dictionary_has_no_duplicate_keys():
    keys = english_keys()
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate keys in EN (the last one wins silently): {dupes}"


def test_placeholders_match_between_languages():
    text = I18N.read_text("utf-8")
    for key in card_texts():
        m = re.search(r"^\s*'" + re.escape(key.replace("'", "\\'")) + r"'\s*:\s*'((?:\\.|[^'])*)'", text, re.M)
        if m:
            assert set(re.findall(r"\{(\w+)\}", key)) == set(re.findall(r"\{(\w+)\}", m.group(1))), key


def test_cards_mark_their_texts_for_translation(tmp_path):
    from elissa.tools import msg
    from elissa.tools.file_edit import FileEditor
    from elissa.tools.files import FileTools

    card = FileEditor(FileTools(lambda: [str(tmp_path)])).mkdir_preview(str(tmp_path / "nueva"))
    assert card["title"] == msg("Crear una carpeta")
    assert msg("Ventana: {window}", window="Bloc de notas") == {"t": "Ventana: {window}", "v": {"window": "Bloc de notas"}}
