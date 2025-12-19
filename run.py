#!/usr/bin/env python3
"""Unified execution script for AI Code Assistance Application

This script orchestrates the complete system:
- Backend FastAPI server with LangGraph workflow
- Frontend React development server
- DeepSeek-R1 reasoning engine
- Qwen2.5-Coder implementation engine
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class SystemRunner:
    """Unified system runner"""

    def __init__(self):
        self.processes = []
        self.project_root = Path(__file__).parent

    def print_header(self, message: str):
        """Print colored header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{message.center(60)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")

    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")

    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.OKCYAN}ℹ️  {message}{Colors.ENDC}")

    def check_port(self, port: int) -> bool:
        """Check if port is available"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False

    def kill_port(self, port: int):
        """Kill process using specified port"""
        self.print_info(f"Checking port {port}...")

        try:
            # Try lsof first
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True
            )

            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        self.print_success(f"Killed process {pid} on port {port}")
                    except ProcessLookupError:
                        pass

                time.sleep(1)  # Wait for port to be released
        except FileNotFoundError:
            # lsof not available, try fuser
            try:
                subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    capture_output=True
                )
                self.print_success(f"Freed port {port}")
            except FileNotFoundError:
                self.print_warning("Could not check port (lsof/fuser not available)")

    def start_backend(self):
        """Start FastAPI backend server"""
        self.print_header("Starting Backend Server")

        # Kill any existing process on port 8000
        self.kill_port(8000)

        backend_dir = self.project_root / "backend"

        if not backend_dir.exists():
            self.print_error(f"Backend directory not found: {backend_dir}")
            return False

        self.print_info("Starting uvicorn server...")

        # Set PYTHONPATH to include project root for shared module access
        env = os.environ.copy()
        project_pythonpath = str(self.project_root)
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{project_pythonpath}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = project_pythonpath

        process = subprocess.Popen(
            ["python", "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd=backend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.processes.append(("Backend", process))

        # Wait for server to start
        time.sleep(3)

        if process.poll() is None:
            self.print_success("Backend server started on http://localhost:8000")
            return True
        else:
            self.print_error("Backend server failed to start")
            stderr = process.stderr.read().decode()
            print(stderr)
            return False

    def start_frontend(self):
        """Start React frontend development server"""
        self.print_header("Starting Frontend Development Server")

        # Kill any existing process on port 3000
        self.kill_port(3000)

        frontend_dir = self.project_root / "frontend"

        if not frontend_dir.exists():
            self.print_error(f"Frontend directory not found: {frontend_dir}")
            return False

        # Check if node_modules exists
        if not (frontend_dir / "node_modules").exists():
            self.print_info("Installing frontend dependencies...")
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)

        self.print_info("Starting React development server...")

        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.processes.append(("Frontend", process))

        # Wait for server to start
        time.sleep(5)

        if process.poll() is None:
            self.print_success("Frontend server started on http://localhost:3000")
            return True
        else:
            self.print_error("Frontend server failed to start")
            stderr = process.stderr.read().decode()
            print(stderr)
            return False

    def show_status(self):
        """Show system status"""
        self.print_header("System Status")

        print(f"{Colors.BOLD}Running Services:{Colors.ENDC}")
        for name, process in self.processes:
            if process.poll() is None:
                print(f"  {Colors.OKGREEN}●{Colors.ENDC} {name}: Running (PID: {process.pid})")
            else:
                print(f"  {Colors.FAIL}●{Colors.ENDC} {name}: Stopped")

        print(f"\n{Colors.BOLD}Endpoints:{Colors.ENDC}")
        print(f"  Backend API: http://localhost:8000")
        print(f"  API Docs: http://localhost:8000/docs")
        print(f"  Frontend: http://localhost:3000")
        print(f"  Health Check: http://localhost:8000/health")

    def cleanup(self):
        """Cleanup all processes"""
        self.print_header("Shutting Down")

        for name, process in self.processes:
            if process.poll() is None:
                self.print_info(f"Stopping {name}...")
                process.terminate()

                try:
                    process.wait(timeout=5)
                    self.print_success(f"{name} stopped")
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.print_warning(f"{name} force killed")

    def run(self):
        """Run the complete system"""
        self.print_header("AI Code Assistance Application")

        print(f"{Colors.BOLD}Models:{Colors.ENDC}")
        print(f"  Reasoning: DeepSeek-R1")
        print(f"  Implementation: Qwen2.5-Coder-32B\n")

        try:
            # Start backend
            if not self.start_backend():
                self.print_error("Failed to start backend")
                return 1

            # Start frontend
            if not self.start_frontend():
                self.print_error("Failed to start frontend")
                return 1

            # Show status
            self.show_status()

            print(f"\n{Colors.OKGREEN}System ready! Press Ctrl+C to stop.{Colors.ENDC}\n")

            # Keep running
            while True:
                time.sleep(1)
                # Check if any process died
                for name, process in self.processes:
                    if process.poll() is not None:
                        self.print_error(f"{name} stopped unexpectedly")
                        return 1

        except KeyboardInterrupt:
            print("\n")
            self.print_info("Received shutdown signal")
        except Exception as e:
            self.print_error(f"Error: {e}")
            return 1
        finally:
            self.cleanup()

        return 0


def main():
    """Main entry point"""
    runner = SystemRunner()
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
