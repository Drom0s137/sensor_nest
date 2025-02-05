import tornado.ioloop
import tornado.web
import tornado.websocket
import zmq
import zmq.asyncio
import asyncio
import json

# Create ZeroMQ subscribers
zmq_context = zmq.asyncio.Context()

class ZMQSubscriber:
    def __init__(self, address):
        self.socket = zmq_context.socket(zmq.SUB)
        self.socket.connect(address)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

# WebSocket Clients
clients = []

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("ZeroMQ-WebSocket Bridge is running.")

class DetectionWebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket client connected.")
        clients.append(self)

    def on_close(self):
        print("WebSocket client disconnected.")
        if self in clients:
            clients.remove(self)

    def check_origin(self, origin):
        return True

async def zmq_bridge_loop():
    detection_subscriber = ZMQSubscriber("tcp://localhost:5555")  # Detection system
    lidar_subscriber = ZMQSubscriber("tcp://localhost:5556")  # LiDAR system

    poller = zmq.asyncio.Poller()
    poller.register(detection_subscriber.socket, zmq.POLLIN)
    poller.register(lidar_subscriber.socket, zmq.POLLIN)

    # Initialize empty data structures so either stream can start independently
    detection_data = {"detections": [], "image": None}
    lidar_data = {"points": [], "scan_frequency": 0, "timestamp": 0}

    while True:
        try:
            # Poll for new messages (timeout prevents blocking)
            events = await poller.poll(timeout=100)  # 100ms timeout

            for socket, event in events:
                if socket == detection_subscriber.socket and event == zmq.POLLIN:
                    detection_msg = await detection_subscriber.socket.recv()
                    detection_data = json.loads(detection_msg.decode('utf-8'))  # Update detection data
                    #print("Received Detection Data")

                if socket == lidar_subscriber.socket and event == zmq.POLLIN:
                    lidar_msg = await lidar_subscriber.socket.recv()
                    lidar_data = json.loads(lidar_msg.decode('utf-8'))  # Update LiDAR data
                    #print("Received LiDAR Data")

            # Always send the latest available data, even if one stream hasn't started
            combined_msg = {
                "detection": detection_data,
                "lidar": lidar_data
            }

            for client in clients:
                try:
                    client.write_message(json.dumps(combined_msg))
                except Exception as e:
                    print("Error sending WebSocket message:", e)

        except Exception as e:
            print("Error in bridge loop:", e)

        await asyncio.sleep(0.01)  # Prevent high CPU usage

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/ws", DetectionWebSocket),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8080)
    print("WebSocket server started on port 8080.")
    asyncio.ensure_future(zmq_bridge_loop())
    tornado.ioloop.IOLoop.current().start()
