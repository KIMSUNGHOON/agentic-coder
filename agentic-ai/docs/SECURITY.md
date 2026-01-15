# Agentic 2.0 보안 가이드

## 개요

Agentic 2.0는 on-premise 로컬 서버 환경에서 실행되며, 모든 데이터는 로컬에만 저장됩니다. 외부 네트워크로 데이터가 유출되지 않도록 설계되었습니다.

## 데이터 저장 정책

### 1. 로컬 전용 저장

**모든 데이터는 로컬 서버 내부에만 저장됩니다:**

```yaml
# config/config.yaml - 보안 설정
security:
  # 데이터 저장 위치 (로컬 전용)
  data_storage:
    local_only: true
    base_path: "./data"

  # 외부 전송 차단
  network:
    block_external_upload: true
    allowed_hosts:
      - "localhost"
      - "127.0.0.1"
      - "your-local-llm-server-ip"  # vLLM 서버 IP만 허용

  # 로그 저장 (로컬 전용)
  logging:
    local_only: true
    log_path: "./logs"

  # 세션 데이터 (로컬 DB만)
  persistence:
    backend: "sqlite"  # 또는 "postgres" (로컬)
    local_only: true
```

### 2. 저장되는 데이터 종류

**로컬 저장 데이터:**

| 데이터 종류 | 저장 위치 | 외부 전송 |
|-----------|---------|----------|
| 프롬프트 | `./logs/prompts/` | ❌ 차단 |
| LLM 응답 | `./logs/responses/` | ❌ 차단 |
| 세션 데이터 | `./data/sessions/` | ❌ 차단 |
| 체크포인트 | `./data/checkpoints.db` | ❌ 차단 |
| 작업 결과 | `./workspace/` | ❌ 차단 |
| 로그 | `./logs/` | ❌ 차단 |
| 메트릭 | `./logs/metrics.jsonl` | ❌ 차단 |

**외부 통신:**

| 목적 | 대상 | 허용 여부 |
|-----|-----|----------|
| LLM 호출 | vLLM 로컬 서버 | ✅ 허용 |
| 기타 모든 통신 | 외부 인터넷 | ❌ 차단 |

### 3. LLM 통신 보안

**vLLM 로컬 서버만 통신:**

```python
# core/llm_client.py 설정
endpoints = [
    EndpointConfig(
        url="http://localhost:8000/v1",  # 로컬 서버만
        name="local-vllm",
        api_key="not-needed"  # API Key 불필요
    )
]

# 외부 API 호출 차단
llm_client = DualEndpointLLMClient(
    endpoints=endpoints,
    model_name="gpt-oss-120b",
    # 외부 통신 없음
)
```

## 보안 검증

### 1. 네트워크 격리 확인

**방화벽 설정 (예시):**

```bash
# 외부 통신 차단, 로컬만 허용
sudo ufw default deny outgoing
sudo ufw allow out to 127.0.0.1
sudo ufw allow out to <vLLM-server-IP>
sudo ufw enable
```

**네트워크 검증:**

```bash
# 외부 통신 시도 (실패해야 정상)
curl https://api.openai.com  # Connection refused

# 로컬 통신 시도 (성공해야 정상)
curl http://localhost:8000/v1/health  # OK
```

### 2. 데이터 암호화 (선택)

**로컬 데이터 암호화:**

```yaml
security:
  encryption:
    enabled: true
    algorithm: "AES-256-GCM"
    key_file: "/secure/path/encryption.key"

  # 세션 데이터 암호화
  persistence:
    encrypt_checkpoints: true

  # 로그 암호화
  logging:
    encrypt_logs: true
```

### 3. 접근 제어

**파일 권한 설정:**

```bash
# 데이터 디렉토리 권한 제한
chmod 700 ./data
chmod 700 ./logs
chmod 700 ./workspace

# 소유자만 접근
chown -R agentic:agentic ./data ./logs ./workspace
```

**사용자 격리:**

```bash
# 전용 사용자로 실행
sudo -u agentic python -m agentic
```

## 감사 및 모니터링

### 1. 접근 로그

**모든 데이터 접근 기록:**

```python
# observability/audit_logger.py
class AuditLogger:
    def log_data_access(self, user, resource, action):
        """모든 데이터 접근 기록"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "resource": resource,
            "action": action,
            "ip": "local",
        }
        # 로컬 감사 로그에만 기록
        with open("./logs/audit.jsonl", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
```

### 2. 네트워크 모니터링

**외부 통신 시도 감지:**

```python
# security/network_monitor.py
class NetworkMonitor:
    def monitor_connections(self):
        """외부 연결 시도 감지"""
        allowed_hosts = ["localhost", "127.0.0.1", "<vLLM-IP>"]

        for conn in get_active_connections():
            if conn.remote not in allowed_hosts:
                logger.critical(
                    f"🚨 Unauthorized external connection detected: {conn.remote}"
                )
                # 연결 차단
                conn.close()
```

### 3. 정기 감사

**주기적 보안 검사:**

```bash
#!/bin/bash
# security/audit_check.sh

echo "=== Agentic 2.0 Security Audit ==="

# 1. 외부 통신 확인
echo "Checking for external connections..."
netstat -an | grep ESTABLISHED | grep -v "127.0.0.1\|localhost"

# 2. 데이터 파일 권한 확인
echo "Checking file permissions..."
find ./data ./logs -type f -not -perm 600

# 3. 감사 로그 확인
echo "Recent audit log entries:"
tail -20 ./logs/audit.jsonl

# 4. 디스크 사용량 확인
echo "Disk usage:"
du -sh ./data ./logs ./workspace
```

## 규정 준수

### GDPR / 개인정보보호

**데이터 최소화:**
- 필요한 데이터만 수집
- 익명화 처리
- 보관 기간 제한

**데이터 주체 권리:**
- 데이터 삭제 (Right to be forgotten)
- 데이터 이동 (Data portability)

**구현:**

```python
# security/privacy.py
class PrivacyManager:
    def anonymize_data(self, data):
        """개인정보 익명화"""
        # 이름, 이메일 등 마스킹
        pass

    def delete_user_data(self, user_id):
        """사용자 데이터 완전 삭제"""
        # 모든 로컬 데이터 삭제
        pass

    def export_user_data(self, user_id):
        """사용자 데이터 내보내기"""
        # 로컬 데이터 압축 내보내기
        pass
```

## 재해 복구

### 로컬 백업

**정기 백업:**

```bash
#!/bin/bash
# backup.sh - 로컬 백업만

BACKUP_DIR="/backup/agentic"
DATE=$(date +%Y%m%d_%H%M%S)

# 데이터 백업
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" ./data

# 로그 백업
tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" ./logs

# 설정 백업
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" ./config

# 오래된 백업 삭제 (7일 이상)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

### 복구 절차

```bash
# 복구
cd /home/user/agentic-coder/agentic-ai

# 데이터 복구
tar -xzf /backup/agentic/data_YYYYMMDD_HHMMSS.tar.gz

# 로그 복구
tar -xzf /backup/agentic/logs_YYYYMMDD_HHMMSS.tar.gz

# 설정 복구
tar -xzf /backup/agentic/config_YYYYMMDD_HHMMSS.tar.gz
```

## 보안 체크리스트

운영 전 확인사항:

- [ ] 모든 데이터 저장 경로가 로컬인지 확인
- [ ] 외부 API 호출 코드 없는지 확인
- [ ] vLLM 서버 외 외부 통신 차단 확인
- [ ] 방화벽 설정 확인
- [ ] 파일 권한 설정 (700/600) 확인
- [ ] 전용 사용자 계정으로 실행 확인
- [ ] 로그 로테이션 설정 확인
- [ ] 백업 스크립트 동작 확인
- [ ] 감사 로그 기록 확인
- [ ] 네트워크 모니터링 활성화 확인

## 문제 발생 시 대응

### 의심스러운 활동 감지

```python
# security/incident_response.py
class IncidentResponse:
    def handle_security_incident(self, incident_type):
        """보안 사고 대응"""

        # 1. 로그 기록
        logger.critical(f"Security incident: {incident_type}")

        # 2. 시스템 일시 중지
        self.pause_system()

        # 3. 관리자 알림
        self.notify_admin(incident_type)

        # 4. 감사 로그 백업
        self.backup_audit_logs()

        # 5. 포렌식 데이터 수집
        self.collect_forensic_data()
```

### 긴급 연락처

- 시스템 관리자: [관리자 연락처]
- 보안 담당자: [보안 담당자 연락처]

## 참고 자료

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
