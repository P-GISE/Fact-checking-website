# 오프라인 판정 평가 도구 — v1

TASK-014의 **평가 준비 도구**다. 모델·검색·API·DB를 호출하지 않으며 자동으로 주장을 정답에 대응시키지 않는다. 예측을 정답 claimId에 수동 대응시킨 뒤 5종 판정 라벨만 채점한다. 이 도구 실행은 한국어 모델 성능·근거 신뢰성·연구 가설 검증이 아니다. 생산 Validator 규칙도 변경하지 않는다.

## 실행

저장소 루트에서 기존 Worker 가상환경을 사용한다.

```bash
PYTHONPATH=apps/worker .venv/bin/python -m factlens.evaluation fingerprint evaluation/example-dataset.json
PYTHONPATH=apps/worker .venv/bin/python -m factlens.evaluation score evaluation/example-dataset.json evaluation/example-run.json --split test > /tmp/factlens-evaluation.json
```

두 예시 파일은 **직접 작성한 합성 fixture**다. 실제 영상·제공자 출력·연구 데이터가 아니다. 의도적으로 틀린 확정, 누락, 실패를 포함한다. 출력은 5건 중 completed=3/missing=1/failed=1, accuracy=0.4, macroF1=0.4다. 이 숫자는 합성 산술 검증이며 제품 성능이 아니다. 출력에는 kind=synthetic, researchValidation=false가 명시된다.

성공은 종료코드 0과 JSON, 실패는 종료코드 2와 고정 EVALUATION_INPUT_INVALID 메시지다. 잘못된 파일 내용/예외 원문을 출력하지 않는다. 각 입력 파일은 2 MiB, 최대 10,000개 주장/예측으로 제한한다.

## 입력 계약

- Dataset: datasetId/version/kind(synthetic 또는 annotated)/annotationVersion/claims. 각 claim은 id/originId/split(dev 또는 test)/label. 추가 필드·빈 식별자·중복 id를 거부한다.
- 원본/변형/재인용 영상은 동일 originId로 사람이 묶는다. 같은 originId가 dev/test 양쪽에 있으면 전체 manifest를 거부한다. 다른 ID로 잘못 붙인 동일 원본을 자동 탐지하지는 못한다.
- Run: runId/system(A/B/C 또는 RULES)/datasetDigest/modelVersion/promptVersion/ruleVersion/predictions. 각 prediction은 claimId/status(completed 또는 failed)/verdict. completed는 5종 라벨이 필수이고 failed는 null이어야 한다.
- 중복 예측 ID·manifest 밖 ID·정규화한 전체 manifest SHA-256 불일치를 거부한다. manifest를 바꾸면 fingerprint를 다시 산출하고 예측 run의 대상 데이터도 재확인한다. 결과 파일의 해시만 바꿔 과거 실행을 새 실행처럼 사용하면 안 된다.
- 선택 split의 모든 gold 주장을 분모로 쓴다. 해당하지 않는 다른 split의 알려진 예측은 점수에서 제외한다. 선택 split이 비어 있으면 오류다.
- 버전·system·kind·원본 계열은 호출자가 선언한 메타데이터이며 검증된 학습/실행 이력으로 인증하지 않는다.

## 지표와 분모

| 지표 | 정의 |
|---|---|
| accuracy | 정답 판정 수 / 선택 split의 전체 gold 주장 수 |
| macroF1 | CONFIRMED/REFUTED/INSUFFICIENT/REVIEW_REQUIRED/EXCLUDED 고정 5종의 F1 평균. 분모0인 클래스 F1은 0 |
| completionRate | completed 예측 수 / 전체 gold 주장 수 |
| abstentionRate | completed 중 INSUFFICIENT 또는 REVIEW_REQUIRED 수 / 전체 gold 주장 수. EXCLUDED·실패는 포함하지 않음 |
| falseVerdictRate | 정답과 다른 CONFIRMED/REFUTED 수 / 전체 gold 주장 수 |
| decisiveErrorRate | 위 오판 수 / completed CONFIRMED/REFUTED 수. 확정 판정 0건이면 null |

누락/실패는 MISSING 혼동행렬 열과 해당 gold 클래스 FN에 포함하고 counts에서 별도 구분한다. 전부 실패하면 falseVerdictRate=0이어도 completionRate/accuracy=0이므로 단독 오판율로 성능을 주장하지 않는다. 지원 클래스가 적은 소규모 묶음에서는 고정 5종 Macro-F1이 낮아질 수 있어 perClass support/F1과 함께 해석한다.

Claim Recall, Evidence Precision@K, Evidence Validity, Cross-modal F1, 시간/비용은 **측정하지 않는다**. 사람이 대응시킨 claimId만으로 Claim Recall을 추정하지 않는다. 실패 샘플을 빼고 점수를 다시 산출하지 않는다.

## 실자료 연구 평가 전 준비

1. 사용 권한·외부 전송/보관 조건을 확인하고 원본 계열을 먼저 묶어 dev/test를 고정한다.
2. 정답 라벨 기준·복합 주장 분해·유보/제외·충돌 규칙과 독립 주석/불일치 조정 절차를 정한다. annotationVersion을 남긴다.
3. 같은 gold/split에서 A(텍스트), B(A+검색), C(최종 전체 시스템)를 비교하되 각 모델/프롬프트/규칙·검색 조건·실행 이력을 별도로 보존한다. 현재 C 전체 멀티모달 시스템은 미완료다.
4. 개발에 test 정답을 사용하지 않고, 실행 전에 목표 지표/분모·K·합격 기준·실패 처리와 비교/절제 실험 조건을 고정한다.
5. 원본/정답 대응 품질과 별도 누락 주장·근거·시각·시간/비용을 평가해 최종 연구 결과를 만든다. 이 실행기의 점수만으로 TASK-014를 완료하지 않는다.

## 실제 생산 규칙 회귀 — RULES

```bash
PYTHONPATH=apps/worker .venv/bin/python -m factlens.rule_regression evaluation/rules-fixture.json --split test > /tmp/factlens-rules-report.json
```

이 명령은 입력 Claim과 EvidenceDocument에 **생산 validate_evidence/decide를 실제 호출**해 예측을 만든다. 기존 score는 제공된 라벨을 채점하는 도구이고, 이 실행은 규칙 실행 자체를 검증한다. RULES 식별자는 연구 A/B/C와 별개이며 모델/STT/검색은 호출하지 않는다.

fixture는 synthetic만 허용한다. manifest의 모든 gold ID와 입력 case가 1:1이어야 하며 duplicate/extra/missing case는 거부한다. 기존 label manifest SHA-256 외에 전체 주장·전체 전사 context·원문/인용/발행 메타데이터를 포함한 fixture SHA-256, 실제 RULE_VERSION, validator/decision/contracts/evaluation/runner 소스 파일 SHA-256을 기록한다. 소스 해시는 파일 추적용이며 실행 환경/호출자가 변조할 수 없다는 인증은 아니다.

종료코드 0은 선택 split의 회귀 기대값 전부 일치, 1은 판정 불일치 또는 실행 실패가 포함된 JSON 보고서, 2는 잘못된 입력이다. 런타임 실패도 failed와 FN/전체 분모에 남기고 예외 원문은 출력하지 않는다. 잘못된 파일 내용도 고정 RULE_REGRESSION_INPUT_INVALID로 처리한다.

동봉 fixture 9개는 지지·반박·충돌·부족·제외·부정·인접 정정·부정 단위·하한 표현의 **직접 작성한 회귀 사례**다. 테스트에서 말하는 split=test는 회귀 자료 구분이며, 보지 않은 실자료 연구 평가나 모델 성능을 뜻하지 않는다. 정답과 기대값은 테스트 개발자가 지정했다.

v2 확정 비교는 한국/대한민국, 1900~2099년, 고용률%·실업률%·인구명의 제한된 등식 기록만 지원한다. 표시 주장과 전체 입력 전사, 근거 전체 텍스트가 이 정형 계약을 만족해야 한다. 지원 밖 발언은 검토/유보하며 일반 언어 이해가 아니다.

회귀의 발행 주체/날짜는 out-of-band 합성 입력이다. 정상 웹문서의 발행 메타데이터·인용 맥락/출처 진위를 검증했다고 주장하지 않는다. 현재 근거 전체 문맥 gate 때문에 일반 문서와 metadata를 포함한 실제 페이지는 대부분 확정되지 않는다. 이는 TASK-023의 지원 문서/맥락/provenance 계약 후속이다. Claim Recall·근거 품질/독립성·시각·STT/시간/비용은 계속 미측정이다.
