# MARS: website orders to ROS2

## Flow

```
Website "Place Order" -> MongoDB (PENDING)
  -> order_manager claims the oldest order (IN_PROGRESS)
  -> Nav2 drives to the item's aisle stop pose
  -> aisle QR scanned, must match the item
  -> /arm/pick_request -> arm picks -> /arm/status DONE
  -> inventory deducted, PICKED transaction logged
  -> next item ... last item ...
  -> Nav2 to drop location -> order COMPLETED
```

Any failure (Nav2, wrong or missing QR, arm FAILED or timeout, low stock) marks the order `FAILED` with a `failure_reason` and sends the rover home.

## Folders

| Folder | What it is |
|---|---|
| `mars_website/` | Your shop (Node + MongoDB). Only 3 products: Apple, Banana, Grapes |
| `mars_orders/` | ROS2 Jazzy package (`ament_python`) |
| `mars_world/` | Gazebo world from the previous step |

## Run: full loop without the rover or arm (mock Nav2 + mock arm)

1. Start MongoDB, then load the products and QR records once:
   ```
   cd mars_website
   python3 db/setup_products.py
   python3 db/setup_qr.py
   ```
2. Start the website:
   ```
   npm install
   node server.js
   ```
   Open http://localhost:3000 and place an order.
3. Build the package:
   ```
   cd <your_ws>/src && cp -r /path/to/mars_orders .
   cd .. && colcon build --packages-select mars_orders
   source install/setup.bash
   pip install pymongo   # if python3-pymongo is not installed
   ```
4. Launch (no camera, so the QR check is off):
   ```
   ros2 launch mars_orders orders.launch.py use_sim_time:=false mock_nav:=true mock_arm:=true verify_qr:=false
   ```
5. Watch the order go PENDING, IN_PROGRESS, COMPLETED in MongoDB, and the stock drop in `products`.

## Run: with the real setup (later)

```
ros2 launch mars_orders orders.launch.py camera_topic:=/camera/image_raw
```

Needs Nav2 running with a map of `mars_warehouse.sdf` and the initial pose set, a camera publishing `rgb8`, `bgr8` or `mono8` images, and the arm node below.

## Arm interface (draft, share with the arm teammate)

| Topic | Type | Direction | Payload (JSON in `data`) |
|---|---|---|---|
| `/arm/pick_request` | `std_msgs/String` | rover to arm | `{"order_id","product_id","product","quantity","aisle"}` |
| `/arm/status` | `std_msgs/String` | arm to rover | `{"order_id","product_id","state":"DONE"\|"FAILED","message"}` |

The arm must echo `order_id` and `product_id` from the request. Inventory is only updated after `DONE`.

## Locations

`config/locations.yaml` holds the aisle stop poses, `home` and `drop`. Keep it in sync with `mars_warehouse.sdf`.

| Product | Aisle | Pose (x, y, yaw) |
|---|---|---|
| APPLE001 | 1 | (-2.2, 2.5, 3.14159) |
| BANANA001 | 2 | (-2.2, 0.0, 3.14159) |
| GRAPES001 | 3 | (-2.2, -2.5, 3.14159) |
| home / drop | | (3.0, -3.0, 3.14159) |

## Changes made to your website files

| File | Change |
|---|---|
| `index.html` | Removed Orange, Watermelon, Mango (no aisle for them yet); fixed the stray `>` in the title |
| `script.js` | Blocks an empty cart; shows an error if the server fails; clears the cart after a successful order |
| `server.js`, `package.json`, `style.css`, `db/*.py` | Unchanged |

`scan_order_qr.py` is no longer needed: QR scanning moved into `order_manager`, and stock is now deducted after the arm reports DONE instead of at scan time.

## Tests

```
cd mars_orders && python3 -m pytest test
```
