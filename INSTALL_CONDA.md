# Conda 환경 설치 가이드

이 문서는 이미 생성된 Conda 환경에 프로젝트 의존성을 수동으로 설치하는 방법을 설명합니다.

## 📋 전제 조건

- Conda 또는 Miniconda 설치됨
- Python 3.12를 지원하는 Conda 환경이 생성되어 있음

## 🐍 Option 1: 기존 Conda 환경에 설치

이미 Conda 환경이 있다면, 해당 환경을 활성화하고 pip으로 의존성을 설치하세요.

```bash
# 환경 활성화
conda activate <your-env-name>

# Python 버전 확인 (3.12 권장)
python --version

# Backend 의존성 설치
cd backend
pip install -r requirements.txt

# Frontend 의존성 설치
cd ../frontend
npm install

# .env 파일 생성 (프로젝트 루트)
cd ..
cp .env.example .env
# .env 파일을 편집해서 vLLM 엔드포인트 설정

# 설치 완료!
```

## 🆕 Option 2: 새 Conda 환경 생성 (environment.yml 사용)

프로젝트에서 제공하는 `environment.yml` 파일로 새 환경을 생성할 수 있습니다.

### Full Stack 환경 (Backend + Frontend)

```bash
# 환경 생성
conda env create -f environment.yml

# 환경 활성화
conda activate coding-agent

# Frontend 의존성 설치
cd frontend
npm install

# .env 파일 생성 (프로젝트 루트)
cd ..
cp .env.example .env
```

### Backend Only 환경

```bash
# Backend 전용 환경 생성
cd backend
conda env create -f environment.yml

# 환경 활성화
conda activate coding-agent-backend

# .env 파일 생성 (프로젝트 루트)
cd ..
cp .env.example .env
```

## 🔧 환경 변수 설정

프로젝트 루트의 `.env` 파일을 편집해서 LLM 엔드포인트를 설정하세요:

```env
# Primary LLM endpoint
# IMPORTANT: Use localhost, NOT 0.0.0.0 for client connections
LLM_ENDPOINT=http://localhost:8001/v1
LLM_MODEL=deepseek-ai/DeepSeek-R1
MODEL_TYPE=deepseek

# Optional: Task-specific endpoints
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder
```

## 🚀 실행

### 수동 실행

```bash
# Terminal 1: Backend
conda activate coding-agent  # 또는 your-env-name
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
conda activate coding-agent  # 또는 your-env-name
cd frontend
npm run dev
```

### 스크립트로 실행 (편의 기능)

```bash
# 전체 스택을 한 번에 실행
./run_conda.sh
```

**주의:** `run_conda.sh`는 `coding-agent` 환경이 존재한다고 가정합니다. 다른 환경 이름을 사용한다면 스크립트를 수정하거나 수동으로 실행하세요.

## 🔄 의존성 업데이트

### Backend 의존성 업데이트

```bash
conda activate <your-env-name>
cd backend
pip install -r requirements.txt --upgrade
```

### Frontend 의존성 업데이트

```bash
cd frontend
npm update
```

### Conda 환경 업데이트 (environment.yml 사용 시)

```bash
conda env update -f environment.yml --prune
```

## 🧹 환경 제거

더 이상 필요하지 않은 환경을 제거하려면:

```bash
conda deactivate
conda env remove -n coding-agent
# 또는
conda env remove -n coding-agent-backend
```

## ❓ 문제 해결

### 1. Python 버전 불일치

환경의 Python 버전이 3.12가 아니라면:

```bash
# 새 환경 생성 시 Python 버전 지정
conda create -n coding-agent python=3.12
conda activate coding-agent
pip install -r backend/requirements.txt
```

### 2. 의존성 충돌

의존성 충돌이 발생하면:

```bash
# 기존 패키지 무시하고 재설치
pip install --ignore-installed packaging
pip install -r requirements.txt
```

### 3. Node.js 버전 문제

Frontend에서 Node.js 버전 문제가 발생하면:

```bash
# Conda로 Node.js 20 설치
conda install -c conda-forge nodejs=20
```

## 📚 추가 정보

자세한 내용은 메인 [README.md](README.md)를 참조하세요.
