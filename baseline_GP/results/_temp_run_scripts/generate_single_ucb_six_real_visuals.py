from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(r"F:\pythonprojects")
sys.path.insert(0, str(ROOT))

from baseline_GP.marine_knownmap_runtime import run_episode_single_usv_search_knownmap

IMAGES_DIR = ROOT / "images"
TMP_DIR = ROOT / "baseline_GP" / "results" / "_temp_run_scripts" / "_single_ucb_six_real_visuals"

POLICY = "marine_knownmap_path_v2_infosampled"
MAPS = ("open_water", "obstacle_field", "peninsula_passage")
MOTIONS = ("static", "random_walk")
SEED = 0
MAX_ITERS = 240


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for map_kind in MAPS:
        for motion in MOTIONS:
            scenario = f"{map_kind}_{motion}"
            out_dir = TMP_DIR / scenario
            out_dir.mkdir(parents=True, exist_ok=True)
            result = run_episode_single_usv_search_knownmap(
                episode_seed=SEED,
                max_iters=MAX_ITERS,
                policy_name=POLICY,
                map_kind=map_kind,
                target_motion_mode=motion,
                clue_acquisition_mode="ucb",
                viewpoint_generation_mode="simple_ring_v1",
                path_safety_mode="soft_clearance_astar_v1",
                anomaly_tail_quantile=0.90,
                anomaly_weight_lambda=1.25,
                save_artifacts=True,
                output_dir=str(out_dir),
            )
            src = out_dir / f"episode_{POLICY}_seed_{SEED:03d}.png"
            dst = IMAGES_DIR / f"single_ucb_{map_kind}_{motion}_seed{SEED:03d}_final.png"
            if not src.exists():
                raise FileNotFoundError(src)
            shutil.copy2(src, dst)
            outputs.append(dst)
            print(
                f"{dst} | success={result.get('success_all_found')} "
                f"found={result.get('found_count')} steps={result.get('completed_steps')}"
            )

    print("generated_count", len(outputs))


if __name__ == "__main__":
    main()
