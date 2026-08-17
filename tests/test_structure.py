"""Verifica structura repo-ului asa cum o verifica hassfest si HACS.

Ruleaza cu:  python3 tests/test_structure.py
"""

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "opcom_pzu"

ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS  " if cond else "FAIL  ") + label + (f"   {extra}" if extra else ""))
    if not cond:
        ok = False


# ---- fisiere obligatorii --------------------------------------------------
for rel in ("hacs.json", "README.md", "LICENSE",
            "custom_components/opcom_pzu/manifest.json",
            "custom_components/opcom_pzu/__init__.py",
            "custom_components/opcom_pzu/config_flow.py",
            "custom_components/opcom_pzu/strings.json",
            "custom_components/opcom_pzu/translations/en.json",
            "custom_components/opcom_pzu/translations/ro.json",
            "custom_components/opcom_pzu/www/opcom-pzu-card.js"):
    check(f"exista {rel}", (ROOT / rel).is_file())

# ---- manifest -------------------------------------------------------------
manifest = json.loads((COMP / "manifest.json").read_text())
for key in ("domain", "name", "codeowners", "documentation", "iot_class",
            "issue_tracker", "version", "config_flow"):
    check(f"manifest are '{key}'", key in manifest)
check("domain = numele folderului", manifest["domain"] == COMP.name, manifest["domain"])
check("config_flow = true", manifest.get("config_flow") is True)
check("version este semver", re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")) is not None,
      manifest.get("version"))
check("fara dependinte externe (doar stdlib + HA)", manifest.get("requirements") == [])
check("documentation si issue_tracker pe acelasi repo",
      manifest["issue_tracker"].startswith(manifest["documentation"]),
      f"{manifest['documentation']} / {manifest['issue_tracker']}")

hacs = json.loads((ROOT / "hacs.json").read_text())
check("hacs.json are 'name'", "name" in hacs)
check("hacs.json cere o versiune minima de HA", "homeassistant" in hacs, hacs.get("homeassistant"))

# ---- cheile de traducere ---------------------------------------------------
def keys_from(path: Path, platform: str) -> set[str]:
    """Cheile date ca `key="..."` in descrierile de entitati dintr-un modul."""
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "key" and isinstance(kw.value, ast.Constant):
                    found.add(kw.value.value)
    return found


used = {
    "sensor": keys_from(COMP / "sensor.py", "sensor"),
    "binary_sensor": keys_from(COMP / "binary_sensor.py", "binary_sensor"),
    "number": keys_from(COMP / "number.py", "number"),
    "select": {"window_duration"},
}

for lang in ("en", "ro"):
    tr = json.loads((COMP / "translations" / f"{lang}.json").read_text())
    entities = tr.get("entity", {})
    for platform, keys in used.items():
        declared = set(entities.get(platform, {}))
        missing = keys - declared
        extra = declared - keys
        check(f"{lang}: toate cheile {platform} sunt traduse", not missing, f"lipsesc: {missing}")
        check(f"{lang}: fara traduceri orfane in {platform}", not extra, f"in plus: {extra}")
    for step in ("config", "options"):
        check(f"{lang}: sectiunea '{step}' exista", step in tr)

strings = json.loads((COMP / "strings.json").read_text())
en = json.loads((COMP / "translations" / "en.json").read_text())
check("strings.json identic cu translations/en.json", strings == en)

# optiunile din config flow trebuie sa fie traduse
from_const = (COMP / "const.py").read_text()
conf_keys = set(re.findall(r'^CONF_\w+: Final = "(\w+)"', from_const, re.M))
for lang in ("en", "ro"):
    tr = json.loads((COMP / "translations" / f"{lang}.json").read_text())
    for step, section in (("config", "user"), ("options", "init")):
        data = tr[step]["step"][section]["data"]
        check(f"{lang}: {step}.{section} descrie toate optiunile",
              conf_keys <= set(data), f"lipsesc: {conf_keys - set(data)}")

# ---- platformele declarate au fisier ---------------------------------------
init = (COMP / "__init__.py").read_text()
platforms = re.findall(r"Platform\.(\w+)", init)
check("cel putin o platforma declarata", bool(platforms))
for p in platforms:
    check(f"platforma {p.lower()} are modul", (COMP / f"{p.lower()}.py").is_file())

# ---- cardul ---------------------------------------------------------------
card = (COMP / "www" / "opcom-pzu-card.js").read_text()
check("cardul defineste elementul", 'customElements.define("opcom-pzu-card"' in card)
check("cardul se inregistreaza in customCards", "window.customCards" in card)
check("cardul are setConfig", "setConfig(" in card)
check("cardul are getCardSize", "getCardSize(" in card)
check("cardul nu incarca resurse externe",
      not re.search(r"""(?:src|href|import)\s*[=(]\s*['"]https?://""", card))
check("numele fisierului din const.py se potriveste",
      f'CARD_FILENAME: Final = "opcom-pzu-card.js"' in from_const)

# ---- fara import-uri HA in modulul pur ------------------------------------
pure = (COMP / "opcom.py").read_text()
check("opcom.py nu importa Home Assistant", "homeassistant" not in pure)

print("\n" + ("STRUCTURA E VALIDA" if ok else "EXISTA PROBLEME DE STRUCTURA"))
sys.exit(0 if ok else 1)
