"""R4 preparation with explicit close-stamp normalization and full overnight checks."""
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from registry import grid, digest, atomic_json
from timestamps import normalized_opens


def prepare(data_dir,out):
    data_dir,out=Path(data_dir),Path(out)
    out.mkdir(parents=True,exist_ok=True)
    g=grid()
    evidence=json.loads((Path(__file__).parent/'DATA_PROVENANCE.json').read_text())
    prov=json.loads((data_dir/'provenance.json').read_text())
    dates=json.loads((data_dir/'dates.json').read_text())
    if (prov['source_commit']!=g['source_commit'] or
        prov['data_hash']!=evidence['mirror_data_hash'] or digest(prov['files'])!=prov['data_hash'] or
        set(dates)!=set(prov['files'])):
        raise ValueError('Raw data differs from the timestamp-audited mirror')
    arrays=[]
    for date in dates:
        raw=(data_dir/(date+'.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=prov['files'][date]:
            raise ValueError('Raw checksum mismatch: '+date)
        x=np.asarray(json.loads(raw),dtype=float)
        if x.size:arrays.append(x)
    a=np.concatenate(arrays)
    if a.ndim!=2 or a.shape[1]!=6 or not np.isfinite(a).all():
        raise ValueError('Invalid raw shape/values')
    frame=pd.DataFrame(a,columns=['raw_time','open','high','low','close','volume']).drop_duplicates()
    if frame.raw_time.duplicated().any():raise ValueError('Conflicting timestamps')
    if ((frame.high<frame[['open','low','close']].max(axis=1)) |
        (frame.low>frame[['open','high','close']].min(axis=1)) | (frame.volume<0)).any():
        raise ValueError('Invalid OHLCV')
    price=frame[['open','high','low','close']].to_numpy()
    if not np.isclose(price*4,np.round(price*4),rtol=0,atol=1e-8).all():
        raise ValueError('Off-tick raw prices')
    # This interpretation is frozen for this exact, empirically audited mirror.
    # Keep observation availability separate: its candle finishes at raw_time.
    opened=normalized_opens(frame.raw_time.to_numpy(),'close')
    frame.index=pd.Index(opened)
    frame=frame.sort_index()
    schedule=mcal.get_calendar('NYSE').schedule(start_date=dates[0],end_date=g['development_end'])
    et=ZoneInfo('America/New_York')
    rth=np.full((len(schedule),390,5),np.nan)
    overnight=np.full((len(schedule),3),np.nan)
    counts=[]
    normal=[]
    cash_minutes=[]
    for d,(day,row) in enumerate(schedule.iterrows()):
        start=row.market_open.tz_convert(et)
        end=row.market_close.tz_convert(et)
        end_minutes=(end.hour*60+end.minute)-570
        expected=np.arange(int(start.timestamp()),int(start.timestamp())+390*60,60,dtype=np.int64)
        positions=frame.index.get_indexer(expected)
        good=positions>=0
        rth[d,good]=frame.iloc[positions[good]][['open','high','low','close','volume']].to_numpy()
        prior=day.date()-timedelta(days=1)
        night=datetime(prior.year,prior.month,prior.day,18,tzinfo=et)
        night_times=np.arange(int(night.timestamp()),int(start.timestamp()),60,dtype=np.int64)
        npos=frame.index.get_indexer(night_times)
        missing=int((npos<0).sum())
        if missing==0:
            bars=frame.iloc[npos]
            volume=bars.volume.sum()
            if volume>0:
                overnight[d]=[bars.high.max(),bars.low.min(),
                              ((bars.high+bars.low+bars.close)/3*bars.volume).sum()/volume]
        normal.append((start.hour,start.minute,end.hour,end.minute)==(9,30,16,0))
        cash_minutes.append(end_minutes)
        counts.append({'date':str(day.date()),'rth_missing':int((~good[:end_minutes]).sum()),
                       'overnight_missing':missing})
    np.save(out/'rth.npy',rth)
    np.save(out/'overnight.npy',overnight)
    result={'status':'PREPARED_WITH_EMPIRICALLY_INFERRED_CLOSE_TIMESTAMPS',
            'timestamp_convention':'close','normalization_seconds':-60,
            'available_at':'normalized_open_timestamp + 60 seconds',
            'timestamp_evidence':'DATA_PROVENANCE.json',
            'uploader_explicitly_confirmed_timestamps':False,
            'source_commit':prov['source_commit'],'data_hash':prov['data_hash'],
            'dates':schedule.index.strftime('%Y-%m-%d').tolist(),'normal_session_mask':normal,
            'cash_session_minutes':cash_minutes,'quality':counts,
            'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/'rth.npy',out/'overnight.npy']},
            'study_grid_hash':digest(g),
            'limitations':evidence['limitations']}
    atomic_json(out/'prepared.json',result)
    print(json.dumps({'sessions':len(schedule),'normal_sessions':sum(normal),
                      'valid_overnight_rows':int(np.isfinite(overnight).all(axis=1).sum()),
                      'timestamp_convention':'close (empirically inferred)'},indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    prepare(a.data,a.out)
