"""
Admin routes for user management.
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps

from services.cosmos_service import CosmosService, validate_password

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Initialize service at module level (singleton pattern)
cosmos_service = CosmosService()


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        if not session.get('is_admin'):
            return render_template('error.html',
                error="Access Denied",
                message="You do not have permission to access this page."), 403
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/users')
@admin_required
def list_users():
    """Display user management page."""
    users = cosmos_service.list_users()
    return render_template('admin_users.html', users=users)


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    """Create a new user."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    is_admin = request.form.get('is_admin') == 'on'
    
    # Validation
    if not username:
        return render_template('admin_users.html',
            users=cosmos_service.list_users(),
            error="Username is required"), 400
    
    if len(username) < 3:
        return render_template('admin_users.html',
            users=cosmos_service.list_users(),
            error="Username must be at least 3 characters"), 400
    
    # Validate password
    is_valid, error = validate_password(password)
    if not is_valid:
        return render_template('admin_users.html',
            users=cosmos_service.list_users(),
            error=error), 400
    
    try:
        cosmos_service.create_user(
            username=username,
            password=password,
            is_admin=is_admin,
            created_by=session.get('username')
        )
        logger.info(f"Admin '{session.get('username')}' created user '{username}'")
        return redirect(url_for('admin.list_users'))
        
    except ValueError as e:
        return render_template('admin_users.html',
            users=cosmos_service.list_users(),
            error=str(e)), 400
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        return render_template('admin_users.html',
            users=cosmos_service.list_users(),
            error="Failed to create user. Please try again."), 500


@admin_bp.route('/users/<user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    """Toggle user active status."""
    user = cosmos_service.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Prevent self-deactivation
    if user_id == session.get('user_id'):
        return jsonify({"error": "Cannot deactivate your own account"}), 400
    
    new_status = not user.get('is_active', True)
    
    if new_status:
        cosmos_service.activate_user(user_id, activated_by=session.get('username'))
    else:
        cosmos_service.deactivate_user(user_id, deactivated_by=session.get('username'))
    
    logger.info(f"Admin '{session.get('username')}' {'activated' if new_status else 'deactivated'} user '{user['username']}'")
    
    # Return updated user list for HTMX
    users = cosmos_service.list_users()
    return render_template('admin_users.html', users=users, success=f"User {'activated' if new_status else 'deactivated'} successfully")


@admin_bp.route('/users/<user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_user_admin(user_id):
    """Toggle user admin status."""
    user = cosmos_service.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Prevent removing own admin status
    if user_id == session.get('user_id'):
        return jsonify({"error": "Cannot modify your own admin status"}), 400
    
    new_status = not user.get('is_admin', False)
    cosmos_service.update_user(user_id, {'is_admin': new_status}, updated_by=session.get('username'))
    
    logger.info(f"Admin '{session.get('username')}' {'granted' if new_status else 'revoked'} admin for user '{user['username']}'")
    
    # Return updated user list for HTMX
    users = cosmos_service.list_users()
    return render_template('admin_users.html', users=users, success=f"Admin status {'granted' if new_status else 'revoked'} successfully")


@admin_bp.route('/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    """Reset user password."""
    new_password = request.form.get('new_password', '')
    
    # Validate password
    is_valid, error = validate_password(new_password)
    if not is_valid:
        users = cosmos_service.list_users()
        return render_template('admin_users.html', users=users, error=error), 400
    
    try:
        success = cosmos_service.reset_password(
            user_id=user_id,
            new_password=new_password,
            reset_by=session.get('username')
        )
        
        if success:
            logger.info(f"Admin '{session.get('username')}' reset password for user_id '{user_id}'")
            users = cosmos_service.list_users()
            return render_template('admin_users.html', users=users, success="Password reset successfully")
        else:
            users = cosmos_service.list_users()
            return render_template('admin_users.html', users=users, error="User not found"), 404
            
    except ValueError as e:
        users = cosmos_service.list_users()
        return render_template('admin_users.html', users=users, error=str(e)), 400
    except Exception as e:
        logger.error(f"Failed to reset password: {e}")
        users = cosmos_service.list_users()
        return render_template('admin_users.html', users=users, error="Failed to reset password"), 500
