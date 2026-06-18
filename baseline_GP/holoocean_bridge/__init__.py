"""Bridge utilities for running baseline_GP decisions in HoloOcean shells."""


from baseline_GP.holoocean_bridge.coordinate_adapter import (
    CoordinateAdapterConfig,
    grid_to_world,
    world_to_grid,
    grid_path_to_world,
    project_world_to_nearest_free_cell,
)
from baseline_GP.holoocean_bridge.scene_map_adapter import (
    load_scene_map_spec,
    scene_map_config_from_spec,
    build_scene_occupancy_grid,
    save_scene_map_npz,
    load_scene_map_npz,
    scene_map_world_bounds,
    validate_scene_map,
)
from baseline_GP.holoocean_bridge.scenario_builder import build_surface_vessel_scenario
from baseline_GP.holoocean_bridge.execution_backend import (
    get_sensor_vector,
    send_action,
    step_main_agent_waypoint,
    run_waypoint_sequence,
    run_single_grid_cell_waypoint,
)
from baseline_GP.holoocean_bridge.single_usv_policy_adapter import (
    load_openwater_policy_state,
    plan_next_policy_cell,
    finalize_policy_step_after_holoocean,
)
from baseline_GP.holoocean_bridge.mainline_perception_adapter import (
    MainlineAdapterStepInput,
    MainlineAdapterStepOutput,
    ReusableMainlinePerceptionAdapter,
    mainline_perception_adapter_contract,
)
