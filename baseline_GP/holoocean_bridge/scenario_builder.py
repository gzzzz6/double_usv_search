"""Builder for constructing HoloOcean simulator scenario configurations."""

from typing import List, Union, Tuple, Dict, Any


def build_surface_vessel_scenario(
    agent_name: str,
    world: str = "OpenWater",
    package_name: str = "Ocean",
    start_world: Union[List[float], Tuple[float, float, float]] = (0.0, 0.0, 0.0),
    control_scheme: int = 1,
    sensors: List[Dict[str, Any]] = None,
) -> dict:
    """Build a configuration dictionary for a single SurfaceVessel scenario in HoloOcean.

    Args:
        agent_name: The unique string identifier for the main agent.
        world: The HoloOcean world name (default: "OpenWater").
        package_name: The HoloOcean package containing the world (default: "Ocean").
        start_world: The initial 3D coordinate (x, y, z) of the vessel in world space.
        control_scheme: The control scheme index (default: 1 for waypoint input [x, y]).
        sensors: A list of sensor configuration dictionaries. If None, defaults to
                 containing both GPSSensor and LocationSensor.

    Returns:
        dict: A fully populated HoloOcean scenario configuration dictionary.
    """
    if sensors is None:
        sensors = [
            {
                "sensor_type": "GPSSensor",
                "socket": "COM"
            },
            {
                "sensor_type": "LocationSensor",
                "socket": "COM"
            }
        ]

    # Normalize start_world to a list
    start_location = list(start_world)
    if len(start_location) != 3:
        raise ValueError("start_world must represent a 3D coordinate (length 3)")

    scenario_cfg = {
        "name": f"{agent_name}_waypoint_smoke",
        "world": world,
        "package_name": package_name,
        "main_agent": agent_name,
        "agents": [
            {
                "agent_name": agent_name,
                "agent_type": "SurfaceVessel",
                "sensors": sensors,
                "control_scheme": control_scheme,
                "location": start_location,
                "rotation": [0.0, 0.0, 0.0]
            }
        ]
    }

    return scenario_cfg
