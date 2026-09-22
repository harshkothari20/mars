#!/usr/bin/env python3
"""MARS order manager.

  Website order (MongoDB, status PENDING)
    -> Nav2 drives to the item's aisle stop pose and stops
    -> aisle QR is scanned to confirm the item
    -> arm is asked to pick   (/arm/pick_request), waits for DONE (/arm/status)
    -> inventory is updated, rover moves to the next item
    -> after the last item, rover drives to the drop location
    -> order is marked COMPLETED
"""
import json
import math
import os
import threading
import time

import rclpy
import yaml
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String

from mars_orders.order_store import OrderStore
from mars_orders.qr_utils import decode_qr, image_to_bgr

PICK_REQUEST_TOPIC = "/arm/pick_request"   # rover -> arm
ARM_STATUS_TOPIC = "/arm/status"           # arm -> rover


class OrderManager(Node):
    def __init__(self):
        super().__init__("order_manager")

        share = get_package_share_directory("mars_orders")
        self.declare_parameter("mongo_uri", "mongodb://localhost:27017")
        self.declare_parameter("db_name", "shopping_cart")
        self.declare_parameter("locations_file", os.path.join(share, "config", "locations.yaml"))
        self.declare_parameter("camera_topic", "/camera/image_raw")
        self.declare_parameter("verify_qr", True)
        self.declare_parameter("nav_timeout_s", 180.0)
        self.declare_parameter("qr_timeout_s", 10.0)
        self.declare_parameter("arm_timeout_s", 90.0)
        self.declare_parameter("poll_period_s", 2.0)

        self.verify_qr_enabled = self.get_parameter("verify_qr").value
        self.nav_timeout = self.get_parameter("nav_timeout_s").value
        self.qr_timeout = self.get_parameter("qr_timeout_s").value
        self.arm_timeout = self.get_parameter("arm_timeout_s").value
        self.poll_period = self.get_parameter("poll_period_s").value

        with open(self.get_parameter("locations_file").value) as f:
            self.locations = yaml.safe_load(f)
        self.frame_id = self.locations.get("frame_id", "map")

        self.store = OrderStore(
            self.get_parameter("mongo_uri").value,
            self.get_parameter("db_name").value,
        )

        # Nav2
        self.nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")

        # Arm handoff
        self.pick_pub = self.create_publisher(String, PICK_REQUEST_TOPIC, 10)
        self.create_subscription(String, ARM_STATUS_TOPIC, self.on_arm_status, 10)
        self._active = None            # {"order_id", "product_id"} while waiting on the arm
        self._arm_state = None
        self._arm_msg = ""
        self._arm_event = threading.Event()

        # Camera (only stored here, decoded on demand while scanning)
        self._last_image = None
        self._last_image_time = 0.0
        self.create_subscription(
            Image, self.get_parameter("camera_topic").value, self.on_image, qos_profile_sensor_data
        )

        threading.Thread(target=self.mission_loop, daemon=True).start()

    # ------------------------------------------------------------------ callbacks

    def on_image(self, msg):
        self._last_image = msg
        self._last_image_time = time.monotonic()

    def on_arm_status(self, msg):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f"Ignoring non-JSON arm status: {msg.data!r}")
            return
        active = self._active
        if not active:
            return
        if data.get("order_id") != active["order_id"] or data.get("product_id") != active["product_id"]:
            return
        state = str(data.get("state", "")).upper()
        if state in ("DONE", "FAILED"):
            self._arm_state = state
            self._arm_msg = data.get("message", "")
            self._arm_event.set()

    # ------------------------------------------------------------------ helpers

    def _wait_future(self, future, timeout):
        end = time.monotonic() + timeout
        while rclpy.ok() and not future.done():
            if time.monotonic() > end:
                return False
            time.sleep(0.05)
        return future.done()

    def make_pose(self, p):
        msg = PoseStamped()
        msg.header.frame_id = self.frame_id
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.position.x = float(p["x"])
        msg.pose.position.y = float(p["y"])
        yaw = float(p["yaw"])
        msg.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.orientation.w = math.cos(yaw / 2.0)
        return msg

    def navigate(self, label, pose):
        log = self.get_logger()
        log.info(f"Navigating to {label}")
        goal = NavigateToPose.Goal()
        goal.pose = self.make_pose(pose)

        send = self.nav_client.send_goal_async(goal)
        if not self._wait_future(send, 15.0):
            log.error("Nav2 did not respond to the goal")
            return False
        handle = send.result()
        if not handle.accepted:
            log.error(f"Nav2 rejected the goal to {label}")
            return False

        result = handle.get_result_async()
        if not self._wait_future(result, self.nav_timeout):
            log.error(f"Navigation to {label} timed out")
            handle.cancel_goal_async()
            return False
        if result.result().status != GoalStatus.STATUS_SUCCEEDED:
            log.error(f"Navigation to {label} failed (status {result.result().status})")
            return False

        log.info(f"Arrived at {label}")
        return True

    def verify_qr(self, expected):
        """Scan the aisle QR. True only if it matches the expected product QR."""
        log = self.get_logger()
        if not self.verify_qr_enabled:
            log.warn("verify_qr is off, skipping QR check")
            return True

        start = time.monotonic()
        deadline = start + self.qr_timeout
        last_checked = 0.0
        seen = None
        warned = False

        while rclpy.ok() and time.monotonic() < deadline:
            msg, stamp = self._last_image, self._last_image_time
            if msg is not None and stamp >= start and stamp > last_checked:
                last_checked = stamp
                frame = image_to_bgr(msg)
                if frame is None:
                    if not warned:
                        log.warn(f"Unsupported image encoding: {msg.encoding}")
                        warned = True
                else:
                    text = decode_qr(frame)
                    if text:
                        seen = text
                        if text == expected:
                            log.info(f"QR confirmed: {text}")
                            return True
            time.sleep(0.1)

        if seen:
            log.error(f"Wrong QR: expected {expected}, saw {seen}")
        else:
            log.error(f"No QR read within {self.qr_timeout:.0f}s (expected {expected})")
        return False

    def pick(self, order, item, aisle):
        """Ask the arm to pick. Returns (ok, message)."""
        deadline = time.monotonic() + 10.0
        while self.pick_pub.get_subscription_count() == 0:
            if time.monotonic() > deadline or not rclpy.ok():
                return False, f"no arm node is listening on {PICK_REQUEST_TOPIC}"
            time.sleep(0.2)

        self._arm_event.clear()
        self._arm_state = None
        self._active = {"order_id": order["orderId"], "product_id": item.product_id}

        payload = {
            "order_id": order["orderId"],
            "product_id": item.product_id,
            "product": item.product,
            "quantity": item.quantity,
            "aisle": aisle,
        }
        self.pick_pub.publish(String(data=json.dumps(payload)))
        self.get_logger().info(f"Pick requested: {item.quantity} x {item.product}")

        got = self._arm_event.wait(self.arm_timeout)
        self._active = None
        if not got:
            return False, "arm timed out"
        return self._arm_state == "DONE", (self._arm_msg or self._arm_state)

    # ------------------------------------------------------------------ mission

    def abort(self, order, reason):
        self.get_logger().error(f"{order['orderId']} FAILED: {reason}")
        self.store.fail_order(order, reason)
        self.navigate("home", self.locations["home"])   # do not sit in an aisle

    def run_order(self, order):
        log = self.get_logger()
        oid = order["orderId"]

        if not order.get("cart"):
            log.warn(f"{oid} has an empty cart, completing it")
            self.store.complete_order(order)
            return

        items, unknown = self.store.remaining_items(order)
        if unknown:
            return self.abort(order, f"no QR record for: {', '.join(unknown)}")

        log.info(f"Starting {oid}: " + ", ".join(f"{i.quantity} x {i.product}" for i in items))

        for item in items:
            loc = self.locations["aisles"].get(item.product_id)
            if loc is None:
                return self.abort(order, f"no aisle configured for {item.product}")
            if not self.store.has_stock(item.product_id, item.quantity):
                return self.abort(order, f"not enough stock for {item.product}")

            if not self.navigate(f"aisle {loc['aisle']} ({item.product})", loc):
                return self.abort(order, f"could not reach aisle {loc['aisle']}")

            if not self.verify_qr(item.qr_id):
                return self.abort(order, f"QR check failed for {item.product}")

            ok, msg = self.pick(order, item, loc["aisle"])
            if not ok:
                return self.abort(order, f"arm failed on {item.product}: {msg}")

            if not self.store.confirm_pick(order, item):
                return self.abort(order, f"stock too low when confirming {item.product}")
            log.info(f"{item.product} picked, inventory updated")

        if not self.navigate("drop location", self.locations["drop"]):
            return self.abort(order, "could not reach the drop location")

        self.store.complete_order(order)
        log.info(f"{oid} COMPLETED")

    def mission_loop(self):
        log = self.get_logger()

        while rclpy.ok() and not self.nav_client.wait_for_server(timeout_sec=2.0):
            log.info("Waiting for Nav2 (navigate_to_pose)...")

        try:
            n = self.store.requeue_in_progress()
            if n:
                log.warn(f"Re-queued {n} order(s) left IN_PROGRESS by a previous run")
        except Exception as e:
            log.error(f"MongoDB error on startup: {e}")

        log.info("Ready, waiting for orders")
        while rclpy.ok():
            try:
                order = self.store.claim_next_order()
            except Exception as e:
                log.error(f"MongoDB error: {e}")
                time.sleep(self.poll_period)
                continue

            if order is None:
                time.sleep(self.poll_period)
                continue

            try:
                self.run_order(order)
            except Exception as e:
                log.error(f"Unexpected error on {order.get('orderId')}: {e}")
                try:
                    self.store.fail_order(order, f"exception: {e}")
                except Exception:
                    pass


def main():
    rclpy.init()
    node = OrderManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
