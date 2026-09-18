"""Import device types (with port templates and panel images) into the catalog.

Sources are pluggable: register a new class in ``SOURCES`` to add another
catalog (a vendor portal, an internal sheet, a different library). The bundled
sources are:

* ``netbox`` — NetBox devicetype-library on GitHub (YAML + elevation images)
* ``file``   — a single local devicetype YAML
* ``dir``    — a directory of local devicetype YAML files

Examples::

    $env:DB_PASSWORD = "<password>"

    # 列出某个厂商在库里的型号
    python .\\tools\\import_device_types.py --source netbox --vendor Huawei --list

    # 导入一个型号（含端口模板与面板图）
    python .\\tools\\import_device_types.py --source netbox --vendor Ubiquiti ^
        --slug ubiquiti-unifi-switch-24-pro

    # 从本地文件或目录导入（离线环境）
    python .\\tools\\import_device_types.py --source file --file .\\device-types\\switch.yaml
    python .\\tools\\import_device_types.py --source dir --dir .\\device-types --no-images

图片写入 ``web/assets/device-images/<vendor>/<slug>.<face>.png``，
devicetype-library 的图片是 CC0，可直接内部分发。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from office_asset.device_topology import (  # noqa: E402  (path setup must run first)
    parse_device_type_yaml,
    upsert_device_type,
)
from office_asset.sql import SqlGateway  # noqa: E402


LIBRARY_RAW = "https://raw.githubusercontent.com/netbox-community/devicetype-library/master"
LIBRARY_API = "https://api.github.com/repos/netbox-community/devicetype-library/contents"
IMAGE_DIR = ROOT_DIR / "web" / "assets" / "device-images"
DEFAULT_MYSQL = "mysql"
USER_AGENT = "office-asset-mgmt-devicetype-import"


# --------------------------------------------------------------------- database


def mysql_command(database: str) -> list[str]:
    return [
        os.environ.get("MYSQL_BIN", DEFAULT_MYSQL),
        "--protocol=tcp",
        f"--host={os.environ.get('DB_HOST', '127.0.0.1')}",
        f"--port={os.environ.get('DB_PORT', '3306')}",
        f"--user={os.environ.get('DB_USER', 'root')}",
        f"--database={database}",
        "--default-character-set=utf8mb4",
        "--batch",
        "--raw",
        "--skip-column-names",
        "--silent",
    ]


def run_sql(sql: str, database: str) -> str:
    password = os.environ.get("DB_PASSWORD", "")
    if not password:
        raise RuntimeError("DB_PASSWORD environment variable is required.")
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    completed = subprocess.run(
        mysql_command(database),
        input=sql,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(ROOT_DIR),
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def sql_quote(value: object | None) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"


def text_value(value: object | None) -> str:
    return "" if value is None else str(value).strip()


def sql_int(value: object | None, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def build_gateway(database: str) -> SqlGateway:
    def query_json(sql: str, default: object | None = None) -> object | None:
        output = run_sql(sql, database)
        line = next((item for item in output.splitlines() if item.strip()), "")
        if not line:
            return default
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return default

    return SqlGateway(
        execute=lambda sql: run_sql(sql, database),
        query_json=query_json,
        quote=sql_quote,
        text=text_value,
        integer=sql_int,
    )


# ---------------------------------------------------------------------- sources


class DeviceTypeSource:
    """One importable device type: YAML text plus optional image URLs."""

    def __init__(
        self,
        yaml_text: str,
        *,
        vendor: str = "",
        image_base: str = "",
        reference: str = "",
        source_kind: str = "library",
    ) -> None:
        self.yaml_text = yaml_text
        self.vendor = vendor
        self.image_base = image_base
        self.reference = reference
        self.source_kind = source_kind


class NetBoxLibrarySource:
    """NetBox devicetype-library on GitHub (CC0 device data and images)."""

    name = "netbox"

    def list_vendor(self, vendor: str) -> list[str]:
        payload = _http_json(f"{LIBRARY_API}/{vendor}")
        slugs: list[str] = []
        for item in payload if isinstance(payload, list) else []:
            file_name = str(item.get("name", ""))
            if file_name.endswith(".yaml"):
                slugs.append(file_name[:-5])
        return sorted(slugs)

    def resolve(self, slug: str = "", vendor: str = "", path: str = "") -> list[DeviceTypeSource]:
        if path:
            yaml_text = Path(path).read_text(encoding="utf-8")
            parsed = parse_device_type_yaml(yaml_text)
            vendor = vendor or parsed["manufacturer"]
            slug = parsed["slug"]
        if not slug:
            raise SystemExit("--source netbox 需要 --slug（或用 --list 查看厂商型号）")
        candidates: list[tuple[str, str]] = []
        if vendor:
            candidates.append((vendor, _netbox_file_name(slug, vendor)))
        for split_at in range(1, min(4, len(slug.split("-")))):
            parts = slug.split("-")
            guess_vendor = "".join(word.capitalize() for word in parts[:split_at])
            guess_model = "-".join(word.capitalize() for word in parts[split_at:])
            candidates.append((guess_vendor, guess_model))
        last_error = ""
        for folder, file_name in candidates:
            url = f"{LIBRARY_RAW}/device-types/{folder}/{file_name}.yaml"
            try:
                yaml_text = _http_text(url)
            except Exception as exc:
                last_error = str(exc)
                continue
            return [
                DeviceTypeSource(
                    yaml_text,
                    vendor=folder,
                    image_base=f"{LIBRARY_RAW}/elevation-images/{folder}/{slug}",
                    reference=f"netbox:{folder}/{file_name}",
                )
            ]
        raise SystemExit(f"未能从 devicetype-library 获取 {slug}（{last_error}）")


class LocalFileSource:
    name = "file"

    def resolve(self, slug: str = "", vendor: str = "", path: str = "") -> list[DeviceTypeSource]:
        if not path:
            raise SystemExit("--source file 需要 --file <yaml 路径>")
        target = Path(path)
        if not target.is_file():
            raise SystemExit(f"文件不存在：{target}")
        return [DeviceTypeSource(target.read_text(encoding="utf-8"), vendor=vendor, reference=str(target))]


class LocalDirSource:
    name = "dir"

    def resolve(self, slug: str = "", vendor: str = "", path: str = "") -> list[DeviceTypeSource]:
        if not path:
            raise SystemExit("--source dir 需要 --dir <目录>")
        directory = Path(path)
        if not directory.is_dir():
            raise SystemExit(f"目录不存在：{directory}")
        files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
        if slug:
            files = [item for item in files if slug in item.stem.lower()]
        if not files:
            raise SystemExit(f"{directory} 里没有匹配的 YAML 文件。")
        return [DeviceTypeSource(item.read_text(encoding="utf-8"), vendor=vendor, reference=str(item)) for item in files]


SOURCES: dict[str, object] = {
    NetBoxLibrarySource.name: NetBoxLibrarySource(),
    LocalFileSource.name: LocalFileSource(),
    LocalDirSource.name: LocalDirSource(),
}


def register_source(name: str, source: object) -> None:
    """Register an additional import source (keeps the tool extensible)."""
    SOURCES[name] = source


# ------------------------------------------------------------------ http helpers


def _http_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _http_json(url: str, timeout: int = 20) -> object:
    return json.loads(_http_text(url, timeout))


def _http_bytes(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _netbox_file_name(slug: str, vendor: str) -> str:
    prefix = re.sub(r"[^a-z0-9]+", "-", vendor.lower()).strip("-")
    tail = slug[len(prefix) :].strip("-") if prefix and slug.startswith(prefix) else slug
    return "-".join(word.capitalize() for word in tail.split("-")) or slug


def _vendor_folder(manufacturer: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", manufacturer or "vendor").strip("-")
    return cleaned.lower() or "vendor"


# ---------------------------------------------------------------------- import


def download_images(source: DeviceTypeSource, parsed: dict, target_root: Path) -> dict[str, str]:
    """Download front/rear elevation images; missing images are not an error."""
    if not source.image_base:
        return {}
    folder = target_root / _vendor_folder(parsed["manufacturer"])
    folder.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    for face, flag in (("front", parsed.get("front_image")), ("rear", parsed.get("rear_image"))):
        if not flag:
            continue
        url = f"{source.image_base}.{face}.png"
        try:
            payload = _http_bytes(url)
        except Exception as exc:  # 图片缺失不影响型号与端口导入
            print(f"  图片跳过 {face}：{exc}")
            continue
        file_path = folder / f"{parsed['slug']}.{face}.png"
        file_path.write_bytes(payload)
        relative = file_path.relative_to(ROOT_DIR / "web")
        result[face] = f"/{relative.as_posix()}"
        print(f"  图片写入 {file_path.relative_to(ROOT_DIR)}")
    return result


def import_source(
    source: DeviceTypeSource,
    db: SqlGateway,
    database: str,
    *,
    download: bool,
    dry_run: bool,
    actor: str,
) -> dict:
    parsed = parse_device_type_yaml(source.yaml_text)
    print(
        f"- {parsed['manufacturer']} {parsed['model']}（{parsed['slug']}）："
        f"{len(parsed['ports'])} 个端口，{parsed['u_height']}U，{parsed['category']}"
    )
    if dry_run:
        return {"slug": parsed["slug"], "dryRun": True}
    images = download_images(source, parsed, IMAGE_DIR) if download else {}
    result = upsert_device_type(
        db,
        parsed,
        source=source.source_kind,
        source_ref=source.reference,
        image_paths=images,
    )
    db.execute(
        f"""
        INSERT INTO audit_log (
          action_type, entity_type, entity_id, entity_name,
          old_value, new_value, summary, actor, source
        )
        VALUES (
          'device_type_imported',
          'device_type_catalog',
          {sql_quote(result['catalogId'])},
          {sql_quote(f"{parsed['manufacturer']} {parsed['model']}".strip())},
          {sql_quote('{}')},
          {json_quote({'slug': parsed['slug'], 'portCount': result['portCount'], 'source': source.reference})},
          {sql_quote(f"命令行导入型号：{parsed['slug']}（{result['portCount']} 个端口模板）")},
          {sql_quote(actor)},
          'cli'
        );
        """
    )
    return result


def json_quote(value: object) -> str:
    return sql_quote(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入设备型号（含端口模板与面板图）")
    parser.add_argument("--source", default="netbox", choices=sorted(SOURCES))
    parser.add_argument("--slug", default="", help="型号 slug，例如 ubiquiti-unifi-switch-24-pro")
    parser.add_argument("--vendor", default="", help="厂商目录名，例如 Ubiquiti")
    parser.add_argument("--file", default="", help="source=file 时的 YAML 路径")
    parser.add_argument("--dir", default="", help="source=dir 时的目录")
    parser.add_argument("--list", action="store_true", help="只列出厂商型号，不导入")
    parser.add_argument("--no-images", action="store_true", help="不下载面板图片")
    parser.add_argument("--dry-run", action="store_true", help="只解析不写库")
    parser.add_argument("--database", default=os.environ.get("DB_NAME", "office_asset_mgmt"))
    parser.add_argument("--actor", default="cli:import_device_types")
    args = parser.parse_args(argv)

    source = SOURCES[args.source]
    if args.list:
        if not hasattr(source, "list_vendor"):
            raise SystemExit(f"{args.source} 不支持 --list")
        if not args.vendor:
            raise SystemExit("--list 需要 --vendor")
        for slug in source.list_vendor(args.vendor):  # type: ignore[attr-defined]
            print(slug)
        return 0

    path = args.file or args.dir
    sources = source.resolve(slug=args.slug, vendor=args.vendor, path=path)  # type: ignore[attr-defined]
    if not sources:
        raise SystemExit("没有找到可导入的型号。")
    if args.dry_run:
        for item in sources:
            import_source(item, None, args.database, download=False, dry_run=True, actor=args.actor)  # type: ignore[arg-type]
        return 0
    db = build_gateway(args.database)
    imported = 0
    for item in sources:
        result = import_source(
            item,
            db,
            args.database,
            download=not args.no_images,
            dry_run=False,
            actor=args.actor,
        )
        imported += 1
        print(f"  已写入 catalog_id={result['catalogId']}，端口 {result['portCount']} 个")
    print(f"完成：导入 {imported} 个型号。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
