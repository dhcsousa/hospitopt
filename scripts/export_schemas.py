"""Export JSON schemas for all top-level Pydantic config models."""

import sys
from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

CONFIGS: list[tuple[str, str]] = [
    ("hospitopt_api.settings.APIConfig", "api-schema.json"),
    ("hospitopt_worker.settings.WorkerConfig", "worker-schema.json"),
]


def main() -> None:
    import json
    from importlib import import_module

    SCHEMAS_DIR.mkdir(exist_ok=True)

    changed = False
    for dotted_path, filename in CONFIGS:
        module_path, cls_name = dotted_path.rsplit(".", 1)
        mod = import_module(module_path)
        cls = getattr(mod, cls_name)

        output_file = SCHEMAS_DIR / filename
        new_content = json.dumps(cls.export_json_schema(), indent=2) + "\n"
        old_content = output_file.read_text() if output_file.exists() else ""

        if new_content != old_content:
            output_file.write_text(new_content)
            print(f"  {filename} (updated)")
            changed = True
        else:
            print(f"  {filename} (unchanged)")

    if changed:
        print("Schemas were out of date, updated files. Please stage and re-commit.")
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
