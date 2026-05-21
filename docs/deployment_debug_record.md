# QuestArmTeleop 项目部署调试记录

## 环境信息

| 项目 | 值 |
|------|-----|
| 系统 | Ubuntu 22.04 (Linux 6.8.0) |
| ROS2 版本 | Humble |
| 机械臂型号 | Nero |
| CAN 接口 | can0, 波特率 1000000 |
| conda 环境 | vt (Python 3.10.12) |
| conda base | Python 3.13.11 (与 ROS2 不兼容) |

---

## 问题排查与解决

### 1. colcon build 失败 — conda Python 版本冲突

**现象：**
```
ModuleNotFoundError: No module named 'catkin_pkg'
ModuleNotFoundError: No module named 'em'
```

**原因：** conda base 环境激活时，python3 指向 Python 3.13，而 ROS2 Humble 的 C 扩展和依赖都是为 Python 3.10 编译的。CMake 缓存了 conda 的 Python 路径，导致即使手动改 PATH 也无效。

**解决：** 清理 build 目录，用系统 Python 编译：
```bash
cd ~/QuestArmTeleop
rm -rf build install log
colcon build
```

**永久方案：**
```bash
conda config --set auto_activate_base false
```

### 2. oculus_reader 包未安装

**现象：** ros2 launch 报 Package 'oculus_reader' not found

**原因：** 首次编译时 oculus_reader 虽然 build 成功但未被正确安装到 install/ 目录。

**解决：** 重新执行 colcon build，确认 install/ 下包含 oculus_reader。

### 3. 缺少 ros-humble-xacro

**现象：** file not found: xacro

**解决：**
```bash
sudo apt install -y ros-humble-xacro
```

### 4. 缺少 can-utils

**现象：** CAN 激活脚本报错 ethtool / can-utils not detected

**解决：**
```bash
sudo apt install -y can-utils
```

### 5. pyAgxArm 未安装到 vt conda 环境

**现象：** ModuleNotFoundError: No module named 'pyAgxArm'

**原因：** pyAgxArm 仅安装在 base conda 环境（/home/yuhang/projects/pyAgxArm，editable 模式），vt 环境没有。

**解决：**
```bash
conda run -n vt pip install -e /home/yuhang/projects/pyAgxArm
```

### 6. rclpy C 扩展加载失败

**现象：** ModuleNotFoundError: No module named 'rclpy._rclpy_pybind11'

**原因：** 启动 launch 时 conda base（Python 3.13）仍然优先于 vt（Python 3.10），导致 ROS2 的 .cpython-310.so 扩展无法被 3.13 加载。

**解决：** 确保启动前切换到 vt 环境：
```bash
conda deactivate
conda activate vt
```

### 7. CAN 接口意外 DOWN

**现象：** RuntimeError: CAN port can0 is not UP.

**原因：** CAN 接口在某时刻掉线（可能因 USB 松动或系统休眠）。

**解决：**
```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

---

## 硬件链路验证结果

通过 pyAgxArm 直接测试 CAN 通信：

| 步骤 | 结果 |
|------|------|
| CAN 连接 | 成功 |
| 关节使能 | 成功 (True) |
| 读取关节角度 | 成功 |
| 发送运动指令 | 能发出，但 joint4 已接近极限值被拒绝 |

当前关节角度（测试时）：

| 关节 | rad | deg |
|------|-----|-----|
| joint1 | 0.0913 | 5.2 |
| joint2 | -0.509 | -29.2 |
| joint3 | -0.0769 | -4.4 |
| joint4 | 2.1732 | 124.5 |
| joint5 | -0.106 | -6.1 |
| joint6 | 0.113 | 6.5 |
| joint7 | 1.2419 | 71.2 |

> joint4 已接近上限 2.147 rad (123°)，微调测试需选择余量较大的关节（如 joint1）。

---

## 正确启动流程

```bash
# 1. 确保 CAN 接口 UP
ip link show can0

# 2. 激活 vt conda 环境
conda deactivate
conda activate vt

# 3. 编译（如代码有改动）
cd ~/QuestArmTeleop
colcon build

# 4. 启动遥操
source ~/QuestArmTeleop/install/setup.bash
ros2 launch oculus_reader teleop_single_nero.launch.py
```

---

### 8. move_to_init_pose.py 脚本运行失败

**现象：**
```
[INFO] [move_to_init_pose]: Target pose (deg): j2=-30, j4=120, rest=0  |  rad: [0.0, -0.5236, 0.0, 2.0944, 0.0, 0.0, 0.0]
[INFO] [move_to_init_pose]: Publishing /control/move_j ...
[INFO] [move_to_init_pose]: Done. Press Ctrl+C to exit.
rclpy._rclpy_pybind11.RCLError: failed to shutdown: rcl_shutdown already called on the given context
```

**原因：** 两个问题叠加导致：

1. **消息丢失** — 脚本只调用了一次 `pub.publish(msg)`，ROS2 topic 是 "fire and forget" 模式。如果 publish 时 `agx_arm_ctrl` 节点还没建立好订阅连接，消息直接丢弃，机械臂不会动。`create_publisher` 的 queue_size=1 更加剧了这个问题。
2. **shutdown 崩溃** — Ctrl+C 时，ROS2 的 signal handler 先调用了 `rclpy.shutdown()`，然后脚本的 `finally` 块又调了一次，导致 `RCLError: rcl_shutdown already called`。

**解决：改用 pyAgxArm CAN SDK 直连，不依赖 ROS2 节点。** 脚本已重写为 `scripts/move_to_init_pose.py`，通过 CAN 口直接控制机械臂：

```bash
conda activate vt
python3 ~/QuestArmTeleop/scripts/move_to_init_pose.py        # 默认 can0
python3 ~/QuestArmTeleop/scripts/move_to_init_pose.py can1    # 指定 CAN 口
```

脚本流程：连接 CAN → 使能机械臂 → `move_j` 到目标位姿 → 等待运动完成 → 打印最终关节角。

> **注意：** 运行前需确认 CAN 接口已激活（`ip link show can0` 显示 UP）。不需要启动任何 ROS2 节点。

**如果要用 ROS2 topic 方式**，前提是 `agx_arm_ctrl` 节点已在运行，然后：

```bash
source ~/QuestArmTeleop/install/setup.bash
ros2 topic pub /control/move_j sensor_msgs/msg/JointState \
  "{name: [joint1, joint2, joint3, joint4, joint5, joint6, joint7], position: [0.0, -0.5236, 0.0, 2.0944, 0.0, 0.0, 0.0]}" -1
```

### 9. joint7 在遥操启动时旋转 360° 撞限位

**现象：** 单独用 CAN SDK 脚本回零后，再启动 ROS2 遥操，joint7 会旋转近 360° 后才稳定。其它关节也有跳变但幅度较小。

**根因：** CAN SDK 脚本和 ROS2 遥操是两条独立控制路径，之间没有状态交接：

1. CAN SDK 脚本把机械臂移到 init pose（j2=-30°, j4=120°）
2. ROS2 启动后，`arm_ik_pose_node` 的 `init_data` 默认全零，IK warm-start 从 [0,0,0,0,0,0,0] 开始求解
3. 第一次 IK 求解时，目标位姿与当前 init_data 差距大，解算出的大角度跳变命令直接发给机械臂
4. joint7 是连续旋转关节（±90°范围内），对大角度跳变最敏感

**解决：将 move-to-init-pose 集成到 ROS2 launch 管线内。** 新增 `move_to_init_pose_node.py` 节点，插入 launch 流程中 agx_arm_ctrl 之后、arm_ik_pose_node 之前：

- 订阅 `/feedback/joint_states` 等待反馈 → 说明 `agx_arm_ctrl` 已就绪
- 发布 `/control/move_j` 把机械臂移到 init pose
- 订阅 `/feedback/arm_status` 等待 `motion_status == 0`（到达目标）
- 运动完成后 `raise SystemExit` 自行退出
- `arm_ik_pose_node` 启动后通过 `sync_state()` 读到正确的关节角，IK warm-start 无跳变

**修改的文件：**

| 文件 | 改动 |
|------|------|
| `src/oculus_reader/scripts/move_to_init_pose_node.py` | 新增 ROS2 节点 |
| `src/oculus_reader/CMakeLists.txt` | install(PROGRAMS) 添加该脚本 |
| `src/oculus_reader/launch/teleop_single_nero.launch.py` | 添加 init pose 节点为 step 2 |
| `src/oculus_reader/launch/teleop_double_nero.launch.py` | 添加左右臂 init pose 节点为 step 2 |

**独立 CAN SDK 版本**仍保留在 `scripts/move_to_init_pose.py`，用于不启动 ROS2 时的手动回零。

---

## ROS2 关节控制接口速查

`/control/move_j` 是机械臂的关节运动控制话题，消息类型 `sensor_msgs/JointState`。

| 话题 | 消息类型 | 说明 |
|------|----------|------|
| `/control/move_j` | `sensor_msgs/JointState` | 关节运动（有平滑插值） |
| `/control/move_js` | `sensor_msgs/JointState` | MIT 模式关节运动（无平滑） |
| `/control/joint_states` | `sensor_msgs/JointState` | 关节+末端执行器联合控制 |
| `/control/move_p` | `geometry_msgs/PoseStamped` | 点到点运动 |
| `/control/move_l` | `geometry_msgs/PoseStamped` | 直线运动 |
| `/control/move_c` | `geometry_msgs/PoseArray` | 圆弧运动 |

### 常用命令

```bash
# 回零位（service 方式）
ros2 service call /move_home std_srvs/srv/Empty

# 急停
ros2 service call /emergency_stop std_srvs/srv/Empty

# 使能/失能
ros2 service call /enable_agx_arm std_srvs/srv/SetBool "{data: true}"
ros2 service call /enable_agx_arm std_srvs/srv/SetBool "{data: false}"

# 查看关节反馈
ros2 topic echo /feedback/joint_states

# 查看 TCP 位姿
ros2 topic echo /feedback/tcp_pose

# 查看机械臂状态
ros2 topic echo /feedback/arm_status
```

---

## 待解决事项

- 在 vt conda 环境下完成完整的 ROS2 launch 启动，验证数据流通路（VR -> pub_pose -> pub_delta_pose -> arm_ik_pose_node -> agx_arm_ctrl -> 机械臂）
- 对齐手柄坐标系与机械臂末端坐标系（调整 launch 文件中 ros_to_arm_rpy 参数）
- 选择余量充足的关节完成微小运动烟雾测试
