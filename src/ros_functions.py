"""
ROS Functions Module for LISA

This module provides ROS 2 navigation integration via UDP communication bridge.
It handles goal pose publishing, navigation status tracking, and waypoint management.

Communication Protocol:
- Sends navigation goals to ROS bridge via UDP (port 5005)
- Receives goal status updates via UDP (port 5006)
- Uses JSON format for data exchange

Key Functionalities:
- Send navigation goals with pose coordinates
- Track goal execution status asynchronously
- Manage predefined waypoint locations
- Register callbacks for status updates
- Wait for goal completion with timeout

Predefined Waypoints:
- station: Supervisor/command post location
- storage_area: Equipment and PPE storage
- work_area: Main work location

The ROS 2 bridge node (running separately) must:
1. Listen on UDP port 5005 for goal poses
2. Publish to ROS 2 /goal_pose topic
3. Monitor action server status
4. Send status updates to UDP port 5006

Status Codes (ActionStatus from ROS 2):
- 1: ACCEPTED
- 2: EXECUTING
- 3: CANCELING
- 4: SUCCEEDED
- 5: CANCELED
- 6: ABORTED

Author: [Your team/organization]
Version: 2.0
"""

import socket
import json
import threading
import time
import uuid
from typing import Callable, Optional, Dict

# Global status tracking
goal_statuses = {}
status_callbacks = {}
_status_listener_thread = None
_status_listener_running = False

def send_goal_to_ros_bridge(x, y, z, qx, qy, qz, qw, frame_id='map', host='127.0.0.1', port=5005, goal_id=None):
    """
    Sends a goal pose to the ROS bridge node via UDP.
    
    Args:
        x, y, z: Position coordinates
        qx, qy, qz, qw: Orientation quaternion
        frame_id: Reference frame (default: 'map')
        host, port: UDP destination
        goal_id: Optional goal ID for tracking (if None, will be auto-generated)
    """
    if goal_id is None:
        goal_id = str(uuid.uuid4())
    
    goal = {
        'x': x,
        'y': y,
        'z': z,
        'qx': qx,
        'qy': qy,
        'qz': qz,
        'qw': qw,
        'frame_id': frame_id,
        'goal_id': goal_id
    }
    data = json.dumps(goal).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data, (host, port))
    sock.close()
    print(f"Sent goal to ROS bridge: {goal}")
    return goal_id

def start_status_listener(host='127.0.0.1', port=5006):
    """
    Start listening for goal status updates from the ROS bridge.
    Returns the listener thread. Only starts one listener thread.
    """
    global _status_listener_thread, _status_listener_running
    
    # If listener is already running, return the existing thread
    if _status_listener_running and _status_listener_thread and _status_listener_thread.is_alive():
        return _status_listener_thread
    
    def listen_for_status():
        global _status_listener_running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((host, port))
            print(f"Listening for goal status updates on {host}:{port}")
            
            while _status_listener_running:
                try:
                    sock.settimeout(1.0)  # 1 second timeout
                    data, addr = sock.recvfrom(1024)
                    status_update = json.loads(data.decode())
                    
                    goal_id = status_update['goal_id']
                    status = status_update['status']
                    status_name = status_update['status_name']
                    timestamp = status_update['timestamp']
                    
                    # Check if this is a response to a goal we sent
                    original_goal_id = status_update.get('original_goal_id')
                    tracking_id = original_goal_id if original_goal_id else goal_id
                    
                    # Store the status
                    goal_statuses[tracking_id] = {
                        'status': status,
                        'status_name': status_name,
                        'timestamp': timestamp,
                        'ros_goal_id': goal_id
                    }
                    
                    # Call registered callback if exists
                    if tracking_id in status_callbacks:
                        callback = status_callbacks[tracking_id]
                        try:
                            callback(tracking_id, status, status_name)
                        except Exception as e:
                            print(f"Error in status callback: {e}")
                        
                        # Remove callback for terminal states
                        if status in [4, 5, 6]:  # SUCCEEDED, CANCELED, ABORTED
                            del status_callbacks[tracking_id]
                            
                except socket.timeout:
                    # Timeout is expected, continue listening
                    continue
                except Exception as e:
                    print(f"Error receiving status update: {e}")
                    break
        except Exception as e:
            print(f"Error in status listener: {e}")
        finally:
            _status_listener_running = False
            try:
                sock.close()
            except:
                pass
    
    _status_listener_running = True
    _status_listener_thread = threading.Thread(target=listen_for_status, daemon=True)
    _status_listener_thread.start()
    return _status_listener_thread

def register_status_callback(goal_id: str, callback: Callable[[str, int, str], None]):
    """
    Register a callback function to be called when a specific goal's status changes.
    
    Args:
        goal_id: The goal ID to monitor
        callback: Function to call with (goal_id, status_code, status_name)
    """
    status_callbacks[goal_id] = callback

def get_goal_status(goal_id: str) -> Optional[Dict]:
    """
    Get the current status of a goal.
    
    Args:
        goal_id: The goal ID to check
        
    Returns:
        Dictionary with status info or None if goal not found
    """
    return goal_statuses.get(goal_id)

def wait_for_goal_completion(goal_id: str, timeout: float = 60.0) -> Optional[str]:
    """
    Wait for a goal to reach a terminal state (SUCCEEDED, CANCELED, ABORTED).
    
    Args:
        goal_id: The goal ID to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        Final status name or None if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status_info = goal_statuses.get(goal_id)
        if status_info:
            status = status_info['status']
            if status in [4, 5, 6]:  # Terminal states
                return status_info['status_name']
        time.sleep(0.1)
    
    return None

def navigate_to(location):
    """
    Navigate to a named waypoint: 'station', 'storage_area', or 'work_area'.
    
    Args:
        location (str): Name of the waypoint destination
        
    Returns:
        str: The goal_id for tracking navigation status
        
    Raises:
        ValueError: If location is not in predefined waypoints
        
    Example:
        goal_id = navigate_to('station')
        result = wait_for_goal_completion(goal_id, timeout=60.0)
    """
    # Predefined waypoints in map frame (x, y, z in meters, quaternion orientation)
    # IMPORTANT: Customize these coordinates for your specific environment
    # Use RViz "2D Pose Estimate" tool to determine coordinates in your map
    waypoints = {
        'station': {  # Supervisor/command post location
            'x': 2.9531030654907227,
            'y': 1.536637783050537,
            'z': 0.0,
            'qx': 0.0,
            'qy': 0.0,
            'qz': -0.6948597872588839,
            'qw': 0.7191452398858931
        },
        'storage_area': {  # Equipment and PPE storage location
            'x': 2.359142780303955,
            'y': -1.53078031539917,
            'z': 0.0,
            'qx': 0.0,
            'qy': 0.0,
            'qz': -0.002724688788894625,
            'qw': 0.9999962880286125
        },
        'work_area': {  # Main work location for inspections
            'x': 12.169673919677734,
            'y': -7.085422039031982,
            'z': 0.0,
            'qx': 0.0,
            'qy': 0.0,
            'qz': 0.750336611499113,
            'qw': 0.6610559503128529
        }
    }
    if location not in waypoints:
        raise ValueError(f"Unknown location: {location}. Choose from {list(waypoints.keys())}")
    wp = waypoints[location]
    goal_id = send_goal_to_ros_bridge(
        wp['x'], wp['y'], wp['z'],
        wp['qx'], wp['qy'], wp['qz'], wp['qw']
    )
    return goal_id

def navigate_to_with_feedback(location, callback=None):
    """
    Navigate to a named waypoint with optional status feedback.
    
    Args:
        location: Waypoint name ('station', 'storage_area', 'work_area')
        callback: Optional callback function for status updates
        
    Returns:
        goal_id: The ID of the sent goal for tracking
    """
    # Send the goal and get the goal_id
    goal_id = navigate_to(location)
    
    if callback:
        # Register callback for this specific goal
        register_status_callback(goal_id, callback)
    
    return goal_id

# Example usage function
# def main():
#     rclpy.init()
#     node = GoalPosePublisher()
#     pose = ... # Fill in geometry_msgs.msg.Pose
#     node.publish_goal_pose(pose)
#     rclpy.shutdown()

# Example usage with status feedback:
# def status_callback(goal_id, status, status_name):
#     print(f"Goal {goal_id} status: {status_name}")
#     if status in [4, 5, 6]:  # Terminal states
#         print(f"Navigation completed with status: {status_name}")
# 
# # Start the status listener
# start_status_listener()
# 
# # Method 1: Send goal and track with callback
# goal_id = navigate_to_with_feedback('station', status_callback)
# 
# # Method 2: Send goal and wait for completion
# goal_id = navigate_to('station')
# result = wait_for_goal_completion(goal_id, timeout=60.0)
# print(f"Navigation result: {result}")
# 
# # Method 3: Check current status
# status_info = get_goal_status(goal_id)
# if status_info:
#     print(f"Current status: {status_info['status_name']}")
