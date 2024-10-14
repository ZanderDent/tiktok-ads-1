from app import create_app
from app.socketio_instance import socketio, init_socketio

app = create_app()
init_socketio(app)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
