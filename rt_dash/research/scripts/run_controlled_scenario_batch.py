#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from rt_dash.policies import PolicyName
from scripts.run_journal_strengthening_study import SCENARIOS, CORE_POLICIES, _run_controlled_one

p=argparse.ArgumentParser()
p.add_argument('scenario', choices=SCENARIOS)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--seeds', type=int, default=30)
p.add_argument('--seed-start', type=int, default=0)
p.add_argument('--duration', type=int, default=60000)
p.add_argument('--quantum', type=int, default=10)
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
rows=[]; trans=[]; jobs=[]
loads=SCENARIOS[a.scenario]
for load in loads:
  for seed in range(a.seed_start, a.seed_start + a.seeds):
    for policy in PolicyName:
      save=seed==0 and load==loads[0] and policy in CORE_POLICIES
      row,t,j=_run_controlled_one((a.scenario,load,seed,policy.value,a.duration,a.quantum,save))
      rows.append(row); trans.extend(t); jobs.extend(j)
print(f'{a.scenario}: {len(rows)} runs')
pd.DataFrame(rows).to_csv(a.output/f'controlled_{a.scenario}_{a.seed_start}_{a.seed_start+a.seeds-1}.csv',index=False)
pd.DataFrame(trans).to_csv(a.output/f'transitions_{a.scenario}_{a.seed_start}_{a.seed_start+a.seeds-1}.csv',index=False)
pd.DataFrame(jobs).to_csv(a.output/f'jobs_{a.scenario}_{a.seed_start}_{a.seed_start+a.seeds-1}.csv',index=False)
