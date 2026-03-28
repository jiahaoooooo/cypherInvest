import os
import csv
import sqlite3
import re
from datetime import datetime
from decimal import Decimal, getcontext
from abc import ABC, abstractmethod

# 设置全局计算精度
getcontext().prec = 20

# ==========================================
# 1. 数据库存储层 (Repository Pattern)
# ==========================================
class BaseDatabase(ABC):
    @abstractmethod
    def save_records(self, records): pass

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

# ==========================================
# 3. 程序入口
# ==========================================
if __name__ == "__main__":
    # 设定数据库位置及表名
    # 物理路径: db/ark_data.db
    # 逻辑表名: holdings
    database = SQLiteDatabase("db/ark_data.db")
    
    # 初始化解析器
    processor = ArkDataProcessor(database, root_dir="raw_data")
    
    # 建议：如果是初次运行，不传参数扫描全部历史文件
    # 如果是每日定时任务，可以传今天的日期前缀
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(today_str)
    processor.scan_and_run(today_str)
    
    # 这里我们执行全量扫描
    processor.scan_and_run()