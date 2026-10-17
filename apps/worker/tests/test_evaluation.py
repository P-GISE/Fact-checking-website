import pytest
from factlens.evaluation import Dataset, Run, fingerprint, score

LABELS=['CONFIRMED','REFUTED','INSUFFICIENT','REVIEW_REQUIRED','EXCLUDED']
def dataset():
 return Dataset.model_validate({'datasetId':'fixture','version':'1','kind':'synthetic','annotationVersion':'fixture-v1','claims':[{'id':str(i),'originId':'origin-'+str(i),'split':'test','label':label} for i,label in enumerate(LABELS)]})
def run(data,predictions):
 return Run.model_validate({'runId':'example','system':'B','datasetDigest':fingerprint(data),'modelVersion':'fixture','promptVersion':'fixture','ruleVersion':'fixture','predictions':predictions})
def prediction(i,label):return {'claimId':str(i),'status':'completed','verdict':label}

def test_perfect_five_class_result_is_explicitly_synthetic_not_research():
 d=dataset();r=run(d,[prediction(i,label) for i,label in enumerate(LABELS)])
 report=score(d,r,'test')
 assert report['metrics']['accuracy']==1 and report['metrics']['macroF1']==1
 assert report['dataset']['kind']=='synthetic' and report['researchValidation'] is False
 assert report['counts']=={'cases':5,'completed':5,'missing':0,'failed':0,'decisive':2,'wrongDecisive':0,'abstained':2}
 assert 'ClaimRecall' in report['notMeasured']

def test_missing_and_failed_predictions_stay_in_denominators():
 d=dataset();r=run(d,[prediction(0,'REFUTED'),prediction(2,'INSUFFICIENT'),{'claimId':'3','status':'failed','verdict':None},prediction(4,'EXCLUDED')])
 report=score(d,r,'test');m=report['metrics']
 # Only two of five correct. REFUTED has FP1/FN1 and zero TP; absent C/R have F1=0.
 assert m['accuracy']==.4 and m['macroF1']==.4
 assert m['completionRate']==.6 and m['abstentionRate']==.2
 assert m['falseVerdictRate']==.2 and m['decisiveErrorRate']==1
 assert report['counts']['missing']==1 and report['counts']['failed']==1
 assert report['confusionMatrix']['REFUTED']['MISSING']==1
 assert report['perClass']['REVIEW_REQUIRED']['fn']==1

def test_no_decisive_outputs_has_null_decisive_error_and_zero_false_verdict():
 d=dataset();report=score(d,run(d,[]),'test')
 assert report['metrics']['decisiveErrorRate'] is None
 assert report['metrics']['falseVerdictRate']==0
 assert report['metrics']['abstentionRate']==0
 assert report['metrics']['accuracy']==0 and report['counts']['missing']==5

@pytest.mark.parametrize('change',['leak','duplicate'])
def test_dataset_rejects_origin_split_leakage_and_duplicate_ids(change):
 raw=dataset().model_dump();extra=dict(raw['claims'][0])
 if change=='leak':extra.update(id='other',split='dev')
 raw['claims'].append(extra)
 with pytest.raises(ValueError):Dataset.model_validate(raw)

@pytest.mark.parametrize('change',['duplicate','unknown','wrong_digest','empty_split'])
def test_scoring_rejects_invalid_or_incomparable_runs(change):
 d=dataset();rows=[prediction(0,'CONFIRMED')];r=run(d,rows)
 if change=='duplicate':
  with pytest.raises(ValueError):run(d,rows+rows)
  return
 if change=='unknown':r=run(d,[prediction('unknown','CONFIRMED')])
 if change=='wrong_digest':r=r.model_copy(update={'datasetDigest':'0'*64})
 with pytest.raises(ValueError):score(d,r,'dev' if change=='empty_split' else 'test')

@pytest.mark.parametrize('row',[{'claimId':'0','status':'failed','verdict':'CONFIRMED'},{'claimId':'0','status':'completed','verdict':None}])
def test_failed_and_completed_output_contracts_cannot_be_mixed(row):
 d=dataset()
 with pytest.raises(ValueError):run(d,[row])

def test_only_selected_split_is_scored_but_entire_manifest_is_validated():
 raw=dataset().model_dump();raw['claims'].append({'id':'dev-only','originId':'separate-origin','split':'dev','label':'CONFIRMED'})
 d=Dataset.model_validate(raw)
 report=score(d,run(d,[prediction('dev-only','CONFIRMED'),prediction(0,'REFUTED')]),'test')
 assert report['counts']['cases']==5 and report['counts']['completed']==1
 assert report['metrics']['accuracy']==0

def test_cli_writes_machine_readable_report_and_rejects_invalid_input(tmp_path):
 import json,os,subprocess,sys
 from pathlib import Path
 d=dataset();r=run(d,[prediction(i,label) for i,label in enumerate(LABELS)])
 manifest=tmp_path/'gold.json';predictions=tmp_path/'run.json'
 manifest.write_text(d.model_dump_json());predictions.write_text(r.model_dump_json())
 env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
 command=[sys.executable,'-m','factlens.evaluation']
 result=subprocess.run(command+['score',str(manifest),str(predictions),'--split','test'],env=env,capture_output=True,text=True)
 assert result.returncode==0 and json.loads(result.stdout)['metrics']['accuracy']==1
 digest=subprocess.run(command+['fingerprint',str(manifest)],env=env,capture_output=True,text=True)
 assert digest.returncode==0 and digest.stdout.strip()==r.datasetDigest
 predictions.write_text('{"secret":"not-to-be-printed"}')
 invalid=subprocess.run(command+['score',str(manifest),str(predictions),'--split','test'],env=env,capture_output=True,text=True)
 assert invalid.returncode==2 and invalid.stdout==''
 assert invalid.stderr=='EVALUATION_INPUT_INVALID\n' and 'not-to-be-printed' not in invalid.stderr
 manifest.write_bytes(b' '*2097153)
 too_large=subprocess.run(command+['fingerprint',str(manifest)],env=env,capture_output=True,text=True)
 assert too_large.returncode==2 and too_large.stdout==''
