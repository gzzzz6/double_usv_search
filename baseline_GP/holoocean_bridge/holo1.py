#手动控制方案



import holoocean
import cv2
import numpy as np
from pynput import keyboard

name0 = "usv0"

config = {
    "name": "test",
    "world": "OpenWater",
    "package_name": "Ocean",
    "main_agent": name0,
    "agents": [
        {
            "agent_name": name0,
            "agent_type": "SurfaceVessel",
            "sensors": [
                {
                    "sensor_type": "LocationSensor",
                    "socket": "COM",
                    "configuration": {
                        "Sigma": 0
                    }
                },
                {
                    "sensor_type": "OrientationSensor",
                    "socket": "COM",
                },
                {
                    "sensor_type": "RGBCamera",  # 水上摄像头
                    "sensor_name": "USV_Camera_Top",
                    "location": [0.0, 0.0, 5.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "Hz": 10,
                    "configuration": {
                        "CaptureWidth": 512,
                        "CaptureHeight": 512
                    }
                },
                {
                    "sensor_type": "RGBCamera",  # 水下摄像头
                    "sensor_name": "USV_Camera_Bottom",
                    "location": [0.0, 0.0, -5.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "Hz": 10,
                    "configuration": {
                        "CaptureWidth": 512,
                        "CaptureHeight": 512
                    }
                }
            ],
            "control_scheme": 0,
            "location": [0, 0, 0],
            "rotation": [0, 0, 0]  # 决定初始朝向
        },
        {
            "agent_name": "auv0",
            "agent_type": "HoveringAUV",  # 水下机器人
            "sensors": [
                {
                    "sensor_type": "DVLSensor"
                }
            ],
            "control_scheme": 0,
            "location": [50, 0, -5]
        },
        {
            "agent_name": "auv1",
            "agent_type": "TorpedoAUV",  # 水下鱼雷
            "sensors": [
                {
                    "sensor_type": "IMUSensor"
                }
            ],
            "control_scheme": 0,
            "location": [25, 0, -5],
            "rotation": [0, 0, 30]
        },
        {
            "agent_name": "usv1",
            "agent_type": "SurfaceVessel",  # 水面船
            "sensors": [
                {
                    "sensor_type": "IMUSensor"
                }
            ],
            "control_scheme": 0,
            "location": [25, 5, 0]
        }
    ]
}


def parse_keys(keys, val):
    command = np.zeros(2)
    if 'w' in keys:
        command[:] += val
    if 's' in keys:
        command[:] -= val
    if 'a' in keys:
        command[0] -= val
        command[1] += val
    if 'd' in keys:
        command[0] += val
        command[1] -= val
    return command


def on_press(key):
    global pressed_keys
    if hasattr(key, 'char'):
        pressed_keys.append(key.char)
        pressed_keys = list(set(pressed_keys))


def on_release(key):
    global pressed_keys
    if hasattr(key, 'char'):
        pressed_keys.remove(key.char)


pressed_keys = list()
listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release)
listener.start()

# 创建两个显示窗口
cv2.namedWindow("USV Camera Top View", cv2.WINDOW_NORMAL)
cv2.namedWindow("USV Camera Bottom View", cv2.WINDOW_NORMAL)

with holoocean.make(scenario_cfg=config) as env:
    force = 10000
    step_count = 0

    # --- 存储上一步航向角，用于计算变化 ---
    previous_heading_deg = None

    while True:
        if 'q' in pressed_keys:
            break

        command = parse_keys(pressed_keys, force)
        env.act(name0, command)
        state = env.tick()
        step_count += 1

        print(f"Step {step_count} | 控制命令: [{command[0]:5.0f}, {command[1]:5.0f}]")

        # 获取usv0的位置
        if name0 in state and "LocationSensor" in state[name0]:
            position = state[name0]["LocationSensor"]  # 标准访问路径
            print(f"  位置: [{position[0]:6.1f}, {position[1]:6.1f}, {position[2]:6.1f}]")
        else:
            print(f"  位置: 数据未找到")

        # 获取usv0的航向
        if name0 in state and "OrientationSensor" in state[name0]:
            orientation_matrix = state[name0]["OrientationSensor"]  # 标准访问路径

            # 1. 提取前向向量
            forward = orientation_matrix[:, 0]

            # 2. 计算航向角（基于世界坐标系）
            # 定义：世界坐标系 +X 轴方向为 "正北 (0°)"
            # 公式：航向角 = atan2(前向向量的Y分量, 前向向量的X分量)
            heading_rad = np.arctan2(forward[1], forward[0])
            heading_deg = np.degrees(heading_rad)

            # 3. 将角度归一化到 [0, 360) 度范围，更符合导航习惯
            heading_deg_normalized = heading_deg % 360.0

            # 4. 计算航向变化（相对于上一步）
            heading_change_deg = None
            if previous_heading_deg is not None:
                # 计算角度差，并调整到 [-180, 180] 度范围，避免跨360°时的跳变
                raw_change = heading_deg_normalized - previous_heading_deg
                heading_change_deg = (raw_change + 180) % 360 - 180

            # 5. 输出航向信息
            print(f"  船头航向: {heading_deg_normalized:6.1f}° (正北=0°, 正西=90°)")

            # 6. 为下一步存储当前航向
            previous_heading_deg = heading_deg_normalized

        else:
            print(f"  航向: 数据未找到")

        # 新增：获取并显示usv0的两个摄像头图像
        # 第一个摄像头（水上摄像头）
        if name0 in state and "USV_Camera_Top" in state[name0]:
            # 获取图像数据
            pixels_top = state[name0]["USV_Camera_Top"]

            # 检查图像维度并确保是3通道（BGR格式）
            if len(pixels_top.shape) == 3:
                # 如果是4通道（RGBA），则只取前3个通道
                if pixels_top.shape[2] == 4:
                    pixels_top = pixels_top[:, :, 0:3]

                # 显示图像
                cv2.imshow("USV Camera Top View", pixels_top)
                print("  水上摄像头: 图像显示正常")
            else:
                print(f"  水上摄像头: 图像维度异常 {pixels_top.shape}")
        else:
            print(f"  水上摄像头: 数据未找到")

        # 第二个摄像头（水下摄像头）
        if name0 in state and "USV_Camera_Bottom" in state[name0]:
            # 获取图像数据
            pixels_bottom = state[name0]["USV_Camera_Bottom"]

            # 检查图像维度并确保是3通道（BGR格式）
            if len(pixels_bottom.shape) == 3:
                # 如果是4通道（RGBA），则只取前3个通道
                if pixels_bottom.shape[2] == 4:
                    pixels_bottom = pixels_bottom[:, :, 0:3]

                # 显示图像
                cv2.imshow("USV Camera Bottom View", pixels_bottom)
                print("  水下摄像头: 图像显示正常")
            else:
                print(f"  水下摄像头: 图像维度异常 {pixels_bottom.shape}")
        else:
            print(f"  水下摄像头: 数据未找到")

        # 检查OpenCV窗口是否收到'q'键
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            # 如果OpenCV窗口收到'q'键，也退出
            pressed_keys.append('q')

        print("-" * 60)

# 清理资源
cv2.destroyAllWindows()
listener.stop()
print("程序执行完毕")