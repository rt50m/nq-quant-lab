"""Reproducible preparation report. Deliberately cannot launch a strategy search."""
from pathlib import Path
import argparse
from registry import preparation_manifest, atomic_json
from audit_data import audit
from data import prepare as normalize_data


def prepare(data, out):
    out=Path(out)
    manifest=preparation_manifest(out)
    quality=audit(data,out)
    normalize_data(data,out/'normalized')
    report={'status':'PREPARATION_ONLY_USE_FULL_WORKFLOW','models':manifest['model_count'],
            'raw_combinations':manifest['raw_combinations'],'completed_backtests':0,
            'blockers':['This audit does not execute the full search or certify its results',
                        'Use the full workflow verification and executable manifest'],
            'timestamp_policy':'Close-stamped, empirically inferred from original CSV; uploader has not explicitly confirmed',
            'grid_hash':manifest['grid_hash'],'data_hash':quality['data_hash']}
    atomic_json(out/'readiness.json',report)
    summary=f'''# Research 004 preparation only

**Preparation audit only. Use run_research_004.yml for the full search. No strategy search was run by this audit.**

- Selected models: {report['models']} (model 31 has ten entry families).
- Draft raw parameter products: {report['raw_combinations']:,}; not deduplicated executable counts.
- Backtests completed: 0.
- Complete RTH sessions under the existing timestamp assumption: {quality['complete_rth_sessions']} / {quality['normal_sessions']}.
- Complete full-overnight sessions under that assumption: {quality['complete_overnight_sessions']}.
- Under the alternative close-stamped hypothesis: {quality['if_close_stamped_complete_overnight_sessions']} complete overnight sessions.
- Sessions whose 15-minute opening extrema differ between conventions: {quality['sessions_with_changed_opening15_extrema']}.

The original Kaggle CSV has now been compared against every cached mirror row: all 1,048,462 timestamp/OHLCV rows match exactly. Its 764 RTH VWAP initializations all occur at 09:31 ET. R4 now explicitly normalizes this frozen dataset as close-stamped: raw time minus 60 seconds for bar-open indexing, with availability still at the raw timestamp. This is strongly supported empirical inference, not an explicit uploader declaration. Raw data and earlier research remain unchanged.

Normalized RTH and full-overnight feature arrays are included under normalized/. The full implementation and manifest are supplied separately through run_research_004.yml. A successful preparation job does not certify that the research is executable.
'''
    (out/'summary.md').write_text(summary,encoding='utf-8')
    print(summary)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    prepare(a.data,a.out)
