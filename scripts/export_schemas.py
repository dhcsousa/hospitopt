"""Export JSON schemas for all top-level Pydantic config models."""

from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

CONFIGS: list[tuple[str, str]] = [
    ("hospitopt_api.settings.APIConfig", "api-schema.json"),
    ("hospitopt_worker.settings.WorkerConfig", "worker-schema.json"),
]


def main() -> None:
    from importlib import import_module

    SCHEMAS_DIR.mkdir(exist_ok=True)

    for dotted_path, filename in CONFIGS:
        module_path, cls_name = dotted_path.rsplit(".", 1)
        mod = import_module(module_path)
        cls = getattr(mod, cls_name)
        cls.export_json_schema(SCHEMAS_DIR / filename)
        print(f"  {filename}")

    print("Done.")


if __name__ == "__main__":
    main()
