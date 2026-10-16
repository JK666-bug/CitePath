import os

import pymysql
from pymysql.cursors import DictCursor


def connect():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "citepath"),
        password=os.environ.get("MYSQL_PASSWORD", "citepath"),
        database=os.environ.get("MYSQL_DATABASE", "citepath"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
