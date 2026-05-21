#!/usr/bin/env python3
"""Move Nero arm to init pose via CAN SDK (no ROS2 required).

Usage:
    conda activate vt
    python3 scripts/move_to_init_pose.py [can_port]

Default can_port: can0
"""
import math
import sys
import time

from pyAgxArm import AgxArmFactory, ArmModel, create_agx_arm_config

# Init pose: j2=-30deg, j4=120deg, rest=0
INIT_JOINTS_RAD = [
    0.0,                     # joint1
    math.radians(-30.0),     # joint2
    0.0,                     # joint3
    math.radians(120.0),     # joint4
    0.0,                     # joint5
    0.0,                     # joint6
    0.0,                     # joint7
]


def wait_motion_done(robot, timeout=10.0, poll_interval=0.1):
    """Wait until motion_status == 0 (arrived) or timeout."""
    time.sleep(0.5)
    start = time.monotonic()
    while True:
        status = robot.get_arm_status()
        if status is not None and getattr(status.msg, "motion_status", None) == 0:
            return True
        if time.monotonic() - start > timeout:
            return False
        time.sleep(poll_interval)


def main():
    can_port = sys.argv[1] if len(sys.argv) > 1 else "can0"

    print(f"CAN port: {can_port}")
    print(f"Target (deg): j2=-30, j4=120, rest=0")
    print(f"Target (rad): {[round(v, 4) for v in INIT_JOINTS_RAD]}")

    cfg = create_agx_arm_config(
        robot=ArmModel.NERO,
        interface="socketcan",
        channel=can_port,
    )
    arm = AgxArmFactory.create_arm(cfg)
    arm.connect()

    print("Enabling arm ...")
    while not arm.enable():
        time.sleep(0.05)
    print("Arm enabled.")

    cur = arm.get_joint_angles()
    if cur is not None:
        print(f"Current (rad): {[round(v, 4) for v in cur.msg]}")

    print("Moving to init pose ...")
    arm.move_j(INIT_JOINTS_RAD)

    if wait_motion_done(arm, timeout=10.0):
        print("Arrived at init pose.")
    else:
        print("WARNING: motion timeout, arm may not have reached target.")

    final = arm.get_joint_angles()
    if final is not None:
        print(f"Final   (rad): {[round(v, 4) for v in final.msg]}")
        print(f"Final   (deg): {[round(math.degrees(v), 1) for v in final.msg]}")


if __name__ == "__main__":
    main()
