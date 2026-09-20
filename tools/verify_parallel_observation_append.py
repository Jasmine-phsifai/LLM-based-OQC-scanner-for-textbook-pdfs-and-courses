"""Exercise parallel public observation contexts on the selected filesystem."""
import argparse
import concurrent.futures,json,pathlib,tempfile
from ocrllm import observation_context
from ocrllm.observation_context import emit
parser = argparse.ArgumentParser()
parser.add_argument('--directory', required=True, help='Existing scratch directory on target filesystem')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='maintenance-observation-', dir=args.directory) as tmp:
 p=pathlib.Path(tmp)/'events.jsonl'
 def worker(n):
  with observation_context(path=p,lecture_id=str(n)):
   for i in range(200):emit('probe',task='ocr',sequence=i,payload='测量'*4000)
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(worker,range(8)))
 raw=p.read_bytes();rows=raw.splitlines();valid=[];invalid=0
 for r in rows:
  try:valid.append(json.loads(r))
  except:invalid+=1
 print(json.dumps(dict(expected=1600,lines=len(rows),valid=len(valid),invalid=invalid,unique=len(set((x['data']['lecture_id'],x['data']['sequence']) for x in valid)))),flush=True)

 assert len(valid) == 1600 and invalid == 0
 assert len({(x['data']['lecture_id'], x['data']['sequence']) for x in valid}) == 1600
