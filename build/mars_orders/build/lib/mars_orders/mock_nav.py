#!/usr/bin/env python3
"""Stand-in for Nav2's navigate_to_pose action, for testing before the rover exists.

Accepts every goal, waits travel_time_s, then reports success.
"""
import time

import rclpy
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer
from rclpy.node import Node


class MockNav(Node):
    def __init__(self):
        super().__init__("mock_nav")
        self.declare_parameter("travel_time_s", 2.0)
        self.travel = self.get_parameter("travel_time_s").value
        self._server = ActionServer(self, NavigateToPose, "navigate_to_pose", self.execute)
        self.get_logger().info("Mock Nav2 ready")

    def execute(self, goal_handle):
        p = goal_handle.request.pose.pose.position
        self.get_logger().info(f"[mock] driving to ({p.x:.2f}, {p.y:.2f})")
        time.sleep(self.travel)
        goal_handle.succeed()
        return NavigateToPose.Result()


def main():
    rclpy.init()
    node = MockNav()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
