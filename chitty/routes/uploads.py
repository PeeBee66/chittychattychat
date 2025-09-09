import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.storage import storage_service
from models.db import db
import logging
import mimetypes

logger = logging.getLogger(__name__)

uploads_bp = Blueprint('uploads', __name__, url_prefix='/api/v1/uploads')

# Allowed MIME types for uploads
ALLOWED_MIME_TYPES = {
    'image/jpeg',
    'image/png', 
    'image/webp',
    'image/gif'
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@uploads_bp.route('/init', methods=['POST'])
@jwt_required()
def init_upload():
    """Initialize file upload and get presigned URL"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        room_id = jwt_data.get('room_id')
        participant_id = jwt_data.get('participant_id')
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400
        
        filename = data.get('filename')
        file_size = data.get('file_size')
        mime_type = data.get('mime_type')
        
        if not all([filename, file_size, mime_type]):
            return jsonify({'error': 'filename, file_size, and mime_type are required'}), 400
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE} bytes'}), 413
        
        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_MIME_TYPES)}'}), 415
        
        # Guess file extension if not provided
        file_ext = mimetypes.guess_extension(mime_type) or ''
        if not filename.lower().endswith(file_ext.lower()) and file_ext:
            filename += file_ext
        
        # Generate unique attachment ID and object key
        attachment_id = str(uuid.uuid4())
        object_key = f"{room_id}/{attachment_id}_{filename}"
        
        # Create attachment record (not available yet)
        query = """
        INSERT INTO attachments (room_id, object_key, mime_type, size_bytes, available)
        VALUES (%s, %s, %s, %s, FALSE)
        RETURNING id
        """
        result = db.execute_one(query, (room_id, object_key, mime_type, file_size))
        if not result:
            return jsonify({'error': 'Failed to initialize upload'}), 500
        
        attachment_db_id = result['id']
        
        # Generate presigned PUT URL
        upload_url = storage_service.generate_presigned_put_url(object_key)
        
        return jsonify({
            'attachment_id': attachment_db_id,
            'upload_url': upload_url,
            'object_key': object_key
        }), 200
        
    except Exception as e:
        logger.error(f"Error initializing upload: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/complete', methods=['POST'])
@jwt_required()
def complete_upload():
    """Mark upload as complete and available"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        room_id = jwt_data.get('room_id')
        
        data = request.get_json()
        if not data or 'attachment_id' not in data:
            return jsonify({'error': 'attachment_id is required'}), 400
        
        attachment_id = data['attachment_id']
        
        # Get attachment record
        query = """
        SELECT id, object_key, available 
        FROM attachments 
        WHERE id = %s AND room_id = %s
        """
        attachment = db.execute_one(query, (attachment_id, room_id))
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        if attachment['available']:
            return jsonify({'error': 'Upload already completed'}), 409
        
        # Verify object exists in MinIO
        if not storage_service.check_object_exists(attachment['object_key']):
            return jsonify({'error': 'File upload not found'}), 404
        
        # Mark as available
        query = """
        UPDATE attachments 
        SET available = TRUE
        WHERE id = %s
        RETURNING id
        """
        result = db.execute_one(query, (attachment_id,))
        if not result:
            return jsonify({'error': 'Failed to complete upload'}), 500
        
        return jsonify({'success': True, 'attachment_id': attachment_id}), 200
        
    except Exception as e:
        logger.error(f"Error completing upload: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/<int:attachment_id>/url', methods=['GET'])
@jwt_required()
def get_attachment_url(attachment_id):
    """Get presigned URL for downloading attachment"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        room_id = jwt_data.get('room_id')
        
        # Get attachment record
        query = """
        SELECT object_key, available, mime_type
        FROM attachments 
        WHERE id = %s AND room_id = %s AND available = TRUE
        """
        attachment = db.execute_one(query, (attachment_id, room_id))
        if not attachment:
            return jsonify({'error': 'Attachment not found or not available'}), 404
        
        # Generate presigned GET URL
        download_url = storage_service.generate_presigned_get_url(attachment['object_key'])
        
        return jsonify({
            'download_url': download_url,
            'mime_type': attachment['mime_type']
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting attachment URL: {e}")
        return jsonify({'error': 'Internal server error'}), 500