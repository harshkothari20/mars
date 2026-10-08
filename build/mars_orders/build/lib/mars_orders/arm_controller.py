#!/usr/bin/env python3
"""Hardcoded pick-and-place arm controller for MARS (sim).

Steps the arm through config/pick_sequence.yaml for whichever product the
pick request names, and fakes the grasp by teleporting the matching
item_box_<product_id> Gazebo model into the rover's basket via
`gz service .../set_pose` at the "swing_to_basket" step - there's no real
grasp physics or IK here, by design (see decisions-and-approach.md).
"""
import json
import math
import os
import subprocess
import threading
import time

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import Float64, String

JOINTS = [
    "arm_shoulder_pan", "arm_shoulder_lift", "arm_elbow_flex",
    "arm_wrist_flex", "arm_wrist_roll", "arm_gripper",
]

PICK_REQUEST_TOPIC = "/arm/pick_request"
ARM_STATUS_TOPIC = "/arm/status"


class ArmController(Node):
    def __init__(self):
        super().__init__("arm_controller")
        share = get_package_share_directory("mars_orders")
        self.declare_parameter("locations_file", os.path.join(share, "config", "locations.yaml"))
        self.declare_parameter("sequence_file", os.path.join(share, "config", "pick_sequence.yaml"))
        self.declare_parameter("world_name", "mars_warehouse")

        with open(self.get_parameter("locations_file").value) as f:
            locations = yaml.safe_load(f)
        with open(self.get_parameter("sequence_file").value) as f:
            self.sequence = yaml.safe_load(f)

        self.aisles = locations["aisles"]
        self.basket_offset = locations.get("basket_offset", {"x": 0.0, "y": -0.13, "z": 0.34})
        self.world = self.get_parameter("world_name").value

        self.joint_pubs = {
            name: self.create_publisher(Float64, f"/arm/joint/{name}/cmd_pos", 10)
            for name in JOINTS
        }
        self.status_pub = self.create_publisher(String, ARM_STATUS_TOPIC, 10)
        self.create_subscription(String, PICK_REQUEST_TOPIC, self.on_request, 10)

        self.get_logger().info("Arm controller ready (hardcoded sequence, no IK)")

    def on_request(self, msg):
        try:
            req = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f"Bad pick request: {msg.data!r}")
            return
        threading.Thread(target=self.run_pick, args=(req,), daemon=True).start()

    def publish_joints(self, joints):
        for name, value in joints.items():
            pub = self.joint_pubs.get(name)
            if pub is not None:
                pub.publish(Float64(data=float(value)))

    def basket_world_pose(self, product_id):
        loc = self.aisles.get(product_id)
        if loc is None:
            return None
        yaw = float(loc["yaw"])
        ox, oy = self.basket_offset["x"], self.basket_offset["y"]
        wx = loc["x"] + ox * math.cos(yaw) - oy * math.sin(yaw)
        wy = loc["y"] + ox * math.sin(yaw) + oy * math.cos(yaw)
        return wx, wy, self.basket_offset["z"]

    def set_box_pose(self, product_id, x, y, z):
        model = f"item_box_{product_id}"
        req = f'name: "{model}", position: {{x: {x}, y: {y}, z: {z}}}, orientation: {{x:0,y:0,z:0,w:1}}'
        try:
            subprocess.run(
                ["gz", "service", "-s", f"/world/{self.world}/set_pose",
                 "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                 "--timeout", "2000", "--req", req],
                check=True, capture_output=True, timeout=3.0,
            )
        except Exception as e:
            self.get_logger().warn(f"set_pose failed for {model}: {e}")

    def run_pick(self, req):
        order_id = req.get("order_id")
        product_id = req.get("product_id")
        log = self.get_logger()

        basket = self.basket_world_pose(product_id)
        if basket is None:
            self.publish_status(order_id, product_id, "FAILED", f"no aisle configured for {product_id}")
            return

        log.info(f"Picking {req.get('product')} for {order_id}")
        for step in self.sequence["steps"]:
            self.publish_joints(step["joints"])
            if step.get("box_pose") == "basket":
                self.set_box_pose(product_id, *basket)
            time.sleep(float(step.get("dwell_s", 1.0)))

        self.publish_status(order_id, product_id, "DONE", "")
        log.info(f"{product_id} placed in basket")

    def publish_status(self, order_id, product_id, state, message):
        self.status_pub.publish(String(data=json.dumps({
            "order_id": order_id, "product_id": product_id,
            "state": state, "message": message,
        })))


def main():
    rclpy.init()
    node = ArmController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()