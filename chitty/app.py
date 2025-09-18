import os
import logging
from datetime import timedelta
from flask import Flask, render_template, session
from flask_jwt_extended import JWTManager
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-this')
    app.config['JWT_SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-this')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # Tokens don't expire for this app
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    
    # Redis for session storage with better connection parameters
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.from_url(
        redis_url,
        socket_timeout=3,
        socket_connect_timeout=3,
        retry_on_timeout=True,
        health_check_interval=30
    )
    logger.info("Redis client initialized (will connect on first use)")
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # Register blueprints
    from routes.rooms import rooms_bp
    from routes.names import names_bp
    from routes.uploads import uploads_bp
    
    app.register_blueprint(rooms_bp)
    app.register_blueprint(names_bp)
    app.register_blueprint(uploads_bp)
    
    # Initialize Socket.IO
    from sockets import init_socketio
    socketio = init_socketio(app)
    
    # Main routes
    @app.route('/')
    def index():
        """Main chat interface"""
        return render_template('index.html')

    @app.route('/join/<room_id>')
    def join_room_direct(room_id):
        """Direct link to join a room - redirects to index with room parameter"""
        from flask import redirect, url_for
        return redirect(url_for('index', room=room_id))

    @app.route('/room/<room_id>')
    def room(room_id):
        """Room-specific chat interface"""
        return render_template('chat.html', room_id=room_id)
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        try:
            # Test database connection
            from models.db import db
            db.execute("SELECT 1")
            
            # Test Redis connection (non-blocking)
            try:
                # Use a shorter timeout for health check
                redis_client.ping()
                redis_status = 'connected'
            except Exception as redis_e:
                # Only log Redis warnings every 10th health check to reduce log spam
                if not hasattr(app, '_redis_warning_counter'):
                    app._redis_warning_counter = 0
                app._redis_warning_counter += 1
                
                if app._redis_warning_counter % 10 == 1:  # Log every 10th failure
                    logger.warning(f"Redis not connected (#{app._redis_warning_counter}): {redis_e}")
                
                redis_status = 'disconnected'
            
            return {
                'status': 'healthy', 
                'service': 'chitty-chat',
                'redis_status': redis_status
            }, 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e)}, 503
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return render_template('500.html'), 500
    
    return app, socketio

# Create app and socketio instance
app, socketio = create_app()

if __name__ == '__main__':
    import time
    # Background task for processing expired rooms
    def background_tasks():
        """Background tasks for room expiry processing"""
        while True:
            try:
                from services.archive import archive_service
                archive_service.process_expired_rooms()
            except Exception as e:
                logger.error(f"Background task error: {e}")
            time.sleep(60)  # Check every minute
    
    # Start background task in a separate thread
    import threading
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()
    
    # Run the application
    socketio.run(app, host='0.0.0.0', port=5055, debug=True)