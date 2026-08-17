"""Checks the repo structure as hassfest and HACS do.

Run with:  python3 tests/test_structure.py
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


# ---- mandatory files ------------------------------------------------------
for rel in ("hacs.json", "README.md", "LICENSE",
            "custom_components/opcom_pzu/manifest.json",
            "custom_components/opcom_pzu/__init__.py",
            "custom_components/opcom_pzu/config_flow.py",
            "custom_components/opcom_pzu/strings.json",
            "custom_components/opcom_pzu/translations/en.json",
            "custom_components/opcom_pzu/translations/ro.json",
            "custom_components/opcom_pzu/www/opcom-pzu-card.js"):
    check(f"{rel} exists", (ROOT / rel).is_file())

# ---- manifest -------------------------------------------------------------
manifest = json.loads((COMP / "manifest.json").read_text())
for key in ("domain", "name", "codeowners", "documentation", "iot_class",
            "issue_tracker", "version", "config_flow"):
    check(f"manifest are '{key}'", key in manifest)
check("domain = folder name", manifest["domain"] == COMP.name, manifest["domain"])
check("config_flow = true", manifest.get("config_flow") is True)
check("version is semver", re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")) is not None,
      manifest.get("version"))
check("no external dependencies (only stdlib + HA)", manifest.get("requirements") == [])
check("documentation and issue_tracker on same repo",
      manifest["issue_tracker"].startswith(manifest["documentation"]),
      f"{manifest['documentation']} / {manifest['issue_tracker']}")

hacs = json.loads((ROOT / "hacs.json").read_text())
check("hacs.json has 'name'", "name" in hacs)
check("hacs.json requires min HA version", "homeassistant" in hacs, hacs.get("homeassistant"))

# ---- translation keys -----------------------------------------------------
def keys_from(path: Path, platform: str) -> set[str]:
    """Keys given as `key="..."` in entity descriptions of a module."""
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
        check(f"{lang}: all {platform} keys are translated", not missing, f"missing: {missing}")
        check(f"{lang}: no orphan translations in {platform}", not extra, f"extra: {extra}")
    for step in ("config", "options"):
        check(f"{lang}: section '{step}' exists", step in tr)

strings = json.loads((COMP / "strings.json").read_text())
en = json.loads((COMP / "translations" / "en.json").read_text())
check("strings.json identical to translations/en.json", strings == en)

# config flow options must be translated
from_const = (COMP / "const.py").read_text()
conf_keys = set(re.findall(r'^CONF_\w+: Final = "(\w+)"', from_const, re.M))
for lang in ("en", "ro"):
    tr = json.loads((COMP / "translations" / f"{lang}.json").read_text())
    for step, section in (("config", "user"), ("options", "init")):
        data = tr[step]["step"][section]["data"]
        check(f"{lang}: {step}.{section} describes all options",
              conf_keys <= set(data), f"missing: {conf_keys - set(data)}")

# ---- declared platforms have a file ---------------------------------------
init = (COMP / "__init__.py").read_text()
platforms = re.findall(r"Platform\.(\w+)", init)
check("at least one declared platform", bool(platforms))
for p in platforms:
    check(f"platform {p.lower()} has module", (COMP / f"{p.lower()}.py").is_file())

# ---- the card -------------------------------------------------------------
card = (COMP / "www" / "opcom-pzu-card.js").read_text()
check("card defines element", 'customElements.define("opcom-pzu-card"' in card)
check("card registers in customCards", "window.customCards" in card)
check("card has setConfig", "setConfig(" in card)
check("card has getCardSize", "getCardSize(" in card)
check("card does not load external resources",
      not re.search(r"""(?:src|href|import)\s*[=(]\s*['"]https?://""", card))
check("const.py filename matches",
      f'CARD_FILENAME: Final = "opcom-pzu-card.js"' in from_const)

# ---- no HA imports in the pure module -----------------------------------
pure = (COMP / "opcom.py").read_text()
check("opcom.py does not import Home Assistant", "homeassistant" not in pure)

print("\n" + ("STRUCTURE IS VALID" if ok else "THERE ARE STRUCTURE ISSUES"))
sys.exit(0 if ok else 1)
