from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "baseline_GP").is_dir():
            return parent
    raise RuntimeError("Could not locate repository root containing baseline_GP")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baseline_GP.core_map import create_world  # noqa: E402
from baseline_GP.holoocean_bridge.coordinate_adapter import (  # noqa: E402
    CoordinateAdapterConfig,
    grid_to_world,
    project_world_to_nearest_free_cell,
    world_to_grid,
)


PHASE_DIR = REPO_ROOT / "baseline_GP" / "results" / "holoocean_bridge_v1" / "phase2_coordinate_bridge"
REPORT_DIR = PHASE_DIR / "reports"
MANIFEST_DIR = PHASE_DIR / "manifests"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    config = CoordinateAdapterConfig(cell_size_m=5.0)
    nav_map_prior = create_world(h=60, w=80, map_kind="obstacle_field")
    starts = [(25, 2), (35, 2)]

    start_checks = []
    for cell in starts:
        world = grid_to_world(cell, config)
        round_trip = world_to_grid(world, config, map_shape=nav_map_prior.shape)
        projected = project_world_to_nearest_free_cell(world, nav_map_prior, config)
        start_checks.append(
            {
                "cell": list(cell),
                "world_xyz": [float(v) for v in world],
                "round_trip_cell": list(round_trip),
                "projected_free_cell": list(projected),
                "round_trip_ok": tuple(round_trip) == tuple(cell),
                "projected_is_free": int(nav_map_prior[projected]) == 0,
            }
        )

    checks = {
        "generated_at": datetime.now().isoformat(),
        "map_kind": "obstacle_field",
        "map_shape": list(nav_map_prior.shape),
        "config": {
            "cell_size_m": config.cell_size_m,
            "origin_world_xy": list(config.origin_world_xy),
            "water_surface_z": config.water_surface_z,
        },
        "two_usv_start_checks": start_checks,
        "all_round_trips_ok": all(item["round_trip_ok"] for item in start_checks),
        "all_projected_cells_free": all(item["projected_is_free"] for item in start_checks),
    }

    checks_path = MANIFEST_DIR / "phase2_coordinate_bridge_checks.json"
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")

    rows = [
        "# Phase 2 Coordinate Bridge Smoke Summary",
        "",
        f"**Generated at:** {checks['generated_at']}",
        "",
        "## Configuration",
        "",
        "| Item | Value |",
        "|------|-------|",
        f"| Map kind | `{checks['map_kind']}` |",
        f"| Map shape | `{tuple(nav_map_prior.shape)}` |",
        f"| cell_size_m | `{config.cell_size_m}` |",
        f"| origin_world_xy | `{config.origin_world_xy}` |",
        f"| water_surface_z | `{config.water_surface_z}` |",
        "",
        "## Two-USV Start Mapping",
        "",
        "| Cell | World [x, y, z] | Round-trip | Projected free cell |",
        "|------|-----------------|------------|---------------------|",
    ]
    for item in start_checks:
        rows.append(
            f"| `{tuple(item['cell'])}` | `{item['world_xyz']}` | "
            f"`{tuple(item['round_trip_cell'])}` | `{tuple(item['projected_free_cell'])}` |"
        )

    rows.extend(
        [
            "",
            "## Conclusions",
            "",
            f"- All round-trips ok: **{checks['all_round_trips_ok']}**",
            f"- All projected cells free: **{checks['all_projected_cells_free']}**",
            "- HoloOcean was not imported or launched in this phase.",
        ]
    )

    (REPORT_DIR / "phase2_coordinate_bridge_summary.md").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    if not checks["all_round_trips_ok"] or not checks["all_projected_cells_free"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
