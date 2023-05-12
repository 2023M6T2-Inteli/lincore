import rclpy

from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf_transformations import euler_from_quaternion
from turtlesim.msg import Pose as TPose
import math
from collections import deque

import requests

MAX_DIFF = 0.1

class Pose(TPose):

    def __init__(self, x=0.0, y=0.0, theta=0.0):
        super().__init__(x=x, y=y, theta=theta)
        
    def __repr__(self):

        return f"(x={self.x:.2f}, y={self.y:.2f}, theta={self.theta:.2f})"
    
    def __add__(self, other):

        self.x += other.x
        self.y += other.y
        return self
    
    def __sub__(self, other):
        self.x -= other.x
        self.y -= other.y
        return self
    
    def __eq__(self, other):
        return abs(self.x - other.x) <= MAX_DIFF and abs(self.y - other.y) <= MAX_DIFF
    
class Rotation(TPose):

    def __init__(self, theta=0.0):
        super().__init__(x=0.0, y=0.0, theta=theta)
        self.rotated = False
        
    def __repr__(self):
        return f"(theta={self.theta:.2f})"
    
    def __eq__(self, other):
        return abs(self.theta - other.theta) <= 0.05

class MissionControl(deque):

    shapes = {
        "square": [
            Pose(1.0, 1.0), Pose(1.0, -1.0), Pose(-1.0, -1.0), Pose(-1.0, 1.0), Pose(1.0, 1.0)
        ],
        "g": [
            Pose(-1.0, 1.0), Pose(-2.0, 0.0), Pose(-1.0, -1.0), Pose(0.0, -0.3), Pose(-0.5, -0.45)
        ],
        None: [Pose(0.0, 0.0)]
    }
    
    def __init__(self, shape=None):
        """
        No construtor do controle de missão é preciso definir o arquivo
        csv de pontos a serem lidos. A partir daí, o construtor inicia o deque
        e faz a leitura do arquivo csv, adicionando cada ponto na fila.
        """
        super().__init__()
        
    def enqueue(self, x):
        """Método para adicionar novos pontos ao fim da fila."""
        super().append(x)
    
    def dequeue(self):
        """Método para retirar pontos do começo da fila."""
        return super().popleft()
    
    def load_shape(self, shape):
        super().clear()
        for pose in MissionControl.shapes[shape]:
            self.enqueue(pose)

    
class BotController(Node):
    def __init__(self, control_period=0.05, mission_control=MissionControl()):
        super().__init__("bot_controller")

        self.initiated = False
        self.setpoint = Pose()
        self.pose = Pose()
        self.theta= Rotation()
        self.setpoint_rotation = Rotation()
        self.setpoint_translation = 0.0
        self.current_rotation = Rotation()
        self.queue = mission_control

        self.origin = Pose()
        self.shape_selected = False
        
        self.control_timer = self.create_timer(
            timer_period_sec=control_period, 
            callback=self.control_callback
        )
        self.subscription = self.create_subscription(
            msg_type=Odometry,
            topic="odom",
            callback=self.pose_callback,
            qos_profile=10
        )
        self.publisher = self.create_publisher(
            msg_type=Twist, 
            topic="cmd_vel", 
            qos_profile=10
        )

    def control_callback(self): 
        if not self.initiated:
            self.get_logger().info("Aguardando pose...")
            return
        
        msg = Twist()

        if not self.setpoint_rotation.rotated:
            if self.current_rotation == self.setpoint_rotation:
                msg.angular.z = 0.0
                self.get_logger().info(f"Donatello rodou o suficiente")
                self.setpoint_rotation.rotated = True
                print(f"final_rotation: {self.current_rotation}")
            else:
                offset = self.setpoint_rotation.theta - self.current_rotation.theta
                if abs(offset) > 0.05:
                    msg.angular.z = 0.5 if offset > 0 else -0.5
        else:
            if self.pose == self.setpoint:
                msg.linear.x = 0.0
                self.get_logger().info(f"Donatello chegou ao destino")
                self.publisher.publish(msg)
                self.update_setpoint()
            else:
                offset = self.setpoint_rotation.theta - self.current_rotation.theta
                if abs(offset) > 0.05:
                    msg.angular.z = 0.5 if offset < 0 else -0.5
                else:
                    msg.angular.z = 0.0
                self.relative_vector = Pose(x=self.setpoint.x - self.pose.x, y=self.setpoint.y - self.pose.y)
                self.relative_translation = math.sqrt(self.relative_vector.x**2 + self.relative_vector.y**2)
                print(f"pose: {self.pose}, setpoint: {self.setpoint}, desired{self.desired}, current{self.current}")
    
                if abs(self.desired - self.current) > 0.1:
                    msg.linear.x = 0.5 if self.desired - self.current else -0.5
                else:
                    msg.linear.x = 0.0
                    self.get_logger().info(f"Donatello chegou ao destino")
                    self.publisher.publish(msg)
                    self.update_setpoint()

        
        self.publisher.publish(msg)

    def update_setpoint(self):
        try:
            print(self.queue)
            self.setpoint = self.queue.dequeue()
            self.get_logger().info(f"Donatello chegou em {self.pose}, \
                                   andando para {self.setpoint}")
            self.origin = self.pose
            if self.setpoint == Pose(0.0,0.0):
                self.theta = Rotation(theta=0.0) 
            else:
                self.theta= Rotation(theta=math.atan2(self.setpoint.y - self.pose.y, self.setpoint.x - self.pose.x))
                print(f"theta: {self.theta}")

            self.relative_vector = Pose(x=self.setpoint.x - self.pose.x, y=self.setpoint.y - self.pose.y)
            self.relative_translation = math.sqrt(self.relative_vector.x**2 + self.relative_vector.y**2)

            self.desired = math.sqrt(self.relative_vector.x**2 + self.relative_vector.y**2)

            if self.relative_vector.x >= 0 and self.relative_vector.y >=0:
                self.setpoint_rotation = Rotation(theta=abs(self.theta.theta))

            elif self.relative_vector.x >=0 and self.relative_vector.y <= 0:
                self.setpoint_rotation = Rotation(theta=-abs(self.theta.theta))

            elif self.relative_vector.x <=0 and self.relative_vector.y <= 0:
                self.setpoint_rotation = Rotation(theta=-abs(self.theta.theta))
                print(f"setpoint_rotation: {self.setpoint_rotation}")
            else:
                self.setpoint_rotation = Rotation(theta=abs(self.theta.theta))
        except IndexError:
            self.get_logger().info(f"Fim da jornada!")
            self.shape_selected = False

    def pose_callback(self, msg):
        if self.shape_selected:
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y
            z = msg.pose.pose.position.z
            ang = msg.pose.pose.orientation
            _, _, theta = euler_from_quaternion([ang.x, ang.y, ang.z, ang.w])
            self.pose = Pose(x=x, y=y, theta=theta)
            self.current_rotation = Rotation(theta=self.pose.theta)

            self.current = math.sqrt((self.pose.x - self.origin.x)**2 + (self.pose.y - self.origin.y)**2)

            if not self.initiated:
                self.initiated = True
                print(f"pose inicial: {self.pose}")
                self.update_setpoint()
                self.get_logger().info(f"Setpoint: {self.setpoint}")
        else:
            response = requests.get('http://127.0.0.1:8000')
            print(response.json()['shape'])
            self.shape_selected = True
            self.queue.load_shape(response.json()['shape'])
            


def main(args=None):
    rclpy.init(args=args)
    mc = MissionControl()
    tc = BotController(mission_control=mc)
    rclpy.spin(tc)
    tc.destroy_node()

if __name__ == "__main__":
    main()