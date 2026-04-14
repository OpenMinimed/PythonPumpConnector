import sqlite3
import os

from history_data import HistoryData
from log_manager import LogManager
from history_reader import HistoryReader

class DatabaseManager:

    DB_PATH = "history.db"
    
    def __init__(self, hr:HistoryReader):
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

        # Check for sequences in DB that are outside device's range
        missing_outside = db_seqs - device_range
        if missing_outside:
            self.logger.warning(f"Some records in DB are no longer available on device: {sorted(missing_outside)}")

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
                records = self.hr.get_records_between(min_seq, max_seq)
                all_records.extend(records)
                self.logger.debug(f"Fetched {len(records)} records for range {min_seq}-{max_seq}")
                # Check for holes in this batch
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
