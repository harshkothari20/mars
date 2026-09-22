import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import xacro

def generate_launch_description():
    robotXacroName = 'differential_drive_robot'
    namePackage = 'mars'
    
    declareSpawnX = DeclareLaunchArgument('spawn_x', default_value='3.0')
    declareSpawnY = DeclareLaunchArgument('spawn_y', default_value='-3.0')
    declareSpawnYaw = DeclareLaunchArgument('spawn_yaw', default_value='3.14159')
    spawnX = LaunchConfiguration('spawn_x')
    spawnY = LaunchConfiguration('spawn_y')
    spawnYaw = LaunchConfiguration('spawn_yaw')

    # Gazebo (gz-sim) rewrites package://mars/... URIs from the URDF into
    # model://mars/... and resolves them by searching GZ_SIM_RESOURCE_PATH.
    # Without this, mesh files (e.g. the SO-101 arm STLs) fail to load.
    packageShareDir = get_package_share_directory(namePackage)
    gzResourcePathParent = os.path.dirname(packageShareDir)  # .../install/mars/share
    setGzResourcePath = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=gzResourcePathParent + os.pathsep + os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    )

    # Matches description/
    modelFileRelativePath = 'description/robot.xacro'
    pathModelFile = os.path.join(get_package_share_directory(namePackage), modelFileRelativePath)
    robotDescription = xacro.process_file(pathModelFile).toxml()

    # Matches worlds/
    worldFileRelativePath = 'worlds/obstacles.world'
    pathWorldFile = os.path.join(get_package_share_directory(namePackage), worldFileRelativePath)

    gazebo_rosPackageLaunch = PythonLaunchDescriptionSource(
        os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
    )

    gazeboLaunch = IncludeLaunchDescription(
        gazebo_rosPackageLaunch,
        launch_arguments={'gz_args': [f'-r -v -v4 {pathWorldFile}'], 'on_exit_shutdown': 'true'}.items()
    )

    spawnModelNodeGazebo = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', robotXacroName, '-topic', 'robot_description',
            '-x', spawnX, '-y', spawnY, '-z', '0.1', '-Y', spawnYaw,
        ],
        output='screen',
    )

    nodeRobotStatePublisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robotDescription, 'use_sim_time': True}]
    )

    # Matches config/
    bridge_params = os.path.join(
        get_package_share_directory(namePackage),
        'config',
        'bridge_parameters.yaml'
    )

    start_gazebo_ros_bridge_cmd = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['--ros-args', '-p', f'config_file:={bridge_params}'],
        output='screen',
    )

    launchDescriptionObject = LaunchDescription()
    launchDescriptionObject.add_action(declareSpawnX)
    launchDescriptionObject.add_action(declareSpawnY)
    launchDescriptionObject.add_action(declareSpawnYaw)
    launchDescriptionObject.add_action(setGzResourcePath)
    launchDescriptionObject.add_action(gazeboLaunch)
    launchDescriptionObject.add_action(spawnModelNodeGazebo)
    launchDescriptionObject.add_action(nodeRobotStatePublisher)
    launchDescriptionObject.add_action(start_gazebo_ros_bridge_cmd)

    return launchDescriptionObject
