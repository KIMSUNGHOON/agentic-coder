# Troubleshooting Guide

## File Watcher Limit Errors (ENOSPC)

### Symptom
```
Error: ENOSPC: System limit for number of file watchers reached
```

This error occurs in development mode when the system runs out of file watchers for hot-reload functionality.

### Quick Solutions

#### Solution 1: Use Polling (Frontend - Already Applied)
The frontend Vite config now uses polling instead of native file watchers:
```typescript
// frontend/vite.config.ts
watch: {
  usePolling: true,
  interval: 1000,  // Check for changes every 1 second
}
```

**Pros**: No system changes needed
**Cons**: Slightly slower (1-second delay), higher CPU usage

#### Solution 2: Increase System Limit (Recommended)

**Temporary fix (until reboot):**
```bash
sudo sysctl -w fs.inotify.max_user_watches=524288
```

**Permanent fix:**
```bash
# Run the provided script
sudo bash scripts/increase_file_watchers.sh

# Or manually
echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**Verify the change:**
```bash
cat /proc/sys/fs/inotify/max_user_watches
# Should output: 524288
```

#### Solution 3: Exclude More Directories

Already configured in:
- `run.py`: Backend uvicorn excludes data/, workspace/, logs
- `vite.config.ts`: Frontend excludes backend/, data/, workspace/
- `.gitignore`: Excludes data/, workspace/

### Backend Hot-Reload Issues

If backend still has issues, disable auto-reload:
```bash
# In run.py, remove --reload flag (line 123)
# Or manually run:
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000  # No --reload
```

### Verification

After applying fixes, restart servers:
```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Both should start without ENOSPC errors.

---

## Other Common Issues

### Port Already in Use
```
Error: Address already in use
```

**Solution:**
```bash
# Find and kill process using the port
sudo lsof -ti:8000 | xargs kill -9  # Backend
sudo lsof -ti:3000 | xargs kill -9  # Frontend

# Or use the run script which handles this automatically
python run.py
```

### Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'app'
```

**Solution:**
```bash
# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### Permission Denied Errors

**Symptom:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Or run with python explicitly
python run.py
```
