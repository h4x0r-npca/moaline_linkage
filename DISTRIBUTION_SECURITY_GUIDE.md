# 배포 시 SmartScreen / 브라우저 차단 이슈 정리

## 현재 증상

Google Drive에서 `모아라인연동자동화.exe`를 내려받거나 실행할 때 다음 경고가 표시될 수 있습니다.

- 브라우저 다운로드 경고: 일반적으로 다운로드되지 않는 파일 또는 안전하지 않을 수 있는 파일
- Windows SmartScreen 경고: Microsoft Defender SmartScreen에서 인식할 수 없는 앱
- 게시자 표시: 알 수 없는 게시자

## 원인

이 문제는 프로그램 기능 오류가 아니라 Windows와 브라우저의 보안 평판 정책 때문입니다.

주요 원인:

- 새로 만든 exe라 다운로드/실행 평판이 없음
- Authenticode 코드 서명이 없음
- PyInstaller onefile exe는 내부 압축 해제 구조 때문에 보안 제품에서 더 민감하게 볼 수 있음
- Google Drive 공유 링크에서 exe를 직접 배포하면 브라우저가 더 강하게 경고할 수 있음
- 관리자 권한 요청(`--uac-admin`)이 포함되어 있어 SmartScreen이 더 주의 깊게 봄

## 코드 수정으로 가능한 개선

이번 프로젝트에는 exe 버전 리소스를 추가했습니다.

포함 정보:

- CompanyName: `Barogo`
- ProductName: `Moaline Linkage Automation`
- FileDescription: `Moaline Linkage Automation`
- FileVersion: `1.0.0.0`
- ProductVersion: `1.0.0.0`

이 정보는 exe 속성에 표시되며, 완전히 익명인 파일보다 배포 품질이 좋아집니다.

하지만 이것만으로 SmartScreen의 `알 수 없는 게시자`가 사라지지는 않습니다.

## 정식 해결책

정식 해결책은 코드 서명 인증서로 exe를 서명하는 것입니다.

### 권장: EV Code Signing 인증서

EV Code Signing 인증서는 Windows SmartScreen 평판 확보에 가장 유리합니다. 새 프로그램이어도 일반 코드서명 인증서보다 초기 차단이 덜합니다.

### 일반 Code Signing 인증서

일반 OV 코드서명 인증서도 `알 수 없는 게시자` 문제를 해결할 수 있습니다. 다만 SmartScreen 평판은 배포량과 시간이 쌓이면서 개선되는 경우가 많습니다.

## 서명 예시

Windows SDK의 `signtool.exe`가 필요합니다.

예시:

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a dist\모아라인연동자동화.exe
```

인증서 파일이 있는 경우:

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f certificate.pfx /p 비밀번호 dist\모아라인연동자동화.exe
```

서명 확인:

```powershell
signtool verify /pa /v dist\모아라인연동자동화.exe
```

## 임시 배포 방법

코드서명 전까지는 아래 방식으로 안내할 수 있습니다.

### Google Drive 다운로드 경고

다운로드 항목에서 다음 순서로 진행합니다.

1. 더보기 메뉴 클릭
2. `유지` 선택
3. 추가 경고가 나오면 `그래도 유지` 선택

### Windows SmartScreen 경고

SmartScreen 화면에서 다음 순서로 진행합니다.

1. `자세히` 클릭
2. `실행` 클릭

단, 이 안내는 내부 테스트나 신뢰된 거래처 배포에만 권장합니다. 외부 대량 배포는 코드서명 후 진행하는 것이 좋습니다.

## 추가 권장 배포 방식

- exe 단독 업로드보다 zip 압축 후 배포
- 배포 문서에 SHA256 해시값 제공
- 회사 공식 다운로드 페이지 또는 신뢰 가능한 도메인에서 배포
- 코드서명 후 배포
- 버전 번호를 올릴 때마다 파일명에 버전 포함

예시:

```text
모아라인연동자동화_v1.0_20260601.exe
```

## 결론

현재 차단은 프로그램 오류가 아니라 unsigned exe에 대한 보안 경고입니다.

이번 수정으로 exe 메타데이터는 보강했지만, `알 수 없는 게시자`를 근본적으로 해결하려면 코드서명 인증서가 필요합니다. 배포 안정성을 위해서는 코드서명 후 Google Drive보다 공식 배포 경로를 사용하는 것이 가장 좋습니다.
