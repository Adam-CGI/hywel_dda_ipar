#!/usr/bin/env python3
"""
Seed script to create initial admin user in Cosmos DB.

This script:
1. Creates the initial admin user with a secure random password
2. Writes credentials to .admin_credentials (gitignored)
3. Prints credentials to console once

Usage:
    python scripts/seed_admin_user.py
    
    # Or with custom username:
    python scripts/seed_admin_user.py --username myadmin
"""
import os
import sys
import secrets
import string
from datetime import datetime

# Add flask_app to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flask_app'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def generate_secure_password(length=16):
    """Generate a secure password meeting all requirements."""
    # Ensure at least one of each required character type
    password = [
        secrets.choice(string.ascii_uppercase),  # Uppercase
        secrets.choice(string.ascii_lowercase),  # Lowercase
        secrets.choice(string.digits),           # Number
    ]
    
    # Fill remaining with random chars
    alphabet = string.ascii_letters + string.digits
    password += [secrets.choice(alphabet) for _ in range(length - 3)]
    
    # Shuffle to randomize position of required chars
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Seed initial admin user')
    parser.add_argument('--username', default='admin', help='Admin username (default: admin)')
    parser.add_argument('--force', action='store_true', help='Overwrite existing admin user')
    args = parser.parse_args()
    
    # Import CosmosService after path setup
    from services.cosmos_service import CosmosService
    
    print("=" * 60)
    print("IPAR Document Intelligence - Admin User Seed Script")
    print("=" * 60)
    
    try:
        cosmos_service = CosmosService()
        print("✓ Connected to Cosmos DB")
    except Exception as e:
        print(f"✗ Failed to connect to Cosmos DB: {e}")
        sys.exit(1)
    
    username = args.username.lower().strip()
    
    # Check if user already exists
    existing_user = cosmos_service.get_user_by_username(username)
    if existing_user:
        if not args.force:
            print(f"\n⚠ User '{username}' already exists!")
            print(f"  - ID: {existing_user['id']}")
            print(f"  - Admin: {existing_user.get('is_admin', False)}")
            print(f"  - Active: {existing_user.get('is_active', True)}")
            print(f"\nUse --force to reset this user's password")
            sys.exit(0)
        else:
            print(f"\n⚠ Resetting password for existing user '{username}'...")
            password = generate_secure_password()
            cosmos_service.reset_password(
                user_id=existing_user['id'],
                new_password=password,
                reset_by='seed_script'
            )
            print(f"✓ Password reset for user '{username}'")
    else:
        # Create new admin user
        password = generate_secure_password()
        
        try:
            user = cosmos_service.create_user(
                username=username,
                password=password,
                is_admin=True,
                created_by='seed_script'
            )
            print(f"\n✓ Created admin user '{username}'")
            print(f"  - ID: {user['id']}")
            print(f"  - Admin: True")
            print(f"  - Active: True")
        except Exception as e:
            print(f"\n✗ Failed to create user: {e}")
            sys.exit(1)
    
    # Write credentials to file
    credentials_file = os.path.join(os.path.dirname(__file__), '..', '.admin_credentials')
    with open(credentials_file, 'w') as f:
        f.write(f"# IPAR Admin Credentials\n")
        f.write(f"# Generated: {datetime.utcnow().isoformat()}Z\n")
        f.write(f"# WARNING: Delete this file after noting the credentials!\n")
        f.write(f"\n")
        f.write(f"Username: {username}\n")
        f.write(f"Password: {password}\n")
    
    print(f"\n✓ Credentials written to: .admin_credentials")
    
    # Print credentials
    print("\n" + "=" * 60)
    print("INITIAL ADMIN CREDENTIALS")
    print("=" * 60)
    print(f"\n  Username: {username}")
    print(f"  Password: {password}")
    print("\n" + "=" * 60)
    print("⚠  IMPORTANT:")
    print("   - Save these credentials securely")
    print("   - Delete .admin_credentials after noting the password")
    print("   - Change this password after first login")
    print("=" * 60)


if __name__ == '__main__':
    main()
