"""
Secrets management for RoofEstimate.

In local development: uses .env file
In AWS EC2: uses AWS Systems Manager Parameter Store (SSM)

Environment variable AWS_REGION must be set when using SSM.
"""

import os
from typing import Optional


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a secret value from SSM Parameter Store or .env file.

    Priority:
    1. Environment variable (already loaded from .env in development)
    2. AWS SSM Parameter Store (if running on EC2)
    3. Default value

    SSM Parameter naming convention:
    /roofestimate/prod/{KEY_NAME}

    Example:
        get_secret("ANTHROPIC_API_KEY")
        -> checks env var first
        -> then checks SSM: /roofestimate/prod/ANTHROPIC_API_KEY
    """
    # First check if already in environment (from .env or system env)
    value = os.getenv(key)
    if value:
        return value

    # Try AWS SSM if we're in AWS environment
    if _is_aws_environment():
        try:
            value = _get_from_ssm(key)
            if value:
                # Cache it in environment for subsequent calls
                os.environ[key] = value
                return value
        except Exception as e:
            print(f"Warning: Failed to get {key} from SSM: {e}")

    return default


def _is_aws_environment() -> bool:
    """Check if we're running in an AWS environment."""
    # Check for AWS_REGION or EC2 instance metadata
    if os.getenv("AWS_REGION"):
        return True

    # Check if running on EC2 by trying to access instance metadata
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/instance-id",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        )
        urllib.request.urlopen(req, timeout=1)
        return True
    except:
        return False


def _get_from_ssm(key: str) -> Optional[str]:
    """Get secret from AWS Systems Manager Parameter Store."""
    try:
        import boto3

        region = os.getenv("AWS_REGION", "us-east-1")
        ssm = boto3.client("ssm", region_name=region)

        # Parameter naming: /roofestimate/prod/{KEY_NAME}
        parameter_name = f"/roofestimate/prod/{key}"

        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )

        return response["Parameter"]["Value"]

    except ImportError:
        print("Warning: boto3 not installed. Cannot access SSM. Install with: pip install boto3")
        return None
    except Exception as e:
        # Parameter not found or other error
        return None


# Convenience functions for commonly used secrets
def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key."""
    return get_secret("ANTHROPIC_API_KEY")


def get_google_ai_key() -> Optional[str]:
    """Get Google AI API key (for Gemini)."""
    return get_secret("GOOGLE_AI_API_KEY")


def get_google_vision_key() -> Optional[str]:
    """Get Google Vision API key."""
    return get_secret("GOOGLE_VISION_API_KEY")


if __name__ == "__main__":
    # Test script
    print("Testing secrets management...")
    print(f"AWS Environment: {_is_aws_environment()}")
    print(f"ANTHROPIC_API_KEY: {'✓ Found' if get_anthropic_key() else '✗ Not found'}")
    print(f"GOOGLE_AI_API_KEY: {'✓ Found' if get_google_ai_key() else '✗ Not found'}")
    print(f"GOOGLE_VISION_API_KEY: {'✓ Found' if get_google_vision_key() else '✗ Not found'}")
