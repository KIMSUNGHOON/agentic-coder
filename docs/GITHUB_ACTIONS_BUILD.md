# GitHub Actions 자동 빌드 가이드

## 📋 개요

GitHub Actions를 사용하여 Linux, Windows, macOS 바이너리를 자동으로 빌드하고 배포합니다.

## 🚀 사용 방법

### 방법 1: 버전 태그로 자동 빌드 및 릴리스 생성

```bash
# 1. 코드 변경 후 커밋
git add .
git commit -m "Update remote client"

# 2. 버전 태그 생성 및 푸시
git tag v1.0.0
git push origin v1.0.0

# 3. GitHub Actions가 자동으로:
#    - Linux, Windows, macOS 바이너리 빌드
#    - GitHub Release 자동 생성
#    - 3개 바이너리 Release에 첨부
```

**결과:**
- `https://github.com/KIMSUNGHOON/agentic-coder/releases/tag/v1.0.0`
- 다운로드 링크:
  - `agentic-coder-client-linux`
  - `agentic-coder-client-windows.exe`
  - `agentic-coder-client-macos`

### 방법 2: GitHub UI에서 수동 빌드

1. GitHub 저장소 접속
2. **Actions** 탭 클릭
3. **Build Remote Client Binaries** 워크플로우 선택
4. **Run workflow** 버튼 클릭
5. 빌드 완료 후 **Artifacts** 섹션에서 다운로드

**주의:** 수동 빌드는 Release를 생성하지 않고 Artifacts만 생성합니다.

## 📦 빌드 결과물

### Artifacts (수동 빌드 시)

**저장 위치:** 각 워크플로우 실행의 Artifacts 섹션

- `agentic-coder-client-linux` (ZIP)
- `agentic-coder-client-windows.exe` (ZIP)
- `agentic-coder-client-macos` (ZIP)

**다운로드 방법:**
```bash
# GitHub UI에서:
# Actions → Build Remote Client Binaries → 최신 실행 → Artifacts
```

### Release (태그 빌드 시)

**저장 위치:** `https://github.com/KIMSUNGHOON/agentic-coder/releases`

- 모든 바이너리가 Release에 자동 첨부
- 버전별 관리 가능
- 다운로드 링크 자동 생성

## 🔄 버전 관리

### 시맨틱 버저닝

```bash
# Major version (큰 변경)
git tag v2.0.0

# Minor version (기능 추가)
git tag v1.1.0

# Patch version (버그 수정)
git tag v1.0.1

# Pre-release
git tag v1.0.0-beta.1
git tag v1.0.0-rc.1
```

### 태그 관리

```bash
# 로컬 태그 목록
git tag

# 원격 태그 목록
git ls-remote --tags origin

# 태그 삭제 (로컬)
git tag -d v1.0.0

# 태그 삭제 (원격)
git push origin :refs/tags/v1.0.0

# 특정 커밋에 태그
git tag v1.0.0 abc1234
git push origin v1.0.0
```

## 🛠️ 워크플로우 구성

### 파일 위치

`.github/workflows/build-remote-client.yml`

### 트리거 조건

1. **태그 푸시:** `v*` 패턴 (예: v1.0.0, v2.1.3)
2. **수동 실행:** GitHub Actions UI에서

### 빌드 매트릭스

| OS | Runner | 결과물 |
|----|--------|--------|
| Linux | ubuntu-latest | agentic-coder-client-linux |
| Windows | windows-latest | agentic-coder-client-windows.exe |
| macOS | macos-latest | agentic-coder-client-macos |

### 빌드 단계

1. **코드 체크아웃**
2. **Python 3.10 설정**
3. **의존성 설치** (pyinstaller, rich, httpx)
4. **플랫폼별 빌드 스크립트 실행**
5. **바이너리 테스트** (--help 실행)
6. **Artifacts 업로드**
7. **Release 생성** (태그 빌드 시)

## 📊 빌드 상태 확인

### GitHub UI

```
Repository → Actions → Build Remote Client Binaries
```

**상태 아이콘:**
- ✅ 녹색 체크: 성공
- ❌ 빨간 X: 실패
- 🟡 노란 점: 진행 중

### 빌드 로그 확인

1. 실패한 워크플로우 클릭
2. 실패한 job 클릭
3. 실패한 step 확장
4. 로그 확인

**일반적인 오류:**
- Python 의존성 설치 실패 → requirements 확인
- PyInstaller 빌드 오류 → import 경로 확인
- Artifact 업로드 실패 → 경로 확인

## 🔐 보안 및 권한

### GITHUB_TOKEN

워크플로우는 자동으로 제공되는 `GITHUB_TOKEN`을 사용합니다.

**권한:**
- `contents: write` - Release 생성 권한 필요
- 저장소 Settings → Actions → General → Workflow permissions 확인

### Artifacts 보존 기간

**기본 설정:** 90일

**변경 방법:**
```yaml
- name: Upload artifact
  uses: actions/upload-artifact@v4
  with:
    name: ${{ matrix.artifact_name }}
    path: ${{ matrix.binary_path }}
    retention-days: 30  # 30일로 변경
```

## 🚢 배포 워크플로우

### 개발 → 프로덕션

```bash
# 1. 개발 브랜치에서 작업
git checkout -b feature/new-feature
# ... 코드 수정 ...
git commit -m "Add new feature"

# 2. 메인 브랜치로 병합
git checkout main
git merge feature/new-feature

# 3. 버전 태그 생성 및 릴리스
git tag v1.1.0
git push origin main
git push origin v1.1.0

# 4. GitHub Actions 자동 실행
# 5. Release 페이지에서 바이너리 확인
```

### 팀 배포

```bash
# 1. Release 페이지 링크 공유
https://github.com/KIMSUNGHOON/agentic-coder/releases/latest

# 2. 팀원이 플랫폼별 바이너리 다운로드
# Linux 사용자
wget https://github.com/.../agentic-coder-client-linux
chmod +x agentic-coder-client-linux
./agentic-coder-client-linux

# Windows 사용자
# 브라우저에서 .exe 다운로드 후 실행

# macOS 사용자
curl -L -O https://github.com/.../agentic-coder-client-macos
chmod +x agentic-coder-client-macos
./agentic-coder-client-macos
```

## 📝 Release Notes 자동 생성

### 현재 구성

Release body는 YAML에 하드코딩:

```yaml
body: |
  ## Agentic Coder Remote Client - ${{ github.ref_name }}
  ...
```

### 자동 생성 (선택사항)

**방법 1: GitHub 자동 생성**

```yaml
- name: Create Release
  uses: softprops/action-gh-release@v1
  with:
    generate_release_notes: true  # 추가
```

**방법 2: CHANGELOG.md 사용**

```yaml
- name: Extract Release Notes
  id: extract_notes
  run: |
    VERSION=${{ github.ref_name }}
    NOTES=$(sed -n "/## $VERSION/,/## /p" CHANGELOG.md | sed '$d')
    echo "notes<<EOF" >> $GITHUB_OUTPUT
    echo "$NOTES" >> $GITHUB_OUTPUT
    echo "EOF" >> $GITHUB_OUTPUT

- name: Create Release
  uses: softprops/action-gh-release@v1
  with:
    body: ${{ steps.extract_notes.outputs.notes }}
```

## 🐛 트러블슈팅

### 빌드 실패

**증상:** PyInstaller 빌드 오류

**해결:**
```bash
# 로컬에서 먼저 테스트
pip install pyinstaller rich httpx
./scripts/build_remote_client.sh

# 오류 수정 후 재푸시
```

### Release 생성 실패

**증상:** `Resource not accessible by integration`

**해결:**
1. Settings → Actions → General
2. Workflow permissions → Read and write permissions 선택
3. Save

### Artifacts 다운로드 실패

**증상:** `Artifact not found`

**해결:**
- 빌드 로그에서 artifact 경로 확인
- YAML의 `path` 설정 확인

### macOS 실행 권한 오류

**증상:** `"agentic-coder-client-macos" cannot be opened`

**해결:**
```bash
# Gatekeeper 우회
xattr -d com.apple.quarantine agentic-coder-client-macos
chmod +x agentic-coder-client-macos
```

## 📈 고급 설정

### 캐싱으로 빌드 속도 향상

이미 적용됨:
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.10'
    cache: 'pip'  # pip 캐싱 활성화
```

### 병렬 빌드

이미 적용됨:
```yaml
strategy:
  matrix:
    include:
      - os: ubuntu-latest
      - os: windows-latest
      - os: macos-latest
# 3개 OS가 동시에 빌드
```

### 조건부 빌드

특정 브랜치에서만 빌드:
```yaml
on:
  push:
    branches:
      - main
      - release/*
    tags:
      - 'v*'
```

### 슬랙 알림 추가

```yaml
- name: Notify Slack
  if: success()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "Release ${{ github.ref_name }} created! 🎉"
      }
```

## 📚 참고 자료

- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [PyInstaller 공식 문서](https://pyinstaller.org/)
- [softprops/action-gh-release](https://github.com/softprops/action-gh-release)
- [Remote Client Binary 가이드](./REMOTE_CLIENT_BINARY.md)

## ✅ 체크리스트

배포 전 확인:

- [ ] 로컬에서 빌드 테스트 완료
- [ ] `--help`, `--version` 동작 확인
- [ ] CHANGELOG.md 업데이트 (선택)
- [ ] 버전 번호 결정 (시맨틱 버저닝)
- [ ] GitHub Actions 권한 설정 확인
- [ ] 태그 푸시 전 코드 리뷰 완료
- [ ] Release Notes 내용 확인

---

**Quick Start:**

```bash
# 첫 릴리스 생성
git tag v1.0.0
git push origin v1.0.0

# GitHub에서 확인
# https://github.com/KIMSUNGHOON/agentic-coder/releases

# 바이너리 다운로드 및 배포
```
