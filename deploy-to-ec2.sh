#!/bin/bash
#
# Deploy RoofEstimate to EC2
#
set -e

INSTANCE_IP="$1"
KEY_FILE="${2:-roofestimate-key.pem}"

if [ -z "$INSTANCE_IP" ]; then
    echo "Usage: $0 <instance-ip> [key-file]"
    exit 1
fi

echo "🚀 Deploying RoofEstimate to $INSTANCE_IP"
echo ""

# Wait for SSH to be ready
echo "⏳ Waiting for SSH to be ready..."
max_attempts=30
attempt=0
while ! ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@$INSTANCE_IP "echo 'SSH ready'" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ SSH connection timed out"
        exit 1
    fi
    echo "  Attempt $attempt/$max_attempts..."
    sleep 10
done

echo "✅ SSH connection established"
echo ""

# Create deployment script to run on EC2
cat > /tmp/ec2-setup.sh << 'DEPLOY_SCRIPT'
#!/bin/bash
set -e

echo "📦 Updating system packages..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

echo "📦 Installing dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip \
    git curl wget build-essential unzip

echo "📦 Installing AWS CLI..."
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf awscliv2.zip aws
else
    echo "AWS CLI already installed"
fi

echo "📦 Installing Node.js 22..."
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs

echo "✅ Python version: $(python3 --version)"
echo "✅ Node.js version: $(node --version)"
echo "✅ npm version: $(npm --version)"
echo "✅ AWS CLI version: $(aws --version)"

echo "📂 Cloning repository..."
if [ -d "/home/ubuntu/RoofEstimate" ]; then
    echo "  Repository already exists, pulling latest..."
    cd /home/ubuntu/RoofEstimate
    git pull
else
    cd /home/ubuntu
    git clone https://github.com/CapriSats/RoofEstimate.git
    cd RoofEstimate
fi

echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "📦 Installing UI dependencies..."
cd ui
npm install
cd ..

echo "✅ Dependencies installed"
DEPLOY_SCRIPT

# Copy setup script to EC2
echo "📤 Copying deployment script to EC2..."
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no /tmp/ec2-setup.sh ubuntu@$INSTANCE_IP:/tmp/

echo "🔧 Running deployment script on EC2..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "chmod +x /tmp/ec2-setup.sh && /tmp/ec2-setup.sh"

echo ""
echo "🔑 Configuring AWS credentials..."
echo "⚠️  Note: This step requires AWS credentials to be configured manually on the EC2 instance"
echo "    or provided via environment variables AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"

if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP bash << CREDENTIALS
mkdir -p ~/.aws

cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF

cat > ~/.aws/config << 'EOF'
[default]
region = us-east-1
output = json
EOF

chmod 600 ~/.aws/credentials
chmod 600 ~/.aws/config

echo "Testing AWS connection..."
aws sts get-caller-identity
CREDENTIALS
else
    echo "⚠️  Skipping AWS credential configuration (not provided via environment)"
    echo "    Make sure AWS credentials are already configured on the EC2 instance"
fi

echo ""
echo "📝 Creating .env file from SSM parameters..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP << 'ENV_SETUP'
cd /home/ubuntu/RoofEstimate

ANTHROPIC_KEY=$(aws ssm get-parameter --name "/roofestimate/prod/ANTHROPIC_API_KEY" --with-decryption --query 'Parameter.Value' --output text)
GOOGLE_AI_KEY=$(aws ssm get-parameter --name "/roofestimate/prod/GOOGLE_AI_API_KEY" --with-decryption --query 'Parameter.Value' --output text)
GOOGLE_VISION_KEY=$(aws ssm get-parameter --name "/roofestimate/prod/GOOGLE_VISION_API_KEY" --with-decryption --query 'Parameter.Value' --output text)

cat > .env << EOF
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
GOOGLE_AI_API_KEY=$GOOGLE_AI_KEY
GOOGLE_VISION_API_KEY=$GOOGLE_VISION_KEY
MAPBOX_TOKEN=
BING_MAPS_KEY=
EOF

echo "✅ .env file created"
ENV_SETUP

echo ""
echo "📦 Building UI with production API endpoint..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP bash << EOF
cd /home/ubuntu/RoofEstimate/ui

# Create production .env for UI with the correct API endpoint
cat > .env << 'ENVFILE'
VITE_API_URL=http://$INSTANCE_IP:8000
VITE_GOOGLE_MAPS_API_KEY=
ENVFILE

echo "Building UI..."
npm run build

echo "✅ UI build complete"
EOF

echo ""
echo "🔧 Creating systemd services..."

# Create API service
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP << 'API_SERVICE'
sudo tee /etc/systemd/system/roofestimate-api.service > /dev/null << 'EOF'
[Unit]
Description=RoofEstimate API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/RoofEstimate
Environment="PYTHONPATH=/home/ubuntu/RoofEstimate"
ExecStart=/home/ubuntu/RoofEstimate/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
API_SERVICE

# Create UI service
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP << 'UI_SERVICE'
sudo tee /etc/systemd/system/roofestimate-ui.service > /dev/null << 'EOF'
[Unit]
Description=RoofEstimate UI
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/RoofEstimate/ui
Environment="NODE_ENV=production"
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port 3000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
UI_SERVICE

echo ""
echo "🚀 Starting services..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP << 'START_SERVICES'
sudo systemctl daemon-reload
sudo systemctl enable roofestimate-api
sudo systemctl enable roofestimate-ui
sudo systemctl start roofestimate-api
sudo systemctl start roofestimate-ui

echo ""
echo "📊 Service status:"
sudo systemctl status roofestimate-api --no-pager || true
echo ""
sudo systemctl status roofestimate-ui --no-pager || true
START_SERVICES

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Application URLs:"
echo "   API:  http://$INSTANCE_IP:8000"
echo "   API Docs: http://$INSTANCE_IP:8000/docs"
echo "   UI:   http://$INSTANCE_IP:3000"
echo ""
echo "📋 Useful commands:"
echo "   Check API logs:  ssh -i $KEY_FILE ubuntu@$INSTANCE_IP 'sudo journalctl -u roofestimate-api -f'"
echo "   Check UI logs:   ssh -i $KEY_FILE ubuntu@$INSTANCE_IP 'sudo journalctl -u roofestimate-ui -f'"
echo "   Restart API:     ssh -i $KEY_FILE ubuntu@$INSTANCE_IP 'sudo systemctl restart roofestimate-api'"
echo "   Restart UI:      ssh -i $KEY_FILE ubuntu@$INSTANCE_IP 'sudo systemctl restart roofestimate-ui'"
echo ""
