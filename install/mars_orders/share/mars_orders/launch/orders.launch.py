from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    use_sim_time = ParameterValue(LaunchConfiguration("use_sim_time"), value_type=bool)
    verify_qr = ParameterValue(LaunchConfiguration("verify_qr"), value_type=bool)
    camera_topic = ParameterValue(LaunchConfiguration("camera_topic"), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("camera_topic", default_value="/camera/image_raw"),
        DeclareLaunchArgument("verify_qr", default_value="true",
                              description="Check the aisle QR before asking the arm to pick"),
        DeclareLaunchArgument("mock_nav", default_value="false",
                              description="Start a fake navigate_to_pose server (no Nav2 needed)"),
        DeclareLaunchArgument("mock_arm", default_value="false",
                              description="Start a fake arm that answers DONE after a few seconds"),

        Node(package="mars_orders", executable="order_manager", output="screen",
             parameters=[{"use_sim_time": use_sim_time,
                          "camera_topic": camera_topic,
                          "verify_qr": verify_qr}]),
        Node(package="mars_orders", executable="mock_nav", output="screen",
             condition=IfCondition(LaunchConfiguration("mock_nav")),
             parameters=[{"use_sim_time": use_sim_time}]),
        Node(package="mars_orders", executable="mock_arm", output="screen",
             condition=IfCondition(LaunchConfiguration("mock_arm")),
             parameters=[{"use_sim_time": use_sim_time}]),
    ])
