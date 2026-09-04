from datetime import datetime
from zoneinfo import ZoneInfo
import unittest
import numpy as np
from timestamps import normalized_opens, available_at


class TimestampTests(unittest.TestCase):
    def test_close_stamped_opening_range_and_availability(self):
        z=ZoneInfo('America/New_York')
        first=int(datetime(2025,1,2,9,31,tzinfo=z).timestamp())
        raw=np.arange(first,first+15*60,60)
        opens=normalized_opens(raw,'close')
        self.assertEqual(datetime.fromtimestamp(opens[0],z).strftime('%H:%M'),'09:30')
        self.assertEqual(datetime.fromtimestamp(opens[-1],z).strftime('%H:%M'),'09:44')
        self.assertEqual(datetime.fromtimestamp(available_at(raw,'close')[-1],z).strftime('%H:%M'),'09:45')
        np.testing.assert_array_equal(raw,np.arange(first,first+15*60,60))

    def test_utc_shift_preserves_dst_offsets(self):
        z=ZoneInfo('America/New_York')
        for month,day in [(1,2),(6,3)]:
            raw=int(datetime(2025,month,day,18,1,tzinfo=z).timestamp())
            opened=datetime.fromtimestamp(int(normalized_opens([raw],'close')[0]),z)
            self.assertEqual((opened.hour,opened.minute),(18,0))

    def test_no_unstated_heuristic_or_invalid_timestamp(self):
        for stamps,convention in [([60],'unknown'),([61],'close'),([np.nan],'close')]:
            with self.assertRaises(ValueError):normalized_opens(stamps,convention)

    def test_open_stamped_source_remains_unshifted(self):
        np.testing.assert_array_equal(normalized_opens([60,120],'open'),[60,120])
        np.testing.assert_array_equal(available_at([60,120],'open'),[120,180])


if __name__=='__main__':unittest.main()
