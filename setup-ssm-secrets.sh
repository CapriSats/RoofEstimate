#!/bin/bash
#
# Store secrets in AWS Systems Manager Parameter Store
# Run this script ONCE to set up your secrets in SSM
#

set -e

REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT=${ENVIRONMENT:-prod}

echo "🔐 Setting up secrets in AWS SSM Parameter Store"
echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo "Please create .env with your API keys first"
    exit 1
fi

# Load .env file
source .env

# Function to create SSM parameter
create_parameter() {
    local key=$1
    local value=$2
    local param_name="/roofestimate/$ENVIRONMENT/$key"

    if [ -z "$value" ]; then
        echo "⚠️  Skipping $key (not set in .env)"
        return
    fi

    echo "📝 Creating parameter: $param_name"

    # Check if parameter already exists
    if aws ssm get-parameter --name "$param_name" --region "$REGION" &>/dev/null; then
        echo "   Parameter exists. Updating..."
        aws ssm put-parameter \
            --name "$param_name" \
            --value "$value" \
            --type "SecureString" \
            --overwrite \
            --region "$REGION" \
            --description "RoofEstimate API key for $key" \
            > /dev/null
        echo "   ✅ Updated"
    else
        echo "   Creating new parameter..."
        aws ssm put-parameter \
            --name "$param_name" \
            --value "$value" \
            --type "SecureString" \
            --region "$REGION" \
            --description "RoofEstimate API key for $key" \
            --tags "Key=Application,Value=RoofEstimate" "Key=Environment,Value=$ENVIRONMENT" \
            > /dev/null
        echo "   ✅ Created"
    fi
}

# Create parameters for each secret
create_parameter "ANTHROPIC_API_KEY" "$ANTHROPIC_API_KEY"
create_parameter "GOOGLE_AI_API_KEY" "$GOOGLE_AI_API_KEY"
create_parameter "GOOGLE_VISION_API_KEY" "$GOOGLE_VISION_API_KEY"

echo ""
echo "✅ All secrets stored in SSM Parameter Store"
echo ""
echo "📋 To view your parameters:"
echo "   aws ssm describe-parameters --region $REGION --filters 'Key=tag:Application,Values=RoofEstimate'"
echo ""
echo "📋 To retrieve a secret:"
echo "   aws ssm get-parameter --name '/roofestimate/$ENVIRONMENT/ANTHROPIC_API_KEY' --with-decryption --region $REGION"
echo ""
echo "🔒 IAM Policy required for EC2 instance:"
echo ""
cat << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/roofestimate/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt"
      ],
      "Resource": "*"
    }
  ]
}
EOF
