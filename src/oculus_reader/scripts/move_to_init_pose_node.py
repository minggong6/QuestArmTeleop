#!/usr/bin/env python3
import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from agx_arm_msgs.msg import AgxArmStatus


INIT_JOINTS_RAD = [
    0.0,                     # joint1
    math.radians(-30.0),     # joint2
    0.0,                     # joint3
    math.radians(120.0),     # joint4
    0.0,                     # joint5
    0.0,                     # joint6
    0.0,                     # joint7
]

JOINT_NAMES = [f"joint{i}" for i in range(1, 8)]

REACH_TARGET = 0


class MoveToInitPoseNode(Node):
    def __init__(self):
        super().__init__("move_to_init_pose_node")

        self.declare_parameter("init_joints_rad", INIT_JOINTS_RAD)
        self.declare_parameter("move_j_topic", "/control/move_j")
        self.declare_parameter("feedback_joint_topic", "/feedback/joint_states")
        self.declare_parameter("feedback_arm_status_topic", "/feedback/arm_status")
        self.declare_parameter("motion_done_timeout", 10.0)

        init_joints = list(self.get_parameter("init_joints_rad").value)
        move_j_topic = self.get_parameter("move_j_topic").value
        feedback_joint_topic = self.get_parameter("feedback_joint_topic").value
        feedback_status_topic = self.get_parameter("feedback_arm_status_topic").value
        self._timeout = float(self.get_parameter("motion_done_timeout").value)

        self._pub = self.create_publisher(JointState, move_j_topic, 1)
        self._feedback_received = False
        self._motion_done = False

        self.create_subscription(
            JointState, feedback_joint_topic, self._feedback_callback, 1
        )
        self.create_subscription(
            AgxArmStatus, feedback_status_topic, self._status_callback, 1
        )

        self._timer = self.create_timer(0.5, self._try_publish)
        self._motion_start = None
        self._published = False

        self.get_logger().info(
            f"Waiting for feedback on {feedback_joint_topic} ... "
            f"Target (deg): j2=-30, j4=120, rest=0"
        )

    def _feedback_callback(self, msg: JointState):
        if not self._feedback_received:
            self._feedback_received = True
            self.get_logger().info(
                f"Feedback received. Current joints: "
                f"{[round(p, 4) for p in msg.position[:7]]}"
            )

    def _status_callback(self, msg: AgxArmStatus):
        if self._published and not self._motion_done:
            if msg.motion_status == REACH_TARGET:
                self._motion_done = True
                self.get_logger().info("Arrived at init pose. Node will shut down.")
                self._timer.cancel()
                self._shutdown_timer = self.create_timer(0.5, self._do_shutdown)

    def _try_publish(self):
        if not self._feedback_received:
            return
        if self._published:
            if self._motion_start is not None:
                import time
                elapsed = time.monotonic() - self._motion_start
                if elapsed > self._timeout:
                    self.get_logger().warn(
                        f"Motion timeout ({self._timeout}s). Shutting down."
                    )
                    self._shutdown_timer = self.create_timer(0.5, self._do_shutdown)
            return

        msg = JointState()
        msg.name = JOINT_NAMES
        msg.position = list(self.get_parameter("init_joints_rad").value)
        self._pub.publish(msg)
        self._published = True

        import time
        self._motion_start = time.monotonic()
        self.get_logger().info(f"Published move_j → {[round(v, 4) for v in msg.position]}")

    def _do_shutdown(self):
        raise SystemExit


def main(args=None):
    rclpy.init(args=args)
    node = MoveToInitPoseNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
