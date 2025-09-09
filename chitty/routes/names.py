from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
from services.names import name_service
import logging

logger = logging.getLogger(__name__)

names_bp = Blueprint('names', __name__, url_prefix='/api/v1/names')

@names_bp.route('/suggest', methods=['GET'])
@jwt_required(optional=True)
def suggest_names():
    """Get 4 deterministic names for selection based on participant"""
    try:
        # Try to get participant info from JWT
        jwt_data = get_jwt() if request.headers.get('Authorization') else None
        
        if jwt_data and jwt_data.get('participant_id') and jwt_data.get('room_id'):
            # Use deterministic names based on participant + room
            seed = f"{jwt_data['room_id']}_{jwt_data['participant_id']}"
            names = name_service.get_deterministic_names(seed, 4)
            logger.info(f"Generated deterministic names for participant {jwt_data['participant_id']} in room {jwt_data['room_id']}")
        else:
            # Fallback to random names if no JWT
            names = name_service.get_random_names(4)
            logger.info("Generated random names (no JWT provided)")
        
        return jsonify({'names': names}), 200
    except Exception as e:
        logger.error(f"Error getting suggested names: {e}")
        return jsonify({'error': 'Internal server error'}), 500