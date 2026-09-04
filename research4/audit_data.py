"""Read-only provenance and RTH/full-overnight coverage audit of the frozen mirror."""
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from registry import grid, digest, atomic_json


def audit(data, out):
    data, out = Path(data), Path(out)
    g = grid()
    prov = json.loads((data/'provenance.json').read_text())
    if prov['source_commit'] != g['source_commit']:
        raise ValueError('Unexpected raw source version')
    dates = json.loads((data/'dates.json').read_text())
    if set(dates) != set(prov['files']) or digest(prov['files']) != prov['data_hash']:
        raise ValueError('Raw provenance manifest mismatch')
    chunks = []
    for date in dates:
        path = data/(date+'.json')
        if hashlib.sha256(path.read_bytes()).hexdigest() != prov['files'][date]:
            raise ValueError('Raw hash mismatch: '+date)
        rows = np.asarray(json.loads(path.read_text()), dtype=np.float64)
        if rows.size:
            if rows.ndim != 2 or rows.shape[1] != 6:
                raise ValueError('Invalid raw dimensions: '+date)
            chunks.append(rows)
    raw = pd.DataFrame(np.concatenate(chunks), columns=['time','open','high','low','close','volume'])
    if not np.isfinite(raw.to_numpy()).all():
        raise ValueError('Nonfinite raw data')
    raw = raw.drop_duplicates().sort_values('time')
    if raw.time.duplicated().any() or (raw.time % 60 != 0).any():
        raise ValueError('Conflicting timestamps or non-minute data')
    if ((raw.high < raw[['open','close','low']].max(axis=1)) |
        (raw.low > raw[['open','close','high']].min(axis=1)) | (raw.volume < 0)).any():
        raise ValueError('Invalid OHLCV')
    off_tick = int((~np.isclose(raw[['open','high','low','close']].to_numpy()*4,
                             np.round(raw[['open','high','low','close']].to_numpy()*4), rtol=0, atol=1e-8)).any(axis=1).sum())
    index = pd.Index(raw.time.astype('int64'))
    schedule = mcal.get_calendar('NYSE').schedule(start_date=g['development_start'],end_date=g['development_end'])
    et = ZoneInfo('America/New_York')
    records = []
    for date, session in schedule.iterrows():
        opened = session.market_open.tz_convert(et)
        closed = session.market_close.tz_convert(et)
        if (opened.hour,opened.minute,closed.hour,closed.minute) != (9,30,16,0):
            continue
        # Audit the exact declared prior-calendar-day 18:00 to 09:29 interval.
        # A missing scheduled observation remains missing; no forward filling.
        prior_date = date.date()-timedelta(days=1)
        night = datetime(prior_date.year,prior_date.month,prior_date.day,18,tzinfo=et)
        start = int(opened.timestamp())
        overnight = np.arange(int(night.timestamp()),start,60,dtype=np.int64)
        rth = np.arange(start,start+390*60,60,dtype=np.int64)
        pos = index.get_indexer(overnight)
        rpos = index.get_indexer(rth)
        opening = rpos[:15]
        # Counterfactual only: if raw stamps denote closes, normalized opens
        # would be raw time minus 60 seconds. Do not change the raw dataset.
        close_night = index.get_indexer(overnight+60)
        close_rth = index.get_indexer(rth+60)
        changed_range = None
        if (opening>=0).all() and (close_rth[:15]>=0).all():
            first = raw.iloc[opening]
            second = raw.iloc[close_rth[:15]]
            changed_range = bool(first.high.max()!=second.high.max() or first.low.min()!=second.low.min())
        records.append({'date':str(date.date()),'opening15_missing':int((opening<0).sum()),
                        'rth_missing':int((rpos<0).sum()),'overnight_expected':len(overnight),
                        'overnight_missing':int((pos<0).sum()),
                        'if_close_stamped_overnight_missing':int((close_night<0).sum()),
                        'if_close_stamped_rth_missing':int((close_rth<0).sum()),
                        'opening15_extrema_differ_between_conventions':changed_range})
    result = {'status':'DATA_AUDIT_ONLY','source_commit':prov['source_commit'],'data_hash':prov['data_hash'],
              'raw_rows':len(raw),'off_tick_price_rows':off_tick,'normal_sessions':len(records),
              'complete_rth_sessions':sum(r['rth_missing']==0 for r in records),
              'complete_overnight_sessions':sum(r['overnight_missing']==0 for r in records),
              'if_close_stamped_complete_overnight_sessions':sum(r['if_close_stamped_overnight_missing']==0 for r in records),
              'if_close_stamped_complete_rth_sessions':sum(r['if_close_stamped_rth_missing']==0 for r in records),
              'sessions_with_changed_opening15_extrema':sum(r['opening15_extrema_differ_between_conventions'] is True for r in records),
              'timestamp_convention':'UNVERIFIED; close-stamped hypothesis requires source confirmation',
              'sessions':records,
              'limitations':['Public mirror: exchange provenance and roll treatment unverified',
                             'Coverage audit does not certify CME holiday schedules or executable MNQ fills',
                             'Missing active-trade bars must stop account replay, never become zero P&L']}
    atomic_json(out/'data_audit.json',result)
    return result


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=audit(a.data,a.out)
    print(json.dumps({k:v for k,v in result.items() if k not in ['sessions','limitations']},indent=2))
