import sqlite3
import os
from typing import List, Optional

from history.data import HistoryData
from utils.log_manager import LogManager
from history.reader import HistoryReader
from database.constants import DB_PATH

class DatabaseManager:
    
    def __init__(self, hr: Optional[HistoryReader]):
        self.hr = hr
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self._create_db_if_not_exists()
        if self.hr:
            self.hr.record_callback = self._store_record

        # We can end up fetching several thousand records in one go. This
        # takes several minutes and has a chance of screwing up (pump not
        # answering in time, problems writing to the database etc.), thus
        # wasting a lot of time. To avoid this situation, we divide large
        # transfers into smaller batches.
        #
        # Set this to `None` to disable batching.
        self.batch_size = 250

    def _store_record(self, record):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO history_records (event_type, seq_number, relative_offset, raw_data)
            VALUES (?, ?, ?, ?)
        ''', (record.event_type.value, record.sequence_number, record.relative_offset, record.raw_data.hex()))
        conn.commit()
        conn.close()

    def _create_db_if_not_exists(self):
        if not os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE history_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type INTEGER,
                    seq_number INTEGER UNIQUE,
                    relative_offset INTEGER,
                    raw_data TEXT
                )
            ''')
            conn.commit()
            conn.close()

    @staticmethod
    def _subdivide_ranges(ranges, batch_size):
        assert batch_size > 0
        result = []
        for min_seq, max_seq in ranges:
            assert min_seq <= max_seq
            for first in range(min_seq, max_seq + 1, batch_size):
                last = min(first + batch_size - 1, max_seq)
                result.append((first, last))
        return result

    def unsubscribe(self):
        pass

    def sync(self):
        """
        Sync the database with the device by fetching missing records.
        """

        self.logger.debug("Starting sync process")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get all sequence numbers in the database
        cursor.execute("SELECT seq_number FROM history_records ORDER BY seq_number")
        db_seqs = {row[0] for row in cursor.fetchall()}
        self.logger.debug(f"DB sequences count: {len(db_seqs)}, range: {min(db_seqs) if db_seqs else 'empty'} to {max(db_seqs) if db_seqs else 'empty'}")

        # Get the first and last records from the device
        try:
            self.logger.info("Fetching pump's oldest record")
            first_record = self.hr.get_first_record()
            self.logger.info("Fetching pump's latest record")
            last_record = self.hr.get_last_record()
            device_first = first_record.sequence_number
            device_last = last_record.sequence_number
            self.logger.debug(f"Device first seq: {device_first}, last seq: {device_last}")
        except Exception as e:
            self.logger.warning(f"Could not get first/last records: {e}")
            conn.close()
            return

        # Compute missing sequences within device's range
        device_range = set(range(device_first, device_last + 1))
        missing_in_range = sorted(device_range - db_seqs)
        self.logger.debug(f"Device has {len(device_range)} records, missing {len(missing_in_range)} in DB")

        if not missing_in_range:
            self.logger.info("Database is up to date")
            conn.close()
            return

        # Group missing sequences into contiguous ranges
        ranges = []
        if missing_in_range:
            start = missing_in_range[0]
            prev = start
            for seq in missing_in_range[1:]:
                if seq != prev + 1:
                    ranges.append((start, prev))
                    start = seq
                prev = seq
            ranges.append((start, prev))
        self.logger.debug(f"Identified {len(ranges)} contiguous missing ranges: {ranges}")

        # divide ranges into smaller batches before fetching actual records
        if self.batch_size is None:
            self.logger.debug("Skipping subdivision of ranges into batches")
            ranges_to_fetch = ranges
        else:
            self.logger.debug(f"Subdividing ranges into batches of size {self.batch_size}")
            ranges_to_fetch = self._subdivide_ranges(ranges, self.batch_size)

        self.logger.debug(f"Ranges to fetch: {ranges_to_fetch}")

        # Fetch records for each range
        for min_seq, max_seq in ranges_to_fetch:
            self.logger.debug(f"Fetching records from {min_seq} to {max_seq}")
            try:
             
                query_min = max(0, min_seq - 1)
                query_max = max_seq + 1
                records = self.hr.get_records_between(query_min, query_max)
                self.logger.debug(f"Fetched {len(records)} records for range {min_seq}-{max_seq} using query {query_min}-{query_max}")
             
                # Check for holes in this batch. The expected range is still the
                # inclusive set of sequence values we wanted from the DB.
                fetched_seqs = {r.sequence_number for r in records}
                expected = set(range(min_seq, max_seq + 1))
                if fetched_seqs != expected:
                    self.logger.warning(f"Holes in fetched data for range {min_seq}-{max_seq}: expected {len(expected)}, got {len(fetched_seqs)}")
            except Exception as e:
                self.logger.error(f"Failed to get records between {min_seq} and {max_seq}: {e}")
                continue

        conn.close()
        self.logger.info("Sync complete")
        return

    def get_all_db_records(self) -> List[HistoryData]:
        """
        Retrieve all records from the database.
        """

        self.logger.debug("Retrieving all records from DB")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT event_type, seq_number, relative_offset, raw_data
            FROM history_records
            ORDER BY seq_number
        ''')

        records = []
        for row in cursor.fetchall():
            event_type, seq_number, relative_offset, raw_hex = row
            raw_data = bytes.fromhex(raw_hex)
            record = HistoryData(raw_data, use_e2e=False)
            if record.parse():
                records.append(record)
            else:
                self.logger.error(f"Failed to parse record with seq {seq_number}")

        conn.close()
        self.logger.debug(f"Retrieved {len(records)} records from DB")
        return records