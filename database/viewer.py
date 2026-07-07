import sqlite3
import datetime as dt
import os
import logging
from collections import Counter
from tqdm import tqdm
import matplotlib.pyplot as plt

from history.data import HistoryData, HistoryEventType
from utils.log_manager import LogManager
from database.constants import DB_PATH


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

        for event_type, seq_number, relative_offset, raw_hex in tqdm(rows):
            raw_data = bytes.fromhex(raw_hex)
            record = HistoryData(raw_data, use_e2e=False)
            record.abs_time = None
            if record.parse():
                self.records.append(record)

        self._compute_abs_times()

    def _compute_abs_times(self):
        current_ref = None
        for record in self.records:
            if record.event_type == HistoryEventType.NGP_REFERENCE_TIME:
                current_ref = record.event_data.date_time
                record.abs_time = current_ref
            elif current_ref is not None and record.relative_offset is not None:
                record.abs_time = current_ref + dt.timedelta(seconds=record.relative_offset)

    def print_summary(self):
        types = []
        for record in self.records:
            # print(record)
            if record.event_type.name not in types:
                types.append(record.event_type.name)

        print(f"\nparsed {len(self.records)} objects from database")
        print("\ntypes in the database:")
        for t in types:
            print(f"\t{t}")
        return

    def plot_daily_counts(self, output_path="history_graph.png"):
        weeks = []
        for record in self.records:
            abs_time = record.abs_time
            if abs_time is not None:
                iso = abs_time.isocalendar()
                weeks.append((iso[0], iso[1]))

        if not weeks:
            logging.warning("No records with absolute times to plot")
            return

        counter = Counter(weeks)
        sorted_weeks = sorted(counter.items())

        if not sorted_weeks:
            logging.warning("No records with dates to plot")
            return

        labels = [f"{w[0]}-W{w[1]:02d}" for w, _ in sorted_weeks]
        counts = [c for _, c in sorted_weeks]

        plt.figure(figsize=(12, 6))
        plt.bar(range(len(labels)), counts)
        plt.xlabel("Week")
        plt.ylabel("Number of datapoints")
        plt.title("Weekly History Record Counts")
        plt.xticks(range(len(labels)), labels, rotation=45, ha="right")
        plt.tight_layout()
        output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), output_path))
        plt.savefig(output_path)
        plt.close()
        print(f"Weekly counts graph saved to {output_path}")

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
            print("\nno gaps found - all sequence numbers are contiguous")
            return rows

        total_missing = sum(r[2] for r in rows)
        print(f"\nfound {len(rows)} gap(s), {total_missing} total missing records:")
        for gap_start, gap_end, count in rows:
            print(f"\t{gap_start} - {gap_end}: {count} missing")
        return rows


if __name__ == "__main__":

    from utils.os_utils import add_submodule_to_path
    add_submodule_to_path()

    LogManager.init(level=logging.INFO)

    viewer = DBViewer()
    viewer.load_records()
    viewer.print_summary()
    viewer.query_gaps()
    viewer.plot_daily_counts()
