import tornado.ioloop
import tornado.web
import tornado.websocket
import zmq
import zmq.asyncio
import asyncio

# Create an asyncio-compatible ZeroMQ context.
zmq_context = zmq.asyncio.Context()

class ZMQSubscriber:
    def __init__(self, context, address="tcp://localhost:5555"):
        self.socket = context.socket(zmq.SUB)
        self.socket.connect(address)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
    
    async def recv(self):
        msg = await self.socket.recv()
        return msg.decode('utf-8')  # JSON string

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
    subscriber = ZMQSubscriber(zmq_context)
    while True:
        try:
            msg = await subscriber.recv()
            #print("Received from ZeroMQ:", msg)
            for client in clients:
                try:
                    client.write_message(msg)
                except Exception as e:
                    print("Error sending message:", e)
        except Exception as e:
            print("Error receiving from ZeroMQ:", e)
        await asyncio.sleep(0.001)

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
