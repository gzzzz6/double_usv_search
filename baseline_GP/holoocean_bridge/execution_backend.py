"""Execution backend for running SurfaceVessel waypoint sequences in HoloOcean."""

import math
from typing import List, Tuple, Dict, Any

import numpy as np

from baseline_GP.holoocean_bridge.coordinate_adapter import (
    CoordinateAdapterConfig,
    grid_to_world,
    world_to_grid,
)


def get_sensor_vector(state: dict, agent_name: str, sensor_name: str) -> Any:
    """Retrieve sensor output from HoloOcean state supporting flat and nested structures.

    Args:
        state: The environment state dictionary returned by env.tick().
        agent_name: The name of the agent.
        sensor_name: The sensor identifier (e.g. 'GPSSensor', 'LocationSensor').

    Returns:
        Any: The sensor data if found, otherwise None.
    """
    # 1. Try agent-nested structure
    if agent_name in state and isinstance(state[agent_name], dict):
        if sensor_name in state[agent_name]:
            return state[agent_name][sensor_name]

    # 2. Try flat structure
    if sensor_name in state:
        return state[sensor_name]

    return None


def send_action(env: Any, agent_name: str, command: Any) -> None:
    """Send an action command to a specific agent in the environment.

    Args:
        env: The HoloOcean environment instance.
        agent_name: The agent identifier.
        command: The command vector to send.
    """
    env.act(agent_name, command)


def step_main_agent_waypoint(env: Any, command: Any) -> dict:
    """Send target command to the main agent and step the simulator by one tick.

    Args:
        env: The HoloOcean environment instance.
        command: The target command (usually [target_x, target_y] for scheme 1).

    Returns:
        dict: The updated state dictionary from env.tick().
    """
    # Determine the agent name dynamically
    agent_name = "sv"
    if hasattr(env, "_scenario_cfg") and isinstance(env._scenario_cfg, dict):
        agent_name = env._scenario_cfg.get("main_agent", agent_name)
    elif hasattr(env, "agents") and env.agents:
        if isinstance(env.agents, dict):
            agent_name = list(env.agents.keys())[0]
        elif isinstance(env.agents, list):
            agent_name = env.agents[0]

    env.act(agent_name, command)
    return env.tick()


def run_waypoint_sequence(
    env: Any,
    agent_name: str,
    waypoint_cells: List[Tuple[int, int]],
    adapter_config: CoordinateAdapterConfig,
    nav_map_prior: np.ndarray,
    arrival_radius_m: float = 2.5,
    max_ticks_per_waypoint: int = 1500,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute a series of grid waypoints sequentially on a SurfaceVessel.

    Args:
        env: The HoloOcean environment instance.
        agent_name: Name of the SurfaceVessel agent.
        waypoint_cells: List of grid cell coordinates [(r1, c1), (r2, c2), ...] to visit.
        adapter_config: Configured coordinate adapter.
        nav_map_prior: The 2D occupancy grid used for boundaries and mapping validation.
        arrival_radius_m: Distance threshold in meters to consider waypoint reached.
        max_ticks_per_waypoint: Max ticks allowed to reach a waypoint before timeout.

    Returns:
        Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: 
            - A list of per-tick telemetry trace entries.
            - A list of per-waypoint execution summaries.
    """
    trace_log = []
    waypoint_summaries = []
    
    tick_global = 0
    map_shape = nav_map_prior.shape

    print(f"Starting execution of {len(waypoint_cells)} waypoints...")

    for wp_idx, cell in enumerate(waypoint_cells):
        target_row, target_col = cell
        # Convert target grid cell to physical world coordinates
        target_pos_3d = grid_to_world(cell, config=adapter_config)
        target_x, target_y = float(target_pos_3d[0]), float(target_pos_3d[1])

        print(f"Targeting Waypoint {wp_idx}: cell={cell} -> world=[{target_x:.2f}, {target_y:.2f}]")

        wp_ticks = 0
        arrived = False
        timeout = False
        
        # We will log the start of the waypoint
        last_x, last_y, last_z = 0.0, 0.0, 0.0

        while not arrived and not timeout:
            # Control command for control_scheme = 1: target physical location [x, y]
            command = np.array([target_x, target_y], dtype=np.float32)
            
            # Act and tick
            state = step_main_agent_waypoint(env, command)
            
            tick_global += 1
            wp_ticks += 1

            # Read current location from sensors
            loc_data = get_sensor_vector(state, agent_name, "LocationSensor")
            gps_data = get_sensor_vector(state, agent_name, "GPSSensor")
            
            # Prefer LocationSensor for ground truth; fall back to GPSSensor
            curr_pos = loc_data if loc_data is not None else gps_data
            
            if curr_pos is not None:
                curr_x, curr_y, curr_z = float(curr_pos[0]), float(curr_pos[1]), float(curr_pos[2])
                last_x, last_y, last_z = curr_x, curr_y, curr_z
            else:
                curr_x, curr_y, curr_z = last_x, last_y, last_z

            # Compute 2D Euclidean distance to target
            dist = math.sqrt((curr_x - target_x) ** 2 + (curr_y - target_y) ** 2)

            # Project current physical position back to grid coordinates
            try:
                proj_row, proj_col = world_to_grid([curr_x, curr_y, curr_z], adapter_config, map_shape)
            except ValueError:
                # If mapped outside bounds, clamp to map boundaries
                proj_row, proj_col = world_to_grid([curr_x, curr_y, curr_z], adapter_config, map_shape, clamp=True)

            # Check termination conditions
            if dist < arrival_radius_m:
                arrived = True
            elif wp_ticks >= max_ticks_per_waypoint:
                timeout = True

            # Record telemetry entry
            trace_entry = {
                "tick_global": tick_global,
                "waypoint_index": wp_idx,
                "target_row": int(target_row),
                "target_col": int(target_col),
                "target_x": target_x,
                "target_y": target_y,
                "location_x": curr_x,
                "location_y": curr_y,
                "location_z": curr_z,
                "gps_x": float(gps_data[0]) if gps_data is not None else curr_x,
                "gps_y": float(gps_data[1]) if gps_data is not None else curr_y,
                "gps_z": float(gps_data[2]) if gps_data is not None else curr_z,
                "projected_row": int(proj_row),
                "projected_col": int(proj_col),
                "distance_to_target_m": dist,
                "arrived": arrived,
                "timeout": timeout,
            }
            trace_log.append(trace_entry)

        # End of waypoint log
        status_str = "ARRIVED" if arrived else "TIMEOUT"
        print(f"Waypoint {wp_idx} finished in {wp_ticks} ticks. Status: {status_str}, final distance: {trace_log[-1]['distance_to_target_m']:.2f}m")
        
        wp_summary = {
            "waypoint_index": wp_idx,
            "target_cell": [int(target_row), int(target_col)],
            "target_world": [target_x, target_y],
            "final_world": [last_x, last_y, last_z],
            "final_projected_cell": [trace_log[-1]["projected_row"], trace_log[-1]["projected_col"]],
            "ticks": wp_ticks,
            "arrived": arrived,
            "timeout": timeout,
        }
        waypoint_summaries.append(wp_summary)

    return trace_log, waypoint_summaries


def run_single_grid_cell_waypoint(
    env: Any,
    agent_name: str,
    target_cell: Tuple[int, int],
    adapter_config: CoordinateAdapterConfig,
    nav_map_prior: np.ndarray,
    arrival_radius_m: float = 2.5,
    max_ticks: int = 800,
    tick_offset: int = 0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Steer a SurfaceVessel to the physical world waypoint of a single grid cell.

    Args:
        env: The HoloOcean environment instance.
        agent_name: Name of the SurfaceVessel agent.
        target_cell: The targeted grid cell (row, col).
        adapter_config: CoordinateAdapterConfig for grid/world conversion.
        nav_map_prior: The 2D occupancy grid used for boundaries and mapping validation.
        arrival_radius_m: Arrival radius in meters. Default 2.5m (perfect half-cell tolerance).
        max_ticks: Maximum ticks allowed to reach the cell waypoint. Default 800.
        tick_offset: Global tick accumulator offset for trace logging.

    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, Any]]:
            - A list of per-tick telemetry trace entries.
            - A summary dict of the step execution.
    """
    trace_log = []
    map_shape = nav_map_prior.shape
    target_row, target_col = target_cell

    # Convert target grid cell to physical world coordinates
    target_pos_3d = grid_to_world(target_cell, config=adapter_config)
    target_x, target_y = float(target_pos_3d[0]), float(target_pos_3d[1])

    wp_ticks = 0
    arrived = False
    timeout = False
    last_x, last_y, last_z = 0.0, 0.0, 0.0

    while not arrived and not timeout:
        # Control command: target physical location [x, y]
        command = np.array([target_x, target_y], dtype=np.float32)
        
        # Step simulator by one tick
        state = step_main_agent_waypoint(env, command)
        
        wp_ticks += 1
        tick_global = tick_offset + wp_ticks

        # Read current location from sensors
        loc_data = get_sensor_vector(state, agent_name, "LocationSensor")
        gps_data = get_sensor_vector(state, agent_name, "GPSSensor")
        
        curr_pos = loc_data if loc_data is not None else gps_data
        
        if curr_pos is not None:
            curr_x, curr_y, curr_z = float(curr_pos[0]), float(curr_pos[1]), float(curr_pos[2])
            last_x, last_y, last_z = curr_x, curr_y, curr_z
        else:
            curr_x, curr_y, curr_z = last_x, last_y, last_z

        # Compute 2D Euclidean distance to target
        dist = math.sqrt((curr_x - target_x) ** 2 + (curr_y - target_y) ** 2)

        # Project current physical position back to grid coordinates
        try:
            proj_row, proj_col = world_to_grid([curr_x, curr_y, curr_z], adapter_config, map_shape)
        except ValueError:
            proj_row, proj_col = world_to_grid([curr_x, curr_y, curr_z], adapter_config, map_shape, clamp=True)

        # Check termination conditions
        if dist < arrival_radius_m:
            arrived = True
        elif wp_ticks >= max_ticks:
            timeout = True

        # Record telemetry entry
        trace_entry = {
            "tick_global": tick_global,
            "waypoint_index": 0,  # Single waypoint context
            "target_row": int(target_row),
            "target_col": int(target_col),
            "target_x": target_x,
            "target_y": target_y,
            "location_x": curr_x,
            "location_y": curr_y,
            "location_z": curr_z,
            "gps_x": float(gps_data[0]) if gps_data is not None else curr_x,
            "gps_y": float(gps_data[1]) if gps_data is not None else curr_y,
            "gps_z": float(gps_data[2]) if gps_data is not None else curr_z,
            "projected_row": int(proj_row),
            "projected_col": int(proj_col),
            "distance_to_target_m": dist,
            "arrived": arrived,
            "timeout": timeout,
        }
        trace_log.append(trace_entry)

    wp_summary = {
        "target_cell": [int(target_row), int(target_col)],
        "target_world": [target_x, target_y],
        "final_world": [last_x, last_y, last_z],
        "final_projected_cell": [trace_log[-1]["projected_row"], trace_log[-1]["projected_col"]],
        "ticks": wp_ticks,
        "arrived": arrived,
        "timeout": timeout,
    }

    return trace_log, wp_summary

