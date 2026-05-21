## 正确启动流程

```bash
# 1. 确保 CAN 接口 UP
bash ~/QuestArmTeleop/src/agx_arm_ros/scripts/can_activate.sh 

# 2. 激活 vt conda 环境
conda deactivate
conda activate vt

# 回初始位姿
conda activate vt
python3 ~/QuestArmTeleop/scripts/move_to_init_pose.py        # 默认 can0

# 4. 启动遥操
source ~/QuestArmTeleop/install/setup.bash
ros2 launch oculus_reader teleop_single_nero.launch.py
```

---
