# 🎭 Mock Mode - vLLM 없이 테스트하기

집에서 vLLM 서버 없이도 애플리케이션을 테스트할 수 있는 Mock Mode입니다.

## 🚀 빠른 시작 (macOS / Linux)

### 방법 1: 간단한 실행 스크립트 (추천)

```bash
./RUN_MOCK.sh
```

### 방법 2: 직접 실행

```bash
cd frontend
npm install
npm start
```

## 📝 사용 가능한 명령어

```bash
# Mock API 서버만 실행
npm run mock

# 프론트엔드만 실행
npm run dev

# Mock API + 프론트엔드 동시 실행 (추천)
npm start
```

## 🌐 접속 주소

- **프론트엔드**: http://localhost:5173
- **Mock API**: http://localhost:8000/api

## ✨ Mock Mode 기능

Mock Mode에서는 실제 vLLM 서버 없이도 모든 기능을 테스트할 수 있습니다:

### ✅ 지원되는 기능

- ✅ **Chat Mode**: AI와 대화하기 (Mock 응답)
- ✅ **Workflow Mode**: 멀티 에이전트 워크플로우
  - Planning Agent
  - Coding Agent
  - Review Agent
- ✅ **Streaming**: 실시간 타이핑 효과
- ✅ **Conversation 저장/불러오기**: 인메모리 저장소
- ✅ **모든 UI 기능**: 완벽한 UI 테스트

### 🎨 Mock 응답 예시

Mock 서버는 다양한 응답을 랜덤하게 반환합니다:

- 코드 예제
- 단계별 설명
- 문제 해결 방법
- Workflow 실행 과정

## 🔧 기술 스택

- **Mock Server**: Express.js
- **CORS**: 모든 출처 허용 (개발 모드)
- **In-Memory Storage**: 대화 임시 저장
- **Streaming**: Chunked Transfer Encoding

## 💡 실제 서버와의 차이점

| 기능 | Mock Mode | 실제 서버 |
|------|-----------|----------|
| vLLM 필요 | ❌ 불필요 | ✅ 필요 |
| AI 응답 | 🎭 Mock 데이터 | 🤖 실제 AI |
| 응답 속도 | ⚡ 매우 빠름 | 🐢 모델 속도에 따라 |
| 데이터 저장 | 💾 메모리 (재시작 시 삭제) | 💽 데이터베이스 |
| 네트워크 | 🏠 로컬 전용 | 🌐 배포 가능 |

## 🎯 사용 시나리오

### 1. UI/UX 개발 및 테스트
```bash
./RUN_MOCK.sh
```
- vLLM 없이 프론트엔드 개발
- 디자인 수정 및 테스트
- 에러 처리 확인

### 2. 데모 및 프레젠테이션
- 서버 설정 없이 바로 실행
- 안정적인 데모 환경
- 네트워크 독립적

### 3. 집에서 작업
- vLLM 리소스 불필요
- macOS, Windows, Linux 모두 지원
- 빠른 개발 사이클

## 🛠️ Troubleshooting

### Port 이미 사용 중
```bash
# 8000 포트 확인
lsof -ti:8000 | xargs kill -9

# 5173 포트 확인
lsof -ti:5173 | xargs kill -9
```

### npm 패키지 문제
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### 서버가 시작되지 않음
```bash
# Node.js 버전 확인 (14 이상 필요)
node --version

# npm 재설치
npm install -g npm@latest
```

## 📦 의존성

### 필수
- Node.js 14.x 이상
- npm 6.x 이상

### 자동 설치됨
- express
- cors
- concurrently
- (기타 프론트엔드 패키지들)

## 🔄 실제 서버로 전환하기

Mock Mode에서 실제 vLLM 서버로 전환하려면:

1. vLLM 서버 시작
2. 백엔드 서버 실행
3. 프론트엔드에서 API URL 변경 (필요시)

## 📚 추가 정보

- Mock 서버 코드: `frontend/mock-server/server.js`
- 응답 커스터마이징: `mockResponses` 배열 수정
- 워크플로우 변경: `POST /api/workflow/execute` 핸들러 수정

---

**Happy Coding! 🚀**
