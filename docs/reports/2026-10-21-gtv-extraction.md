# GTV 뉴스 원문 후보 생성 수정 — 2026-10-21

## 결과와 범위

같은 저장 전사와 실제 gpt-4.1-mini에서 기존 프롬프트v3는 후보5개가 모두 원문 검증에 탈락했다. v4는 유효2개를 남겼으며 실제 Brave 검색·출처 검증·보고서 반환까지 완료했다. GTV 두 주장은 유효 근거0으로 INSUFFICIENT다. 추출 성공을 사실 확인으로 해석하지 않는다.

이 시험은 기존 전사를 재생하며 ASR·화면 관측을 실행하지 않았다. 격리 runner의 소유 음성 파일은 시험 등록/정리 용도이며 GTV 영상 업로드/전사 재검증이 아니다. 공개 회원 브라우저 전체 흐름도 이번에는 재실행하지 않았다. 기존 전사/권리/원본 정보는 [모델 비교 보고서](2026-10-21-transcription-model-comparison.md), 과거 공개 회원 검증은 [공개 실검증 보고서](2026-10-21-public-live-verification.md)를 따른다. 실행 원문/비용/정리는 [JSON](2026-10-21-gtv-extraction.json)에 보존한다.

## 원인과 수정

비수치 사건을 정형 수치 필드에 억지로 맞추며 quote에 없는 개최 여부/진행 여부/협력 의지 metric과 다른 구간의 subject를 생성했다. quote 자체와 segment_ids는 맞아도 literal 검증에서 실패했다.

Candidate의 subject/period/metric/value/unit 스키마 설명에 원문 연속 문자열 또는 null 규칙을 넣고, 사건은 quote로 유지하면서 없는 측정 항목/숫자/단위를 채우지 않도록 지시했다. claimPromptVersion은 claim-structured-v4다. 모델 지시가 모든 출력을 보장하지 않으므로 기존 런타임 검증은 그대로 유지한다.

claimValidationVersion=literal-candidates-v2, quote/인접 segment/숫자 경계/전체 context/시간 검사, 일부 무효만 제외하고 전부 무효는 실패시키는 동작을 보존했다. invalid 필드를 사후 null로 고치지 않는다. 모델·자격·최대5개·운영 $0.20/건/$20/월과 시간 보정0.25초 한도도 변경하지 않았다.

## 실제 호출 결과

| 시험 | 결과 | 외부 호출 | 보수적 micros |
|---|---|---:|---:|
| 기존v3 GTV 추출 |5개 모두 무효, PROVIDER_RESPONSE_INVALID|1|1088|
| v4 GTV 추출만 |유효2개, 무효3개 제외|1|1380|
| v4 안전 대담 추출만 |모두 무효로 실패, 미해결|1|970|
| v4 실업률2.8 추출만 |대상 한국/지표 실업률/2.8/% 유지|1|640|
| v4 실업률2.9 추출만 |대상 한국/지표 실업률/2.9/% 유지|1|639|
| v4 GTV 검색·보고서 |주장2/검색 근거6/유효0, INSUFFICIENT2|9|22965|
| v4 실업률2.8 검색·보고서 |CONFIRMED1/유효2|3|6410|
| v4 실업률2.9 검색·보고서 |REFUTED1/유효2|3|7577|

합계8개 시험/20회 호출, unknownUsageCalls=0, **41669micros = $0.041669**. 공개 요금 기반 보수적 비용이며 결제 명세서 확정액은 아니다. 시험별 한도를 추출30000micros/검색 보고서100000micros로 낮추었고 기존 월 한도/예약을 사용했다. 모든 시험 filesRemoved/jobTombstoned/mediaTombstoned/usageRetained=true. ubuntu 소유·비심볼릭 링크인 이번 원격 스테이징을 확인해 제거했고 부재도 확인했다. 사용자의 기존 업로드는 조회하지 않았다.

GTV 유효 quote는 “2024년 제2회 경기북부 미래비전 포럼이 열렸습니다.”와 “포럼은 대한민국의 신성장 동력 경기북부, 함께 그리다라는 주제로 열렸습니다.”다. 원문 밖 metric/subject를 만든 나머지 후보는 계속 제외했다. 안전 대담에는 여전히 원문에 없는 metric과 quote 밖 기간이 나와 실패했다. 확률적 모델의 단일 개발 진단이며 일반 정확도 점수가 아니다. 실업률 유효2개는 같은 조사 원자료에 기반하므로 독립 출처2개라고 하지 않는다.

## 코드 검증과 배포 상태

- 원래5개 무효 후보가 계속 실패하는 고정 재생 회귀, null metric 사건의 quote/시간/인접 정정 문맥 보존 회귀를 추가했다. 이 경계 테스트는 기존 구현에서도 통과하며 실제 v3 실패 재현과 구분한다.
- 관련 Worker4개 파일:187 passed,2 skipped. 독립 리뷰:32 passed,29 deselected,발견 사항 없음/APPROVE.
- Iron Laws 해당 파일 check:6개 기존 REVIEW(타입/예외 처리/URL/HTTP클라이언트), 새 차단 결함 없음. 별도 보안 침투 테스트나 verify_patch를 실행했다고 하지 않는다.
- 전체 Linux [Actions39488460762](https://github.com/P-GISE/Fact-checking-website/actions/runs/39488460762): API97/Worker421·타입/빌드·배포 스크립트 회귀 통과, verify/deploy 모두 success. work 코드 커밋9b771e0dd3f65a378e35346d28bb98ee83ebf19f를 AWS에 자동 배포했다. main은 변경하지 않았다.
- 배포 후 서버 git HEAD와 실행 Worker 모듈의 LF SHA256(2b2630d39ad40c13ede1ecccab1bd2406113fbcd593505381364486251c55390)이 해당 코드와 일치한다. 환경 파일0600, 실제 worker openai_brave/200000micros/건·20000000micros/월을 확인했다. 내부 loopback과 외부 HTTPS curl health는 ready다. 컨테이너 urllib 기본 요청은403으로 실패했고 외부 curl 및 배포 health 성공과 구분해 기록한다.
- 문서 후속 커밋은 실행 JSON에서 수집 원문 전체 대신 출처 URL/관계/유효성/사유/원출처 감사 요약만 유지한다. 동작 코드는 변경하지 않으며 문서 전용 [skip ci] 게시로 불필요한 재배포를 생략한다.
- 운영 모델 whisper-1/gpt-4.1-mini/Brave와 openai_brave 유지. providerConfigured:false는 고정 health 응답으로 AI 비활성 증거가 아니다.

## 남은 작업

안전 대담 및 다른 뉴스의 전부 무효 후보 개선·재현성, 한국어 전사의 단위/연도/문장 누락과 잡음/힌트 혼입, 구간 정렬·독립 청취 정답·별도 고정 평가가 남는다. 새 전사 모델은 비교만 승인됐으며 운영 교체하지 않았다. 일반 의미/복잡한 표/출처 독립성/전체 영상 진위 판정과 사용자가 미룬 UI·추가 권한/운영 정책도 미완료다.

