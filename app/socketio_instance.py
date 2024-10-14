from flask_socketio import SocketIO

# Initialize the SocketIO instance (without passing the app yet)
socketio = SocketIO()

def init_socketio(app):
    """
    Call this function to bind the SocketIO instance to the Flask app.
    """
    socketio.init_app(app)
