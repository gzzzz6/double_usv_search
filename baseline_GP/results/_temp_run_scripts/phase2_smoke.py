from baseline_GP.marine_knownmap_runtime import run_episode_single_usv_search_knownmap
from baseline_GP.marine_knownmap_runtime_2usv import run_episode_two_usv_search_knownmap

single = run_episode_single_usv_search_knownmap(
    episode_seed=0,
    max_iters=20,
    policy_name="marine_knownmap_path_v2_infosampled",
    n_targets=3,
    map_kind="obstacle_field",
    map_height_cells=40,
    map_width_cells=60,
    target_motion_mode="static",
    clue_acquisition_mode="ucb",
    path_safety_mode="soft_clearance_astar_v1",
    viewpoint_generation_mode="simple_ring_v1",
    render=False,
    save_artifacts=False,
)
print("single_ok", single.get("map_kind"), single.get("policy_name"), single.get("path_safety_mode"), single.get("viewpoint_generation_mode"), single.get("found_count"))

two = run_episode_two_usv_search_knownmap(
    episode_seed=0,
    max_iters=20,
    policy_name="marine_knownmap_path_v2_infosampled_2usv",
    assignment_mode="coordinated",
    n_targets=3,
    map_kind="obstacle_field",
    map_height_cells=60,
    map_width_cells=80,
    target_motion_mode="static",
    clue_acquisition_mode="ucb",
    path_safety_mode="soft_clearance_astar_v1",
    team_path_avoidance_mode="reservation_v1",
    viewpoint_generation_mode="simple_ring_v1",
    render=False,
)
print("two_ok", two.get("map_kind"), two.get("policy_name"), two.get("assignment_mode"), two.get("team_path_avoidance_mode"), two.get("found_count"))
