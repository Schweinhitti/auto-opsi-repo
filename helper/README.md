# Helper Scripts

This directory contains utility scripts for managing the OPSI auto-repository.

## Available Scripts

- `build.sh` - Build Docker images with --pull for freshness
- `test.sh` - Run unit tests and validate configurations
- `run.sh` - Start the services and create initial configuration
- `status.sh` - Show service status, health, and last build summary
- `logs.sh` - View logs for specific services (builder, web, or all)
- `dry-run.sh` - Run a builder dry run to check for upstream changes
- `cleanup.sh` - Stop services and clean up resources

## Usage

Make scripts executable if needed:
```bash
chmod +x helper/*.sh
```

Examples:
```bash
# Build images
./helper/build.sh

# Run tests
./helper/test.sh

# Start services
./helper/run.sh

# Check status
./helper/status.sh

# View builder logs
./helper/logs.sh builder

# Dry run for a specific product
./helper/dry-run.sh auto-firefox

# Clean up
./helper/cleanup.sh
```