from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

import psycopg2
import os


class Database:

    def get_conn(self):
        return psycopg2.connect(os.getenv("DATABASE_URL"))


    def fetch_all(self, query):

        with self.get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(query)

                cols = [c[0] for c in cur.description]

                rows = cur.fetchall()

                return [dict(zip(cols, r)) for r in rows]


    def fetch_one(self, query):

        with self.get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(query)

                cols = [c[0] for c in cur.description]

                row = cur.fetchone()

                if not row:
                    return None

                return dict(zip(cols, row))


db = Database()