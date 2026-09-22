import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    namePackage = 'mars'
    bringupDir = get_package_share_directory('nav2_bringup')

    # Change ONLY these two defaults if you ever rename the map or params file -
    # nothing else in the package references the map path.
    defaultMapPath = os.path.join(get_package_share_directory(namePackage), 'maps', 'mars_warehouse.yaml')
    defaultParamsPath = os.path.join(get_package_share_directory(namePackage), 'config', 'nav2_params.yaml')

    mapYaml = LaunchConfiguration('map')
    paramsFile = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')

    declareMap = DeclareLaunchArgument(
        'map', default_value=defaultMapPath,
        description='Full path to the saved warehouse map .yaml'
    )
    declareParams = DeclareLaunchArgument(
        'params_file', default_value=defaultParamsPath,
        description='Full path to the Nav2 params .yaml'
    )
    declareUseSimTime = DeclareLaunchArgument('use_sim_time', default_value='true')
    declareAutostart = DeclareLaunchArgument('autostart', default_value='true')

    # Re-uses your existing gazebo_model.launch.py untouched:
    # spawns the robot, robot_state_publisher, gz<->ros bridge
    gazeboModelLaunch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(namePackage), 'launch', 'gazebo_model.launch.py')
        )
    )

    # nav2_bringup's own bringup_launch.py: map_server, amcl, planner_server,
    # controller_server, bt_navigator, behavior_server, smoother_server,
    # velocity_smoother, waypoint_follower - all under one lifecycle manager.
    nav2BringupLaunch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringupDir, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'map': mapYaml,
            'params_file': paramsFile,
            'use_sim_time': use_sim_time,
            'autostart': autostart,
        }.items(),
    )

    ld = LaunchDescription()
    ld.add_action(declareMap)
    ld.add_action(declareParams)
    ld.add_action(declareUseSimTime)
    ld.add_action(declareAutostart)
    ld.add_action(gazeboModelLaunch)
    ld.add_action(nav2BringupLaunch)

    # Nav2's own pre-built RViz config: Map, LaserScan, both costmaps,
    # and the 2D Pose Estimate / Nav2 Goal tools already added.
    bringupDir_rviz = get_package_share_directory('nav2_bringup')
    rvizNode = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(bringupDir_rviz, 'rviz', 'nav2_default_view.rviz')],
        parameters=[{'use_sim_time': use_sim_time}],
    )
    ld.add_action(rvizNode)
    return ld
