"""Reproducible preparation report. Deliberately cannot launch a strategy search."""
from pathlib import Path
import argparse
from registry import preparation_manifest, atomic_json
from audit_data import audit


def prepare(data, out):
    out=Path(out)
    manifest=preparation_manifest(out)
    quality=audit(data,out)
    report={'status':'NOT_READY_FOR_BACKTEST','models':manifest['model_count'],
            'raw_combinations':manifest['raw_combinations'],'completed_backtests':0,
            'blockers':['Timestamp convention is not verified by the data source',
                        '31 model implementations and execution-policy validation remain pending',
                        'Executable duplicate registry and runtime estimate remain pending'],
            'grid_hash':manifest['grid_hash'],'data_hash':quality['data_hash']}
    atomic_json(out/'readiness.json',report)
    summary=f'''# Research 004 preparation only

**NOT READY FOR BACKTEST. No strategy search was run.**

- Selected models: {report['models']} (model 31 has ten entry families).
- Draft raw parameter products: {report['raw_combinations']:,}; not deduplicated executable counts.
- Backtests completed: 0.
- Complete RTH sessions under the existing timestamp assumption: {quality['complete_rth_sessions']} / {quality['normal_sessions']}.
- Complete full-overnight sessions under that assumption: {quality['complete_overnight_sessions']}.
- Under the alternative close-stamped hypothesis: {quality['if_close_stamped_complete_overnight_sessions']} complete overnight sessions.
- Sessions whose 15-minute opening extrema differ between conventions: {quality['sessions_with_changed_opening15_extrema']}.

The alternative timestamp interpretation is a diagnostic, not an authorized correction or a performance result. Confirm original feed bar labeling before freezing opening windows. Model implementations, execution validation and semantic deduplication remain pending. A successful preparation job does not certify that the research is executable.
'''
    (out/'summary.md').write_text(summary,encoding='utf-8')
    print(summary)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    prepare(a.data,a.out)
