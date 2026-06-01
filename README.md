# 모아라인 연동 자동화

모아라인 플러스/상점 프로그램의 연동 설정을 자동화하는 Windows GUI 도구입니다.

기존 매크로 방식처럼 화면을 클릭하지 않고, Windows 레지스트리, com0com 명령행 도구, 모아라인 INI 설정 파일을 직접 확인하고 수정합니다.

## 주요 기능

- 모아라인 플러스/상점 설치 자동 감지
- com0com 설치 확인 및 필요 시 설치
- 가상 COM 포트 페어 자동 생성
- `낮은연동포트번호 사용` 옵션으로 COM1부터 비어 있는 포트 탐색
- 모아라인 플러스 `LinkAge.ini` 자동 설정
- 모아라인 상점 `Call Star.ini` 자동 설정
- 설정 파일 백업 및 연동 삭제/복원
- 모아라인 프로그램 자동 재시작
- 현재 연동 상태 표시
- Python 3.8 기준 단일 exe 빌드 지원

## 사용 기술

- Python 3.8
- CustomTkinter
- tkinter
- Pillow
- psutil
- PyInstaller
- com0com

## 프로젝트 구조

```text
main.py                    GUI 및 전체 작업 흐름
admin.py                   관리자 권한 확인/재실행
constants.py               경로, 포트, URL 등 상수
com0com_handler.py         com0com 설치/포트 생성/삭제/조회
config_writer.py           모아라인 INI 파일 읽기/쓰기/복원
moaline_detector.py        모아라인 플러스/상점 설치 감지
process_handler.py         모아라인 프로세스 종료/재시작
build_helper.py            PyInstaller 빌드 자동화
build_info.py              앱 버전 및 Release 날짜
version_info.txt           Windows exe 버전 리소스
requirements.txt           Python 의존성
build.bat                  Python 3.8 빌드 실행용 배치
PROGRAM_STUDY_GUIDE.md     개발/구조 학습 자료
DISTRIBUTION_SECURITY_GUIDE.md  배포 보안/SmartScreen 안내
```

## 모아라인 플러스 설정 방식

플러스 연동 시 `PRINT1=COM99` 대신 `PRNYN=1`, `PRINT1=선택` 형식을 사용합니다.

예시:

```ini
[linkage]
PRNYN=1
PRINT1=선택
POS1=COM16
MOA1=COM15
BaudRate1=9600
```

## 빌드 방법

Python 3.8 32-bit 설치 후 실행합니다.

```bat
build.bat
```

또는 직접 실행:

```powershell
%LOCALAPPDATA%\Programs\Python\Python38-32\python.exe build_helper.py
```

빌드 결과는 `dist/모아라인연동자동화.exe`에 생성됩니다.

## 배포 참고

생성된 exe는 코드 서명 인증서가 없으면 Windows SmartScreen 또는 브라우저 다운로드 경고가 표시될 수 있습니다.

외부 배포 시에는 Code Signing 인증서로 서명하는 것을 권장합니다. 자세한 내용은 `DISTRIBUTION_SECURITY_GUIDE.md`를 참고하세요.

