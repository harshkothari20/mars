#!/usr/bin/env python3
"""Stand-in for the real arm node, for testing before the arm exists.

Listens on /arm/pick_request, waits pick_duration_s, then publishes DONE on /arm/status.
"""
import json
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class MockArm(Node):
    def __init__(self):
        super().__init__("mock_arm")
        self.declare_parameter("pick_duration_s", 3.0)
        self.duration = self.get_parameter("pick_duration_s").value
        self.pub = self.create_publisher(String, "/arm/status", 10)
        self.create_subscription(String, "/arm/pick_request", self.on_request, 10)
        self.get_logger().info("Mock arm ready")

    def on_request(self, msg):
        try:
            req = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f"Bad pick request: {msg.data!r}")
            return
        self.get_logger().info(
            f"[mock] picking {req.get('quantity')} x {req.get('product')} ({self.duration:.1f}s)"
        )
        threading.Timer(self.duration, self.finish, args=(req,)).start()

    def finish(self, req):
        status = {
            "order_id": req.get("order_id"),
            "product_id": req.get("product_id"),
            "state": "DONE",
            "message": "",
        }
        self.pub.publish(String(data=json.dumps(status)))
        self.get_logger().info(f"[mock] DONE {req.get('product')}")


def main():
    rclpy.init()
    node = MockArm()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
