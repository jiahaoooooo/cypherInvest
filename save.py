import os
import csv
import sqlite3
import re
import argparse
from datetime import datetime
from decimal import Decimal, getcontext
from abc import ABC, abstractmethod

# 设置全局计算精度
getcontext().prec = 20

DATE_PREFIX_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})_[^.]+\.csv$")

# ==========================================
# 1. 数据库存储层 (Repository Pattern)
# ==========================================
class BaseDatabase(ABC):
    @abstractmethod
    def save_records(self, records): pass

    @abstractmethod
    def has_records_for_date(self, date_str): pass

class SQLiteDatabase(BaseDatabase):
    def __init__(self, db_path="db/ark_data.db"):
        self.db_path = db_path
        self._ensure_dir_exists()
        self._init_db()

    def _ensure_dir_exists(self):
        """确保数据库所在的文件夹存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化表并自动补齐审计字段"""
        with self._get_connection() as conn:
            # 1. 创建基础数据表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS holdings (
                    date TEXT, 
                    fund TEXT, 
                    company TEXT, 
                    ticker TEXT,
                    cusip TEXT, 
                    shares INTEGER, 
                    market_value TEXT, 
                    weight TEXT,
                    PRIMARY KEY (date, fund, ticker)
                )
            ''')
            
            # 2. 检查并动态增加审计字段 (针对旧表升级)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(holdings)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'created_at' not in columns:
                conn.execute("ALTER TABLE holdings ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            if 'updated_at' not in columns:
                conn.execute("ALTER TABLE holdings ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            conn.commit()

    def save_records(self, records):
        if not records: return
        
        # 获取当前北京时间字符串（或 UTC）用于更新
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 使用 INSERT OR REPLACE 处理重复，并手动更新 updated_at
            # 注意：REPLACE 会导致旧行的 created_at 重新生成，如需严格保留请用 ON CONFLICT 语法
            query = '''
                INSERT OR REPLACE INTO holdings 
                (date, fund, company, ticker, cusip, shares, market_value, weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            # 为每条记录拼装参数 (原记录元组 + now_str)
            data_to_save = [r + (now_str,) for r in records]
            
            cursor.executemany(query, data_to_save)
            conn.commit()
            print(f" -> 执行完毕。影响行数: {cursor.rowcount} (包含新增和替换)")

    def has_records_for_date(self, date_str):
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM holdings WHERE date = ? LIMIT 1",
                (date_str,),
            ).fetchone()
        return row is not None

# ==========================================
# 2. 数据解析层 (ETL Logic)
# ==========================================
class ArkDataProcessor:
    def __init__(self, db_engine: BaseDatabase, root_dir="raw_data"):
        self.db = db_engine
        self.root_dir = root_dir

    def _clean_to_str(self, value, is_percent=False):
        """将财务数据转换为高精度字符串"""
        if not value: return "0"
        # 移除 $, %, 逗号
        clean_str = re.sub(r'[$,%]', '', str(value).replace(',', '')).strip()
        try:
            d = Decimal(clean_str)
            if is_percent:
                d = d / Decimal('100')
            # normalize() 去除末尾多余的 0
            return str(d.normalize())
        except Exception:
            return "0"

    def process_file(self, file_path):
        """解析 CSV 并提取有效行"""
        valid_records = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                next(reader) # 跳过表头
            except StopIteration:
                return

            for row in reader:
                # 行校验：通过尝试解析第一列日期来过滤掉页脚描述
                try:
                    iso_date = datetime.strptime(row[0], '%m/%d/%Y').strftime('%Y-%m-%d')
                except (ValueError, IndexError):
                    continue # 过滤掉非日期开头的行（如末尾说明）

                # 提取数据
                shares = int(re.sub(r'[,]', '', row[5]).strip() or 0)
                mkt_val = self._clean_to_str(row[6])
                weight = self._clean_to_str(row[7], is_percent=True)

                record = (
                    iso_date,
                    row[1], # fund
                    row[2], # company
                    row[3], # ticker
                    row[4], # cusip
                    shares,
                    mkt_val,
                    weight
                )
                valid_records.append(record)
        
        self.db.save_records(valid_records)

    def scan_and_run(self, date_prefix=None):
        """
        扫描目录并执行。
        date_prefix: 如 '2026-03-25'。若不传则扫描全量历史文件。
        """
        if not os.path.exists(self.root_dir):
            print(f"未找到目录: {self.root_dir}")
            return

        print(f"开始扫描 {self.root_dir} ...")
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith(".csv"):
                    if date_prefix and not file.startswith(date_prefix):
                        continue
                    
                    print(f"处理文件: {file}")
                    self.process_file(os.path.join(root, file))


def find_latest_date_prefix(root_dir):
    """返回目录中最新的 CSV 日期前缀，找不到时返回 None。"""
    latest = None
    root_dir = os.fspath(root_dir)

    if not os.path.exists(root_dir):
        return None

    for root, _, files in os.walk(root_dir):
        for file_name in files:
            match = DATE_PREFIX_PATTERN.match(file_name)
            if not match:
                continue

            file_date = match.group(1)
            if latest is None or file_date > latest:
                latest = file_date

    return latest


def resolve_scan_date_prefix(root_dir, date_prefix=None, scan_all=False):
    """根据命令行选项决定本次需要处理的日期范围。"""
    if scan_all:
        return None
    if date_prefix:
        return date_prefix
    return find_latest_date_prefix(root_dir)


def should_skip_scan(database, date_prefix, scan_all=False):
    """每日任务在目标日期已存在数据时直接跳过，避免重复改写 SQLite。"""
    if scan_all or not date_prefix:
        return False
    return database.has_records_for_date(date_prefix)


def parse_args():
    parser = argparse.ArgumentParser(description="将 ARK CSV 数据写入 SQLite 数据库")
    parser.add_argument(
        "--date-prefix",
        help="仅处理指定日期前缀的 CSV，例如 2026-03-27",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="扫描并写入所有历史 CSV 文件",
    )
    parser.add_argument(
        "--root-dir",
        default="raw_data",
        help="CSV 根目录，默认值为 raw_data",
    )
    parser.add_argument(
        "--db-path",
        default="db/ark_data.db",
        help="SQLite 数据库路径，默认值为 db/ark_data.db",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    database = SQLiteDatabase(args.db_path)
    processor = ArkDataProcessor(database, root_dir=args.root_dir)

    target_date = resolve_scan_date_prefix(
        args.root_dir,
        date_prefix=args.date_prefix,
        scan_all=args.all,
    )

    if args.all:
        print("执行全量扫描写入。")
    elif target_date:
        print(f"执行增量扫描写入，目标日期: {target_date}")
    else:
        print("未找到可处理的 CSV 文件，跳过写入。")
        return

    if should_skip_scan(database, target_date, scan_all=args.all):
        print(f"{target_date} 的数据已存在于数据库，跳过本次写入。")
        return

    processor.scan_and_run(target_date)

# ==========================================
# 3. 程序入口
# ==========================================
if __name__ == "__main__":
    main()
