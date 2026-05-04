from __future__ import annotations

import argparse
import sys

sys.path.insert(0, r"F:\pythonprojects")

from baseline_GP import two_usv_coordinated_post_avoidance_anomaly as runner
from baseline_GP.marine_knownmap_runtime_2usv import PHASE7_SYSTEM_TWO_USV_INDEPENDENT


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 2-USV independent post-avoidance anomaly comparison."
    )
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--max_iters", type=int, default=None)
    parser.add_argument(
        "--motion_mode",
        type=str,
        default=runner.DEFAULT_POST_AVOIDANCE_MOTION_MODE,
        choices=("static", "random_walk"),
    )
    parser.add_argument(
        "--no_resume",
        action="store_true",
        help="Disable resume_if_available and rerun from scratch inside the target output_dir.",
    )
    args = parser.parse_args()

    runner.POST_AVOIDANCE_ASSIGNMENT_MODE = "independent"
    runner.PHASE7_SYSTEM_TWO_USV_COORDINATED = PHASE7_SYSTEM_TWO_USV_INDEPENDENT

    result = runner.run_two_usv_coordinated_post_avoidance_anomaly_comparison(
        output_dir=args.output_dir,
        max_iters=args.max_iters,
        motion_mode=args.motion_mode,
        resume_if_available=not bool(args.no_resume),
    )
    print(f"two_usv_independent_post_avoidance_output_dir={result.get('output_dir')}")


if __name__ == "__main__":
    main()
