import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    namePackage = 'mars'

    use_sim_time = LaunchConfiguration('use_sim_time')

    declareUseSimTime = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use the Gazebo /clock as ROS time'
    )

    # Re-uses your existing gazebo_model.launch.py untouched:
    # spawns the robot, starts robot_state_publisher, starts the gz<->ros bridge
    gazeboModelLaunch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(namePackage), 'launch', 'gazebo_model.launch.py')
        )
    )

    slamParamsFile = os.path.join(
        get_package_share_directory(namePackage), 'config', 'mapper_params_online_async.yaml'
    )

    slamToolboxNode = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slamParamsFile, {'use_sim_time': use_sim_time}],
    )

    # slam_toolbox is a lifecycle node - it stays "unconfigured" (no params
    # loaded, not subscribed to /scan) until something calls configure+activate.
    # This node does that automatically on startup.
    lifecycleManagerNode = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_slam',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': True},
            {'node_names': ['slam_toolbox']},
        ],
    )

    rvizNode = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    ld = LaunchDescription()
    ld.add_action(declareUseSimTime)
    ld.add_action(gazeboModelLaunch)
    ld.add_action(slamToolboxNode)
    ld.add_action(lifecycleManagerNode)
    ld.add_action(rvizNode)
    return ld
