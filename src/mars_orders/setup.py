from glob import glob

from setuptools import find_packages, setup

package_name = "mars_orders"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Harsh",
    maintainer_email="todo@example.com",
    description="Connects website orders to Nav2, QR confirmation and the arm",
    license="MIT",
    entry_points={
        "console_scripts": [
            "order_manager = mars_orders.order_manager:main",
            "mock_arm = mars_orders.mock_arm:main",
            "mock_nav = mars_orders.mock_nav:main",
        ],
    },
)
