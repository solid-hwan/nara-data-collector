# 외부 라이브러리와 공식 명세 고지

나라장터 데이터 MCP의 새 구현은 MIT입니다. 아래 외부 패키지는 각자의 저작권과 라이선스를 유지합니다. 배포 ZIP은 의존성 코드·가상환경을 포함하지 않으며 고정 버전 설치 목록과 고지 사본을 포함합니다.

| 패키지 | 용도 | 버전 | 고지 |
|---|---|---|---|
| openpyxl | 샘플·저장자료 XLSX 출력 | 3.1.5 | [MIT 고지](docs/licenses/openpyxl-3.1.5.dist-info/LICENCE.rst) |
| et_xmlfile | openpyxl XML 기록 의존성 | 2.0.0 | [MIT](docs/licenses/et_xmlfile-2.0.0.dist-info/LICENCE.rst), [Python 고지](docs/licenses/et_xmlfile-2.0.0.dist-info/LICENCE.python) |
| setuptools | 설치 빌드 | 80.9.0 | [MIT](docs/licenses/setuptools-80.9.0.dist-info/licenses/LICENSE) |
| wheel | 설치 빌드 | 0.45.1 | [MIT](docs/licenses/wheel-0.45.1.dist-info/LICENSE.txt) |

빌드 도구에 포함된 vendored 패키지의 고지도 [고지 목록과 SHA-256](docs/licenses/manifest.json)에 원문으로 보존합니다. 런타임의 전이 의존성은 et_xmlfile이며, Python 표준 라이브러리와 설치된 Python 자체는 배포하지 않습니다.

서비스·오퍼레이션·파라미터·필드의 기술 식별자는 조달청이 공공데이터포털에서 공개한 명세를 기준으로 정리했습니다. 공식 문서 본문이나 기존 외부 프로젝트의 코드·문서·프로필·테스트를 가져오지 않았습니다. 데이터 사용은 해당 [공식 서비스 안내](docs/coverage.md)의 조건을 따릅니다. 새 제품의 MIT 고지가 공식 데이터의 출처 표시를 대신하지 않습니다.

MCP 통신은 [2025-11-25 stdio 규격](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [도구 규격](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)을 바탕으로 직접 작성한 작은 서버입니다. SDK 코드를 재배포하지 않습니다. 이 버전은 초기화 방식의 stdio만 제공하며 새로운 프로토콜의 HTTP·작업 확장 지원을 주장하지 않습니다.

기존 KONEPS_sionlab 공개 이력은 v0.3.1 태그로 보존합니다. 이전 기여자의 MIT 고지는 docs/licenses/KONEPS-v0.3.1-LICENSE에 그대로 보관합니다. 새 패키지는 기존 구현을 병합한 호환판이 아닙니다.
