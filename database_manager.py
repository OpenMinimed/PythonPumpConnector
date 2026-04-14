import sqlite3
import os
import logging
from typing import List, Optional

from utils import add_submodule_to_path
add_submodule_to_path()

from history_data import HistoryData, HistoryEventType
from log_manager import LogManager
from history_reader import HistoryReader


class DatabaseManager:

    DB_PATH = "history.db"
    
    def __init__(self, hr: Optional[HistoryReader]):
        self.hr = hr
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self._create_db_if_not_exists()
        return

    def _create_db_if_not_exists(self):
        if not os.path.exists(self.DB_PATH):
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE history_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type INTEGER,
                    seq_number INTEGER UNIQUE,
                    relative_offset INTEGER,
                    raw_event_data_hex TEXT
                )
            ''')
            conn.commit()
            conn.close()

    def sync(self):
        """Sync the database with the device by fetching missing records."""
        self.logger.debug("Starting sync process")
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()

        # Get all sequence numbers in the database
        cursor.execute("SELECT seq_number FROM history_records ORDER BY seq_number")
        db_seqs = {row[0] for row in cursor.fetchall()}
        self.logger.debug(f"DB sequences count: {len(db_seqs)}, range: {min(db_seqs) if db_seqs else 'empty'} to {max(db_seqs) if db_seqs else 'empty'}")

        # Get the first and last records from the device
        try:
            first_record = self.hr.get_first_record()
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

        # Fetch records for each range
        all_records: list[HistoryData] = []
        for min_seq, max_seq in ranges:
            self.logger.debug(f"Fetching records from {min_seq} to {max_seq}")
            try:
             
                query_min = max(0, min_seq - 1)
                query_max = max_seq + 1
                records = self.hr.get_records_between(query_min, query_max)
                all_records.extend(records)
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

        self.logger.debug(f"Total records to store: {len(all_records)}")
        # Store the records (use INSERT OR IGNORE to handle any duplicates)
        stored_count = 0
        for record in all_records:
            cursor.execute('''
                INSERT OR IGNORE INTO history_records (event_type, seq_number, relative_offset, raw_event_data_hex)
                VALUES (?, ?, ?, ?)
            ''', (record.event_type.value, record.sequence_number, record.relative_offset, record.raw_data.hex()))
            stored_count += 1

        conn.commit()
        conn.close()
        self.logger.info(f"Synced {stored_count} records")
        return

    def get_all_db_records(self) -> List[HistoryData]:
        """Retrieve all records from the database."""
        self.logger.debug("Retrieving all records from DB")
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT event_type, seq_number, relative_offset, raw_event_data_hex
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
  

if __name__ == "__main__":
 
    LogManager.init(level=logging.DEBUG)

    # Load data from the database
    db_manager = DatabaseManager(None)
    parsed = db_manager.get_all_db_records()

    # Find reference time from NGP_REFERENCE_TIME events
    ref_time = None
    for record in parsed:
        if record.event_type == HistoryEventType.NGP_REFERENCE_TIME:
            ref_time = record.event_data.date_time
            break

    # Re-parse with reference time if found
    if ref_time:
        for record in parsed:
            record.parse(ref_time)

    types = []
    for record in parsed:
        print(record)
        if record.event_type.name not in types:
            types.append(record.event_type.name)

    print(f"parsed {len(parsed)} objects from database")
    print("types in the database:")
    for t in types:
        print(f" {t}")