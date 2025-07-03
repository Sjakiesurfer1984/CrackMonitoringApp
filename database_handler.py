import sqlite3
import pandas as pd
import logging
import os
from typing import Optional, List

# Constants
DB_PATH = os.path.join(os.path.dirname(__file__), "sensor_data.db")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        logger.info(f"Database path set to: {self.db_path}")

    def _connect(self):
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error(f"❌ Failed to connect to DB: {e}")
            raise

    def _table_exists(self, conn: sqlite3.Connection) -> bool:
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_values';"
        try:
            exists = bool(conn.execute(query).fetchone())
            logger.debug(f"✅ Table exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"❌ Error checking table existence: {e}")
            return False


    def save_to_db(self, df: pd.DataFrame) -> None:
        if df.empty:
            logger.warning("⚠️ Attempted to save empty DataFrame to DB.")
            return

        # rename the date/time column to easier to type and handle datetime column.
        df.rename(columns={"Date/time": "datetime"}, inplace=True)
        # convert to pandas datetime object.
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", dayfirst=True)
        df["datetime"] = df["datetime"].dt.floor("min")

        # drop any NaN's
        df.dropna(subset=["datetime"], inplace=True)

        with self._connect() as conn:
            try:
                # check whether a table called sensor_values exists
                if self._table_exists(conn):
                    logger.info("📥 Checking for existing rows in DB...")
                    # fetch existing timestamps
                    existing = pd.read_sql_query("SELECT datetime FROM sensor_values", conn, parse_dates=["datetime"])
                    existing["datetime"] = existing["datetime"].dt.floor("min")
                    existing_set = set(existing["datetime"].dropna())

                    # identify overlapping rows
                    df_overlap = df[df["datetime"].isin(existing_set)]
                    df_new = df[~df["datetime"].isin(existing_set)]

                    # delete overlapping rows from the DB before insert
                    if not df_overlap.empty:
                        placeholders = ', '.join(['?'] * len(df_overlap))
                        conn.execute(f"DELETE FROM sensor_values WHERE datetime IN ({placeholders})", tuple(df_overlap["datetime"]))
                        logger.info(f"🧹 Deleted {len(df_overlap)} existing rows to update with new data.")

                    # match columns
                    db_cols = pd.read_sql_query("PRAGMA table_info(sensor_values);", conn)["name"].tolist()
                    df = df[[col for col in df.columns if col in db_cols]]

                    # insert updated + new rows
                    df.to_sql("sensor_values", conn, if_exists="append", index=False)
                    logger.info(f"✅ Inserted {len(df)} rows (new + updated)")

                else:
                    df.to_sql("sensor_values", conn, if_exists="replace", index=False)
                    logger.info("📦 Created new table and inserted all data")

            except Exception as e:
                logger.error(f"❌ Failed during DB insert: {e}")






    # def save_to_db(self, df: pd.DataFrame) -> None:
    #     if df.empty:
    #         logger.warning("⚠️ Attempted to save empty DataFrame to DB.")
    #         return

    #     # rename the date/time column to easier to type and handle datetime column. 
    #     df.rename(columns={"Date/time": "datetime"}, inplace=True)
    #     # convert to pandas datatime object. 
    #     df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", dayfirst=True)
    #     df["datetime"] = df["datetime"].dt.floor("min")
        

    #     # drop any NaN's
    #     df.dropna(subset=["datetime"], inplace=True)

    #     with self._connect() as conn:
    #         try:
    #             # check whether a table called sensor_values exists
    #             if self._table_exists(conn):
    #                 logger.info("📥 Checking for existing rows in DB...")
    #                 # use the built in pandas read_sql_query to: 
    #                 # grab all timestamps already saved in the DB.
    #                 # Converts them into a set for fast membership checking.
    #                 existing = pd.read_sql_query("SELECT datetime FROM sensor_values", conn, parse_dates=["datetime"])
    #                 existing["datetime"] = existing["datetime"].dt.floor("min")
    #                 existing_set = set(existing["datetime"].dropna())
    #                 # Filter out rows that already exist
    #                 # It compares the datetime column of the uploaded data against the existing timestamps in the DB.
    #                 # Keeps only those rows not already in the DB.
    #                 df_filtered = df[~df["datetime"].isin(existing_set)]
    #                 df_skipped = df[df["datetime"].isin(existing_set)]
    #                 logger.info(f"🧮 {len(df_filtered)} new rows (after removing duplicates)")
    #                 logger.info(f"\n🧮 {len(df_skipped)} skipped rows, being:\n{df_skipped}")
                    
    #                 logger.debug(f"Sample of incoming datetimes:\n{df['datetime'].head()}")
    #                 logger.debug(f"Sample of DB datetimes:\n{existing.head()}")

    #                 # Ensure columns match the DB table schema
    #                 db_cols = pd.read_sql_query("PRAGMA table_info(sensor_values);", conn)["name"].tolist()
    #                 df_filtered = df_filtered[[col for col in df_filtered.columns if col in db_cols]]

    #                 if not df_filtered.empty:
    #                     df_filtered.to_sql("sensor_values", conn, if_exists="append", index=False)
    #                     logger.info("✅ New data appended to DB")
    #                 else:
    #                     logger.info("ℹ️ All rows already exist in DB or no matching columns. Nothing to add.")
    #             else:
    #                 df.to_sql("sensor_values", conn, if_exists="replace", index=False)
    #                 logger.info("📦 Created new table and inserted all data")
    #         except Exception as e:
    #             logger.error(f"❌ Failed during DB insert: {e}")

    def query_data(self, start_date: str, end_date: str, selected_columns: Optional[List[str]] = None) -> pd.DataFrame:
        with self._connect() as conn:
            if not self._table_exists(conn):
                logger.warning("⚠️ Table 'sensor_values' does not exist.")
                return pd.DataFrame()

            try:
                all_cols = pd.read_sql_query("PRAGMA table_info(sensor_values);", conn)["name"].tolist()
                if selected_columns:
                    valid_cols = ["datetime"] + [col for col in selected_columns if col in all_cols and col != "datetime"]
                else:
                    valid_cols = all_cols

                if not valid_cols:
                    logger.warning("⚠️ No valid columns to query.")
                    return pd.DataFrame()

                select_clause = ", ".join([f'"{col}"' for col in valid_cols])
                query = f"""
                    SELECT {select_clause}
                    FROM sensor_values
                    WHERE datetime BETWEEN ? AND ?
                    ORDER BY datetime;
                """
                df = pd.read_sql_query(query, conn, params=(start_date, end_date))
                df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
                logger.info(f"📤 Queried {len(df)} rows from DB")
                return df
            except Exception as e:
                logger.error(f"❌ Failed to query data: {e}")
                return pd.DataFrame()

    def load_all_data(self) -> pd.DataFrame:
        with self._connect() as conn:
            if not self._table_exists(conn):
                logger.warning("📭 No data found in DB (table missing).")
                return pd.DataFrame()

            try:
                df = pd.read_sql_query("SELECT * FROM sensor_values", conn)
                df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
                logger.info(f"📊 Loaded {len(df)} rows from full DB")
                return df
            except Exception as e:
                logger.error(f"❌ Failed to load all data: {e}")
                return pd.DataFrame()

    def get_latest_datetime(self) -> Optional[pd.Timestamp]:
        with self._connect() as conn:
            if not self._table_exists(conn):
                logger.warning("⚠️ No 'sensor_values' table found for datetime retrieval.")
                return None

            try:
                result = pd.read_sql_query("SELECT MAX(datetime) as max_dt FROM sensor_values", conn)
                if result.empty or pd.isna(result["max_dt"].iloc[0]):
                    logger.info("ℹ️ No datetime records in DB.")
                    return None
                latest = pd.to_datetime(result["max_dt"].iloc[0])
                logger.info(f"⏱ Latest datetime in DB: {latest}")
                return latest
            except Exception as e:
                logger.error(f"❌ Failed to retrieve latest datetime: {e}")
                return None
