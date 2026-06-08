# 모니터링연동 드라이버 정책

모니터링연동은 무료 또는 오픈소스 드라이버/라이브러리만 사용합니다.

## 허용

- ENLYZE PortSniffer: MIT 라이선스 PoC 후보
- com0com: 기존 가상 COM 포트 용도
- Microsoft WDK 샘플: 무료 기술 참고 및 PoC 검토
- pyserial, pystray 등 무료 Python 라이브러리

## 제외

- HHD Software 등 유료 Serial Port Monitoring Control
- 유료 SDK, 유료 런타임, 유료 드라이버
- 정식 배포에 비용이 발생하는 드라이버 서명 절차

## 배포 원칙

- 테스트 POS에서는 PoC 목적으로 테스트모드/서명검사 완화를 허용할 수 있습니다.
- 드라이버 서명 비용이 필요하면 현장 배포는 중단하고 별도 승인 전까지 진행하지 않습니다.
- PoC 성공 전까지 드라이버 backend는 기본값으로 켜지지 않습니다.
