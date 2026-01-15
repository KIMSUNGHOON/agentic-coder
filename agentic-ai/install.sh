#!/bin/bash
# Agentic 2.0 Installation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo ""
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Python version
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_info "Python version: $PYTHON_VERSION"

        # Check if Python >= 3.10
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
            print_error "Python 3.10+ is required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 is not installed"
        exit 1
    fi

    # Check pip
    if command_exists pip3; then
        print_info "pip3 is installed"
    else
        print_error "pip3 is not installed"
        exit 1
    fi

    # Check git (optional)
    if command_exists git; then
        print_info "git is installed"
    else
        print_warn "git is not installed (optional)"
    fi

    print_info "All prerequisites met ✓"
}

# Create virtual environment
create_venv() {
    print_header "Creating Virtual Environment"

    if [ -d "venv" ]; then
        print_warn "Virtual environment already exists"
        read -p "Remove and recreate? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
        else
            print_info "Skipping virtual environment creation"
            return
        fi
    fi

    python3 -m venv venv
    print_info "Virtual environment created ✓"
}

# Activate virtual environment
activate_venv() {
    print_info "Activating virtual environment..."
    source venv/bin/activate
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    if [ -f "requirements.txt" ]; then
        pip install --upgrade pip
        pip install -r requirements.txt
        print_info "Dependencies installed ✓"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
}

# Create directories
create_directories() {
    print_header "Creating Directories"

    mkdir -p data/sessions
    mkdir -p logs
    mkdir -p workspace
    mkdir -p config

    print_info "Directories created ✓"
}

# Create .env file
create_env_file() {
    print_header "Creating Environment File"

    if [ -f ".env" ]; then
        print_warn ".env file already exists"
        read -p "Overwrite? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Skipping .env creation"
            return
        fi
    fi

    cat > .env <<EOF
# Agentic 2.0 Environment Variables

# LLM Configuration
LLM_API_KEY_1=your-api-key-1
LLM_API_KEY_2=your-api-key-2

# Database Configuration (if using PostgreSQL)
POSTGRES_USER=agentic
POSTGRES_PASSWORD=your-secure-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agentic

# Observability
AGENTIC_LOG_LEVEL=INFO
AGENTIC_DEBUG=false

# Monitoring
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
EOF

    print_info ".env file created ✓"
    print_warn "Please edit .env and set your actual API keys and passwords"
}

# Create default config
create_config() {
    print_header "Creating Default Configuration"

    if [ -f "config/config.yaml" ]; then
        print_warn "config/config.yaml already exists"
        print_info "Skipping config creation"
        return
    fi

    cat > config/config.yaml <<'EOF'
llm:
  model_name: "gpt-oss-120b"
  temperature: 0.7
  max_tokens: 4096
  mode: "active-active"

  endpoints:
    - url: "http://localhost:8000/v1"
      api_key: "${LLM_API_KEY_1}"
      name: "endpoint1"
      timeout: 30

    - url: "http://localhost:8001/v1"
      api_key: "${LLM_API_KEY_2}"
      name: "endpoint2"
      timeout: 30

safety:
  max_tool_calls_per_task: 50
  allowed_domains:
    - "github.com"
    - "stackoverflow.com"

workflows:
  default_timeout: 300
  max_iterations: 10

persistence:
  checkpointing:
    enabled: true
    backend: "sqlite"
    sqlite:
      db_path: "./data/checkpoints.db"

observability:
  logging:
    enabled: true
    log_dir: "./logs"
    log_file: "agent.jsonl"
    console_level: "INFO"

production:
  endpoint_selection:
    enabled: true
  error_handling:
    enabled: true
  health_monitoring:
    enabled: true
EOF

    print_info "Default configuration created ✓"
}

# Run tests
run_tests() {
    print_header "Running Tests"

    read -p "Run tests? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping tests"
        return
    fi

    if command_exists pytest; then
        pytest tests/ -v
        print_info "Tests completed ✓"
    else
        print_warn "pytest not found. Installing..."
        pip install pytest
        pytest tests/ -v
        print_info "Tests completed ✓"
    fi
}

# Print next steps
print_next_steps() {
    print_header "Installation Complete!"

    cat <<EOF
${GREEN}Next Steps:${NC}

1. Activate virtual environment:
   ${YELLOW}source venv/bin/activate${NC}

2. Edit configuration:
   ${YELLOW}nano .env${NC}
   ${YELLOW}nano config/config.yaml${NC}

3. Run tests:
   ${YELLOW}python examples/test_integration_full.py${NC}

4. Start application:
   ${YELLOW}python main.py${NC}

   Or with Docker:
   ${YELLOW}docker-compose up -d${NC}

5. Check health:
   ${YELLOW}curl http://localhost:8080/health/ready${NC}

${GREEN}Documentation:${NC}
   - User Guide: docs/USER_GUIDE.md
   - API Reference: docs/API_REFERENCE.md
   - Configuration: docs/CONFIGURATION.md
   - Troubleshooting: docs/TROUBLESHOOTING.md

${GREEN}Support:${NC}
   - Issues: https://github.com/your-repo/issues
   - Docs: https://github.com/your-repo/docs

EOF
}

# Main installation flow
main() {
    print_header "Agentic 2.0 Installation"

    check_prerequisites
    create_venv
    activate_venv
    install_dependencies
    create_directories
    create_env_file
    create_config
    run_tests
    print_next_steps
}

# Run main function
main
