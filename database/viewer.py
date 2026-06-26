import sqlite3
import datetime as dt
import logging
from collections import Counter

from history.data import HistoryData, HistoryEventType
from utils.log_manager import LogManager
from database.manager import DB_PATH


class DBViewer:

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.records: list[HistoryData] = []

    def load_records(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT event_type, seq_number, relative_offset, raw_data
            FROM history_records
            ORDER BY seq_number
        ''')
        rows = cursor.fetchall()
        conn.close()

        for event_type, seq_number, relative_offset, raw_hex in rows:
            raw_data = bytes.fromhex(raw_hex)
            record = HistoryData(raw_data, use_e2e=False)
            if record.parse():
                self.records.append(record)

        self._compute_abs_times()

    def _compute_abs_times(self):
        current_ref = None
        for record in self.records:
            if record.event_type == HistoryEventType.NGP_REFERENCE_TIME:
                current_ref = record.event_data.date_time
                record._HistoryData__abs_time = current_ref
            elif current_ref is not None and record.relative_offset is not None:
                record._HistoryData__abs_time = current_ref + dt.timedelta(seconds=record.relative_offset)

    def print_summary(self):
        types = []
        for record in self.records:
            print(record)
            if record.event_type.name not in types:
                types.append(record.event_type.name)

        print(f"\nparsed {len(self.records)} objects from database")
        print("types in the database:")
        for t in types:
            print(f"  {t}")

    def plot_daily_counts(self, output_path="history_graph.png"):
        dates = []
        for record in self.records:
            abs_time = record._HistoryData__abs_time
            if abs_time is not None:
                dates.append(abs_time.date())

        if not dates:
            logging.warning("No records with absolute times to plot")
            return

        counter = Counter(dates)
        sorted_days = sorted(counter.items())

        if not sorted_days:
            logging.warning("No records with dates to plot")
            return

        import matplotlib.pyplot as plt

        days = [d.strftime("%Y-%m-%d") for d, _ in sorted_days]
        counts = [c for _, c in sorted_days]

        plt.figure(figsize=(12, 6))
        plt.bar(days, counts)
        plt.xlabel("Date")
        plt.ylabel("Number of datapoints")
        plt.title("Daily History Record Counts")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()
        print(f"Daily counts graph saved to {output_path}")

    def query_gaps(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            WITH gaps AS (
                SELECT
                    LAG(seq_number) OVER (ORDER BY seq_number) AS prev_seq,
                    seq_number
                FROM history_records
            )
            SELECT
                prev_seq + 1 AS gap_start,
                seq_number - 1 AS gap_end,
                seq_number - prev_seq - 1 AS missing_count
            FROM gaps
            WHERE seq_number > prev_seq + 1
            ORDER BY gap_start
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("No gaps found - all sequence numbers are contiguous")
            return rows

        total_missing = sum(r[2] for r in rows)
        print(f"Found {len(rows)} gap(s), {total_missing} total missing records:")
        for gap_start, gap_end, count in rows:
            print(f"  {gap_start} - {gap_end}: {count} missing")
        return rows


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from utils.os_utils import add_submodule_to_path
    add_submodule_to_path()

    LogManager.init(level=logging.DEBUG)

    viewer = DBViewer()
    viewer.load_records()
    viewer.print_summary()
    viewer.query_gaps()
    viewer.plot_daily_counts()
