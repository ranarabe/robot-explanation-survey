"""Convert ROS messages to engine objects. (No rclpy import needed.)"""

from .objects import Element, make_element_id


def element_id(detected_object) -> str:
    """Unique name used in facts, e.g. 'cube_red_1'."""
    return make_element_id(detected_object.shape, detected_object.color, detected_object.id)


def element_from_detection(detected_object) -> Element:
    """cube_stacking_interfaces/DetectedObject -> Element."""
    return Element(
        element_id=element_id(detected_object),
        shape=detected_object.shape,
        color=detected_object.color or 'unknown',
        width=float(detected_object.dimensions.x),
        depth=float(detected_object.dimensions.y),
        height=float(detected_object.dimensions.z),
        detection_id=int(detected_object.id),
    )
