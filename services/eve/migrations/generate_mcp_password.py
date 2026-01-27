"""
Utility script to generate a secure random password for the PostgreSQL MCP role
"""
import secrets
import string
import sys
from pathlib import Path

def generate_password(length: int = 32) -> str:
    """
    Generate a cryptographically secure random password.
    
    Args:
        length: Length of password (default: 32)
    
    Returns:
        Secure random password string
    """
    # Use letters, digits, and safe special characters
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def main():
    """Generate password and optionally save to .env file"""
    password = generate_password(32)
    
    print("Generated secure password for PostgreSQL MCP role:")
    print("=" * 60)
    print(password)
    print("=" * 60)
    print("\nTo use this password:")
    print("1. Set environment variable:")
    print(f"   export POSTGRES_MCP_PASSWORD='{password}'")
    print("\n2. Or add to .env file:")
    print(f"   POSTGRES_MCP_PASSWORD={password}")
    
    # Optionally save to .env file
    env_file = Path(__file__).parent.parent / ".env"
    if "--save" in sys.argv or "-s" in sys.argv:
        if env_file.exists():
            # Read existing .env
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Check if POSTGRES_MCP_PASSWORD already exists
            if "POSTGRES_MCP_PASSWORD" in content:
                # Update existing value
                lines = content.split('\n')
                updated_lines = []
                for line in lines:
                    if line.startswith("POSTGRES_MCP_PASSWORD"):
                        updated_lines.append(f"POSTGRES_MCP_PASSWORD={password}")
                    else:
                        updated_lines.append(line)
                content = '\n'.join(updated_lines)
            else:
                # Append new line
                content += f"\nPOSTGRES_MCP_PASSWORD={password}\n"
            
            with open(env_file, 'w') as f:
                f.write(content)
            print(f"\n✅ Saved to {env_file}")
        else:
            # Create new .env file
            with open(env_file, 'w') as f:
                f.write(f"POSTGRES_MCP_PASSWORD={password}\n")
            print(f"\n✅ Created {env_file} with password")
    else:
        print("\n💡 Tip: Use --save or -s flag to automatically save to .env file")
    
    # Also output just the password for easy copying
    print(f"\nPassword (for easy copy):")
    print(password)


if __name__ == "__main__":
    main()
